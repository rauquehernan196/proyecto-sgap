from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sgap.models import User


DEMO_PASSWORD = "demo123"
DEMO_USERS = (
    ("solicitante@sgap.local", "Solicitante", User.Role.REQUESTER),
    ("aprobador@sgap.local", "Aprobador", User.Role.APPROVER),
    ("admin@sgap.local", "Administrador", User.Role.ADMIN),
)


class Command(BaseCommand):
    help = "Crea las cuentas locales de prueba SGAP (contraseña: demo123)."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Las cuentas de prueba solo se pueden crear con DEBUG habilitado."
            )

        for email, name, role in DEMO_USERS:
            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                if user.role != role or not user.is_active:
                    raise CommandError(
                        f"{email} ya existe con otro rol o está deshabilitado. "
                        "No se modificó la cuenta."
                    )
                self.stdout.write(f"Ya existe: {email} ({role}).")
                continue

            User.objects.create_user(
                email=email,
                password=DEMO_PASSWORD,
                first_name=name,
                role=role,
            )
            self.stdout.write(self.style.SUCCESS(f"Creado: {email} ({role})."))

        self.stdout.write(
            self.style.WARNING(
                "Contraseña de prueba para las tres cuentas: demo123. "
                "Úsala solo en desarrollo local."
            )
        )
