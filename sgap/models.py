from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("El superusuario debe tener is_staff e is_superuser.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        REQUESTER = "Solicitante", "Solicitante"
        APPROVER = "Aprobador", "Aprobador"
        ADMIN = "Administrador", "Administrador"

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    role = models.CharField(
        "rol", max_length=20, choices=Role.choices, default=Role.REQUESTER
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["last_name", "first_name", "email"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_administrator(self):
        return self.is_superuser or self.role == self.Role.ADMIN


class Procedure(models.Model):
    name = models.CharField("nombre", max_length=120, unique=True)
    fields = models.JSONField("campos del formulario", default=list)
    active = models.BooleanField("habilitado", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "procedimiento"
        verbose_name_plural = "procedimientos"

    def __str__(self):
        return self.name

    def clean(self):
        if not isinstance(self.fields, list) or not self.fields:
            raise ValidationError({"fields": "Agrega al menos un campo al formulario."})
        if any(not isinstance(item, str) or not item.strip() for item in self.fields):
            raise ValidationError({"fields": "Los nombres de campos no pueden estar vacíos."})


class PermissionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pendiente", "Pendiente"
        APPROVED = "Aprobada", "Aprobada"
        REJECTED = "Rechazada", "Rechazada"
        CANCELLED = "Cancelada", "Cancelada"

    requester = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="permission_requests",
        verbose_name="solicitante",
    )
    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="procedimiento",
    )
    details = models.JSONField("detalle", default=dict)
    rejection_reason = models.TextField(
        "motivo de rechazo", blank=True, null=True, default=None
    )
    status = models.CharField(
        "estado", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField("creada", default=timezone.now)
    updated_at = models.DateTimeField("actualizada", auto_now=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_requests",
        verbose_name="resuelta por",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "solicitud"
        verbose_name_plural = "solicitudes"

    def __str__(self):
        return self.code

    @property
    def code(self):
        return f"SG-{self.pk:04d}" if self.pk else "SG-nueva"


class AuditLog(models.Model):
    action = models.CharField("acción", max_length=80)
    reference = models.CharField("referencia", max_length=120)
    details = models.TextField("detalle", blank=True)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
        verbose_name="usuario",
    )
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "registro de historial"
        verbose_name_plural = "historial"

    def __str__(self):
        return f"{self.action} - {self.reference}"
