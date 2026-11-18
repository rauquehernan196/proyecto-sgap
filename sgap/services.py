from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import AuditLog, PermissionRequest, Procedure, User


def record_audit(action, reference, details, actor):
    AuditLog.objects.create(
        action=action,
        reference=reference,
        details=details,
        actor=actor,
    )


@transaction.atomic
def create_request(requester, procedure, details):
    if requester.role != User.Role.REQUESTER:
        raise PermissionDenied("Solo un solicitante puede crear solicitudes.")
    if not procedure.active or not Procedure.objects.filter(pk=procedure.pk, active=True).exists():
        raise ValidationError("El procedimiento no está disponible.")
    if not details or any(not value.strip() for value in details.values()):
        raise ValidationError("Completa todos los datos de la solicitud.")

    permission_request = PermissionRequest.objects.create(
        requester=requester,
        procedure=procedure,
        details=details,
        approver_notified=False,
    )
    record_audit(
        "Solicitud creada", permission_request.code, procedure.name, requester
    )
    return permission_request


@transaction.atomic
def resolve_request(request_id, approver, approved, rejection_reason=None):
    if approver.role != User.Role.APPROVER:
        raise PermissionDenied("Solo un aprobador puede resolver solicitudes.")
    permission_request = PermissionRequest.objects.select_for_update().filter(
        pk=request_id
    ).first()
    if permission_request is None:
        raise ValidationError("No se encontró la solicitud.")
    if permission_request.status != PermissionRequest.Status.PENDING:
        raise ValidationError("La solicitud ya fue resuelta.")

    permission_request.status = (
        PermissionRequest.Status.APPROVED
        if approved
        else PermissionRequest.Status.REJECTED
    )
    permission_request.rejection_reason = (
        None if approved else (rejection_reason or "").strip() or None
    )
    permission_request.requester_notified = False
    permission_request.admin_notified = False
    permission_request.resolved_by = approver
    permission_request.save(
        update_fields=[
            "status",
            "rejection_reason",
            "requester_notified",
            "admin_notified",
            "resolved_by",
            "updated_at",
        ]
    )
    action = "Solicitud aprobada" if approved else "Solicitud rechazada"
    audit_details = f"Decisión de {approver}"
    if permission_request.rejection_reason:
        audit_details += f". Motivo: {permission_request.rejection_reason}"
    record_audit(action, permission_request.code, audit_details, approver)
    return permission_request


@transaction.atomic
def cancel_request(permission_request, requester):
    permission_request = PermissionRequest.objects.select_for_update().get(
        pk=permission_request.pk
    )
    if permission_request.requester_id != requester.pk:
        raise PermissionDenied("Solo puedes cancelar tus propias solicitudes.")
    if permission_request.status != PermissionRequest.Status.PENDING:
        raise ValidationError("La solicitud ya fue resuelta.")

    permission_request.status = PermissionRequest.Status.CANCELLED
    permission_request.save(update_fields=["status", "updated_at"])
    record_audit(
        "Solicitud cancelada",
        permission_request.code,
        f"Por {requester}",
        requester,
    )
    return permission_request
