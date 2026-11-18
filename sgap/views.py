import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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


@transaction.atomic
def _take_notifications(user):
    if user.role == User.Role.REQUESTER:
        notifications = list(
            PermissionRequest.objects.filter(
                requester=user,
                requester_notified=False,
                status__in=(
                    PermissionRequest.Status.APPROVED,
                    PermissionRequest.Status.REJECTED,
                ),
            )
        )
        field = "requester_notified"
    elif user.role == User.Role.APPROVER:
        notifications = list(
            PermissionRequest.objects.filter(
                approver_notified=False,
                status=PermissionRequest.Status.PENDING,
            ).select_related("requester", "procedure")
        )
        field = "approver_notified"
    elif user.is_administrator:
        notifications = list(
            PermissionRequest.objects.filter(
                admin_notified=False,
                status__in=(
                    PermissionRequest.Status.APPROVED,
                    PermissionRequest.Status.REJECTED,
                ),
            ).select_related("resolved_by")
        )
        field = "admin_notified"
    else:
        return []

    if user.is_administrator:
        target_url = f'{reverse("dashboard")}#recent-activity'
        action_label = "Ver actividad reciente"
    elif user.role == User.Role.APPROVER:
        target_url = f'{reverse("dashboard")}#pending-requests'
        action_label = "Ver solicitudes para aprobar"
    else:
        target_url = f'{reverse("dashboard")}#my-requests'
        action_label = "Ver mis solicitudes"

    result = []
    for item in notifications:
        if field == "requester_notified":
            if item.status == PermissionRequest.Status.APPROVED:
                result.append(
                    (
                        messages.SUCCESS,
                        f"Tu solicitud {item.code} fue aprobada con éxito.",
                        target_url,
                        action_label,
                    )
                )
            else:
                message = f"Tu solicitud {item.code} fue denegada."
                if item.rejection_reason:
                    message += f" Motivo: {item.rejection_reason}"
                result.append((messages.ERROR, message, target_url, action_label))
        elif field == "approver_notified":
            requester = item.requester.get_full_name() or item.requester.email
            result.append(
                (
                    messages.INFO,
                    f"Llegó una nueva solicitud {item.code} de {requester} "
                    f"para {item.procedure.name}.",
                    target_url,
                    action_label,
                )
            )
        else:
            decision = (
                "autorizó"
                if item.status == PermissionRequest.Status.APPROVED
                else "denegó"
            )
            approver = str(item.resolved_by) if item.resolved_by else "El aprobador"
            level = (
                messages.SUCCESS
                if item.status == PermissionRequest.Status.APPROVED
                else messages.WARNING
            )
            result.append(
                (
                    level,
                    f"{approver} {decision} la solicitud {item.code}.",
                    target_url,
                    action_label,
                )
            )

    if notifications:
        PermissionRequest.objects.filter(
            pk__in=[item.pk for item in notifications]
        ).update(**{field: True})
    return result


@login_required
def dashboard(request):
    user = request.user
    for level, message, _, _ in _take_notifications(user):
        messages.add_message(request, level, message)
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
def notification_poll(request):
    notifications = _take_notifications(request.user)
    return JsonResponse(
        {
            "notifications": [
                {
                    "level": messages.DEFAULT_TAGS.get(level, "info"),
                    "message": message,
                    "url": target_url,
                    "action": action_label,
                }
                for level, message, target_url, action_label in notifications
            ]
        }
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
                    f"Solicitud {permission_request.code} realizada con éxito y enviada al aprobador.",
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
        messages.success(
            request,
            f"Solicitud {permission_request.code} cancelada con éxito.",
        )
    return redirect("dashboard")


@role_required(User.Role.APPROVER)
@require_POST
def request_resolve(request, request_id):
    form = RequestDecisionForm(request.POST)
    if not form.is_valid():
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
        status = "aprobada con éxito" if approved else "denegada"
        messages.success(
            request, f"La solicitud {permission_request.code} fue {status}."
        )
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
