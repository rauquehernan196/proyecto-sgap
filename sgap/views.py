import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    ProcedureForm,
    RequestCreateForm,
    RequestDecisionForm,
    UserCreateForm,
)
from .models import AuditLog, PermissionRequest, Procedure, User
from .services import (
    cancel_request,
    create_request,
    record_audit,
    resolve_request,
)


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = request.user
            allowed = user.role in roles or (
                User.Role.ADMIN in roles and user.is_administrator
            )
            if not allowed:
                raise PermissionDenied("No tienes permiso para acceder a esta sección.")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


@login_required
def dashboard(request):
    user = request.user
    if user.is_administrator:
        counts = {
            item["status"]: item["total"]
            for item in PermissionRequest.objects.values("status").annotate(
                total=Count("id")
            )
        }
        return render(
            request,
            "sgap/dashboard.html",
            {
                "role": User.Role.ADMIN,
                "counts": counts,
                "recent_history": AuditLog.objects.select_related("actor")[:8],
            },
        )
    if user.role == User.Role.APPROVER:
        pending_requests = PermissionRequest.objects.filter(
            status=PermissionRequest.Status.PENDING
        ).select_related("requester", "procedure")
        return render(
            request,
            "sgap/dashboard.html",
            {"role": user.role, "requests": pending_requests},
        )
    requests = (
        PermissionRequest.objects.filter(requester=user)
        .select_related("procedure", "resolved_by")
        .order_by("-created_at")
    )
    return render(
        request,
        "sgap/dashboard.html",
        {
            "role": user.role,
            "requests": requests,
            "available_procedures": Procedure.objects.filter(active=True),
        },
    )


@login_required
@require_POST
def switch_session(request):
    logout(request)
    return redirect("login")


@role_required(User.Role.REQUESTER)
def request_create(request):
    procedures = Procedure.objects.filter(active=True)
    if not procedures.exists():
        messages.info(request, "No hay procedimientos habilitados.")
        return redirect("dashboard")

    procedure_id = request.POST.get("procedure") if request.method == "POST" else request.GET.get("procedure")
    procedure = procedures.filter(pk=procedure_id).first() if procedure_id else procedures.first()

    if request.method == "POST":
        form = RequestCreateForm(
            request.POST, procedures=procedures, procedure=procedure
        )
        if form.is_valid() and procedure is not None:
            try:
                permission_request = create_request(
                    request.user, procedure, form.detail_values()
                )
            except ValidationError as error:
                form.add_error(None, error.messages[0])
            else:
                messages.success(
                    request,
                    f"La solicitud {permission_request.code} fue enviada al aprobador.",
                )
                return redirect("dashboard")
    else:
        form = RequestCreateForm(
            procedures=procedures, procedure=procedure
        )

    return render(
        request,
        "sgap/request_form.html",
        {"form": form, "selected_procedure": procedure},
    )


@role_required(User.Role.REQUESTER)
@require_POST
def request_cancel(request, request_id):
    permission_request = get_object_or_404(
        PermissionRequest, pk=request_id, requester=request.user
    )
    try:
        cancel_request(permission_request, request.user)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"La solicitud {permission_request.code} fue cancelada.")
    return redirect("dashboard")


@role_required(User.Role.APPROVER)
@require_POST
def request_resolve(request, request_id):
    form = RequestDecisionForm(request.POST)
    if not form.is_valid():
        if form.has_error("rejection_reason"):
            messages.error(request, form.errors["rejection_reason"][0])
        else:
            messages.error(request, "Selecciona una decisión válida para la solicitud.")
        return redirect("dashboard")
    approved = form.cleaned_data["decision"] == PermissionRequest.Status.APPROVED
    try:
        permission_request = resolve_request(
            request_id,
            request.user,
            approved,
            form.cleaned_data["rejection_reason"],
        )
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        status = permission_request.get_status_display().lower()
        messages.success(request, f"La solicitud {permission_request.code} fue {status}.")
    return redirect("dashboard")


@role_required(User.Role.ADMIN)
def user_list(request):
    return render(
        request,
        "sgap/users.html",
        {"users": User.objects.all(), "form": UserCreateForm()},
    )


@role_required(User.Role.ADMIN)
@require_POST
def user_create(request):
    form = UserCreateForm(request.POST)
    if form.is_valid():
        user = form.save()
        record_audit("Usuario creado", user.email, f"Rol: {user.get_role_display()}", request.user)
        messages.success(request, f"Se creó el usuario {user.email}.")
        return redirect("user_list")
    return render(
        request,
        "sgap/users.html",
        {"users": User.objects.all(), "form": form},
        status=400,
    )


@role_required(User.Role.ADMIN)
@require_POST
def user_toggle(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.pk == request.user.pk:
        messages.error(request, "No puedes deshabilitar tu propia cuenta.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        action = "Usuario habilitado" if user.is_active else "Usuario deshabilitado"
        record_audit(action, user.email, f"Rol: {user.get_role_display()}", request.user)
        messages.success(request, f"Se actualizó el estado de {user.email}.")
    return redirect("user_list")


@role_required(User.Role.ADMIN)
def procedure_list(request):
    return render(
        request,
        "sgap/procedures.html",
        {"procedures": Procedure.objects.all(), "form": ProcedureForm()},
    )


@role_required(User.Role.ADMIN)
@require_POST
def procedure_create(request):
    form = ProcedureForm(request.POST)
    if form.is_valid():
        procedure = form.save()
        record_audit("Procedimiento creado", procedure.name, "Habilitado", request.user)
        messages.success(request, f"Se creó el procedimiento {procedure.name}.")
        return redirect("procedure_list")
    return render(
        request,
        "sgap/procedures.html",
        {"procedures": Procedure.objects.all(), "form": form},
        status=400,
    )


@role_required(User.Role.ADMIN)
@require_POST
def procedure_toggle(request, procedure_id):
    procedure = get_object_or_404(Procedure, pk=procedure_id)
    procedure.active = not procedure.active
    procedure.save(update_fields=["active"])
    state = "habilitado" if procedure.active else "deshabilitado"
    record_audit("Procedimiento actualizado", procedure.name, state, request.user)
    messages.success(request, f"El procedimiento quedó {state}.")
    return redirect("procedure_list")


@role_required(User.Role.ADMIN)
def history_list(request):
    selected_action = request.GET.get("accion", "")
    history = AuditLog.objects.select_related("actor")
    if selected_action:
        history = history.filter(action=selected_action)
    return render(
        request,
        "sgap/history.html",
        {
            "history": history[:250],
            "selected_action": selected_action,
            "actions": AuditLog.objects.order_by()
            .values_list("action", flat=True)
            .distinct(),
            "counts": {
                item["status"]: item["total"]
                for item in PermissionRequest.objects.values("status").annotate(
                    total=Count("id")
                )
            },
        },
    )


@role_required(User.Role.ADMIN)
def history_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="historial_sgap.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Fecha", "Acción", "Referencia", "Detalle", "Usuario"])
    for entry in AuditLog.objects.select_related("actor"):
        writer.writerow(
            [
                entry.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                entry.action,
                entry.reference,
                entry.details,
                entry.actor.email if entry.actor else "",
            ]
        )
    return response
