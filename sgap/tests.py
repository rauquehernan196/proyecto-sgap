from io import StringIO
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AuditLog, PermissionRequest, Procedure, User


@override_settings(DEBUG=True)
class DemoUserCommandTests(TestCase):
    def test_command_creates_login_ready_users_for_each_role(self):
        call_command("create_demo_users", stdout=StringIO())

        expected = (
            ("solicitante@sgap.local", User.Role.REQUESTER),
            ("aprobador@sgap.local", User.Role.APPROVER),
            ("admin@sgap.local", User.Role.ADMIN),
        )
        for email, role in expected:
            with self.subTest(email=email):
                user = User.objects.get(email=email)
                self.assertEqual(user.role, role)
                self.assertTrue(user.is_active)
                self.assertTrue(user.check_password("demo123"))
                self.assertTrue(
                    self.client.login(username=email, password="demo123")
                )
                self.client.logout()

    def test_command_is_idempotent(self):
        call_command("create_demo_users", stdout=StringIO())
        original_password = User.objects.get(
            email="solicitante@sgap.local"
        ).password

        call_command("create_demo_users", stdout=StringIO())

        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(
            User.objects.get(email="solicitante@sgap.local").password,
            original_password,
        )

    @override_settings(DEBUG=False)
    def test_command_refuses_to_create_demo_users_when_debug_is_off(self):
        with self.assertRaises(CommandError):
            call_command("create_demo_users", stdout=StringIO())

        self.assertFalse(User.objects.filter(email__endswith="@sgap.local").exists())


class SgapWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.requester = User.objects.create_user(
            "solicitante@example.com", "Strong-password-123", role=User.Role.REQUESTER
        )
        cls.other_requester = User.objects.create_user(
            "otro@example.com", "Strong-password-123", role=User.Role.REQUESTER
        )
        cls.approver = User.objects.create_user(
            "aprobador@example.com", "Strong-password-123", role=User.Role.APPROVER
        )
        cls.admin = User.objects.create_superuser(
            "admin@example.com", "Strong-password-123"
        )
        cls.procedure = Procedure.objects.create(
            name="Permiso de prueba", fields=["Motivo", "Fecha solicitada"]
        )

    def test_requester_creates_dynamic_request_and_it_is_audited(self):
        self.client.force_login(self.requester)
        requested_date = timezone.localdate() + timedelta(days=1)
        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": self.procedure.pk,
                "detail_0": "Consulta médica",
                "detail_1": requested_date.isoformat(),
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request = PermissionRequest.objects.get()
        self.assertEqual(
            permission_request.details,
            {
                "Motivo": "Consulta médica",
                "Fecha solicitada": requested_date.strftime("%d/%m/%Y"),
            },
        )
        self.assertEqual(permission_request.status, PermissionRequest.Status.PENDING)
        self.assertEqual(AuditLog.objects.get().action, "Solicitud creada")

    def test_restricted_area_request_uses_select_with_configured_choices(self):
        procedure = Procedure.objects.create(
            name="Acceso restringido",
            fields=["Área", "Motivo", "Fecha y hora"],
        )
        self.client.force_login(self.requester)

        response = self.client.get(
            reverse("request_create"), {"procedure": procedure.pk}
        )

        self.assertContains(response, '<select name="detail_0"')
        self.assertContains(response, 'type="datetime-local"')
        self.assertContains(response, "Sala de servidores / TI")
        self.assertContains(response, "Planta de producción")

    def test_restricted_area_request_rejects_an_unlisted_area(self):
        procedure = Procedure.objects.create(
            name="Acceso restringido",
            fields=["Área", "Motivo", "Fecha y hora"],
        )
        self.client.force_login(self.requester)
        requested_datetime = timezone.localtime(timezone.now() + timedelta(days=1))

        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": procedure.pk,
                "detail_0": "Área no autorizada",
                "detail_1": "Mantenimiento",
                "detail_2": "09:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PermissionRequest.objects.exists())
        self.assertTrue(response.context["form"].has_error("detail_0"))

    def test_request_form_formats_and_validates_restricted_access_datetime(self):
        procedure = Procedure.objects.create(
            name="Acceso restringido",
            fields=["Área", "Motivo", "Fecha y hora"],
        )
        self.client.force_login(self.requester)
        requested_datetime = timezone.localtime(timezone.now() + timedelta(days=1))

        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": procedure.pk,
                "detail_0": "Laboratorio",
                "detail_1": "Mantenimiento",
                "detail_2": requested_datetime.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request = PermissionRequest.objects.get()
        self.assertEqual(
            permission_request.details["Fecha y hora"],
            requested_datetime.strftime("%d/%m/%Y %H:%M"),
        )

    def test_request_form_rejects_invalid_restricted_access_datetime(self):
        procedure = Procedure.objects.create(
            name="Acceso restringido",
            fields=["Área", "Motivo", "Fecha y hora"],
        )
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": procedure.pk,
                "detail_0": "Laboratorio",
                "detail_1": "Mantenimiento",
                "detail_2": "2002-02-31T25:90",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PermissionRequest.objects.exists())
        self.assertTrue(response.context["form"].has_error("detail_2"))
        self.assertContains(response, "Ingresa una fecha y hora válidas.")

    def test_request_form_uses_calendar_inputs_and_rejects_invalid_date(self):
        procedure = Procedure.objects.create(
            name="Permiso con fecha", fields=["Fecha solicitada"]
        )
        self.client.force_login(self.requester)

        page = self.client.get(
            reverse("request_create"), {"procedure": procedure.pk}
        )
        self.assertContains(page, 'type="date"')

        response = self.client.post(
            reverse("request_create"),
            {"procedure": procedure.pk, "detail_0": "2026-02-31"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PermissionRequest.objects.exists())
        self.assertTrue(response.context["form"].has_error("detail_0"))
        self.assertContains(response, "Ingresa una fecha válida.")

    def test_request_datetime_is_displayed_in_a_readable_format(self):
        procedure = Procedure.objects.create(
            name="Permiso con fecha y hora", fields=["Fecha y hora"]
        )
        self.client.force_login(self.requester)
        requested_datetime = timezone.localtime(timezone.now() + timedelta(days=1))

        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": procedure.pk,
                "detail_0": requested_datetime.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request = PermissionRequest.objects.get()
        self.assertEqual(
            permission_request.details["Fecha y hora"],
            requested_datetime.strftime("%d/%m/%Y %H:%M"),
        )
        self.assertContains(
            self.client.get(reverse("dashboard")),
            requested_datetime.strftime("%d/%m/%Y %H:%M"),
        )

    def test_request_form_rejects_a_date_before_today(self):
        procedure = Procedure.objects.create(
            name="Permiso con fecha pasada", fields=["Fecha solicitada"]
        )
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": procedure.pk,
                "detail_0": (timezone.localdate() - timedelta(days=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PermissionRequest.objects.exists())
        self.assertTrue(response.context["form"].has_error("detail_0"))
        self.assertContains(response, "La fecha no puede ser anterior a hoy.")

    def test_request_form_rejects_a_datetime_before_now(self):
        procedure = Procedure.objects.create(
            name="Permiso con fecha y hora pasada", fields=["Fecha y hora"]
        )
        self.client.force_login(self.requester)
        past_datetime = timezone.localtime(timezone.now() - timedelta(days=1))

        response = self.client.post(
            reverse("request_create"),
            {
                "procedure": procedure.pk,
                "detail_0": past_datetime.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PermissionRequest.objects.exists())
        self.assertTrue(response.context["form"].has_error("detail_0"))
        self.assertContains(
            response,
            "La fecha y hora no pueden ser anteriores al momento actual.",
        )

    def test_approver_resolves_pending_request(self):
        permission_request = PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Consulta"},
        )
        self.client.force_login(self.approver)

        response = self.client.post(
            reverse("request_resolve", args=[permission_request.pk]),
            {"decision": PermissionRequest.Status.APPROVED},
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request.refresh_from_db()
        self.assertEqual(permission_request.status, PermissionRequest.Status.APPROVED)
        self.assertEqual(permission_request.resolved_by, self.approver)
        self.assertIsNone(permission_request.rejection_reason)

    def test_approver_can_reject_with_an_optional_reason(self):
        permission_request = PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Consulta"},
        )
        self.client.force_login(self.approver)

        response = self.client.post(
            reverse("request_resolve", args=[permission_request.pk]),
            {
                "decision": PermissionRequest.Status.REJECTED,
                "rejection_reason": "Falta documentación",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request.refresh_from_db()
        self.assertEqual(permission_request.status, PermissionRequest.Status.REJECTED)
        self.assertEqual(permission_request.rejection_reason, "Falta documentación")

        self.client.force_login(self.requester)
        self.assertContains(self.client.get(reverse("dashboard")), "Falta documentación")

    def test_blank_rejection_reason_is_saved_as_null(self):
        permission_request = PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Consulta"},
        )
        self.client.force_login(self.approver)

        response = self.client.post(
            reverse("request_resolve", args=[permission_request.pk]),
            {
                "decision": PermissionRequest.Status.REJECTED,
                "rejection_reason": "   ",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request.refresh_from_db()
        self.assertIsNone(permission_request.rejection_reason)


    def test_requester_cannot_cancel_another_users_request(self):
        permission_request = PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Consulta"},
        )
        self.client.force_login(self.other_requester)

        response = self.client.post(
            reverse("request_cancel", args=[permission_request.pk])
        )

        self.assertEqual(response.status_code, 404)
        permission_request.refresh_from_db()
        self.assertEqual(permission_request.status, PermissionRequest.Status.PENDING)

    def test_requester_dashboard_shows_all_own_results_and_hides_other_users(self):
        PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Trámite propio autorizado"},
            status=PermissionRequest.Status.APPROVED,
            resolved_by=self.approver,
        )
        PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Trámite propio denegado"},
            status=PermissionRequest.Status.REJECTED,
            resolved_by=self.approver,
        )
        PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Trámite propio pendiente"},
        )
        PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Trámite propio cancelado"},
            status=PermissionRequest.Status.CANCELLED,
        )
        PermissionRequest.objects.create(
            requester=self.other_requester,
            procedure=self.procedure,
            details={"Motivo": "Trámite de otra cuenta"},
            status=PermissionRequest.Status.APPROVED,
            resolved_by=self.approver,
        )
        self.client.force_login(self.requester)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trámite propio autorizado")
        self.assertContains(response, "Trámite propio denegado")
        self.assertContains(response, "Trámite propio pendiente")
        self.assertContains(response, "Trámite propio cancelado")
        self.assertContains(response, "Autorizado")
        self.assertContains(response, "Denegado")
        self.assertNotContains(response, "Trámite de otra cuenta")

    def test_admin_can_export_audit_history_as_csv(self):
        AuditLog.objects.create(
            action="Solicitud creada",
            reference="SG-0001",
            details="Permisos",
            actor=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("history_export"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn(b"SG-0001", response.content)

    def test_role_without_permission_cannot_open_user_management(self):
        self.client.force_login(self.requester)

        response = self.client.get(reverse("user_list"))

        self.assertEqual(response.status_code, 403)

    def test_dashboard_renders_for_each_role(self):
        for account in (self.requester, self.approver, self.admin):
            with self.subTest(role=account.role):
                self.client.force_login(account)
                response = self.client.get(reverse("dashboard"))
                self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=True, INTERNAL_IPS=["127.0.0.1"])
    def test_login_shows_demo_accounts_in_local_debug_mode(self):
        response = self.client.get(reverse("login"))

        for email in (
            "solicitante@sgap.local",
            "aprobador@sgap.local",
            "admin@sgap.local",
            "demo123",
        ):
            with self.subTest(value=email):
                self.assertContains(response, email)

    @override_settings(DEBUG=False, INTERNAL_IPS=["127.0.0.1"])
    def test_login_hides_demo_accounts_when_debug_is_off(self):
        response = self.client.get(reverse("login"))

        self.assertNotContains(response, "solicitante@sgap.local")
        self.assertNotContains(response, "demo123")

    def test_requester_dashboard_has_procedure_carousel_and_footer(self):
        self.client.force_login(self.requester)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "carousel.js")
        self.assertContains(response, "site-footer")
        self.assertContains(response, self.procedure.name)
        self.assertContains(
            response,
            f'href="{reverse("request_create")}?procedure={self.procedure.pk}"',
        )

    def test_pages_include_both_muted_looping_background_videos(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, "background-videos.js")
        self.assertContains(response, "muted playsinline")
        self.assertContains(response, "8102896-hd_1920_1080_25fps.mp4")
        self.assertContains(response, "6804661-uhd_4096_2160_25fps.mp4")
        self.assertNotContains(response, "loop playsinline")

    def test_switch_session_logs_out_and_returns_to_login(self):
        self.client.force_login(self.requester)

        response = self.client.post(reverse("switch_session"))

        self.assertRedirects(response, reverse("login"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        login_page = self.client.get(reverse("login"))
        self.assertContains(login_page, "Iniciar sesión")

    def test_admin_can_create_a_procedure_with_custom_fields(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("procedure_create"),
            {
                "name": "Acceso temporal",
                "field_names": "Área, Motivo",
                "active": "on",
            },
        )

        self.assertRedirects(response, reverse("procedure_list"))
        procedure = Procedure.objects.get(name="Acceso temporal")
        self.assertEqual(procedure.fields, ["Área", "Motivo"])

    def test_custom_user_is_available_in_django_admin(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin:sgap_user_add"))

        self.assertEqual(response.status_code, 200)

    def test_invalid_decision_does_not_resolve_request(self):
        permission_request = PermissionRequest.objects.create(
            requester=self.requester,
            procedure=self.procedure,
            details={"Motivo": "Consulta"},
        )
        self.client.force_login(self.approver)

        response = self.client.post(
            reverse("request_resolve", args=[permission_request.pk]),
            {"decision": "No es una decisión"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        permission_request.refresh_from_db()
        self.assertEqual(permission_request.status, PermissionRequest.Status.PENDING)
