from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("notifications/poll/", views.notification_poll, name="notification_poll"),
    path("cambiar-sesion/", views.switch_session, name="switch_session"),
    path("solicitudes/nueva/", views.request_create, name="request_create"),
    path(
        "solicitudes/<int:request_id>/cancelar/",
        views.request_cancel,
        name="request_cancel",
    ),
    path(
        "solicitudes/<int:request_id>/resolver/",
        views.request_resolve,
        name="request_resolve",
    ),
    path("usuarios/", views.user_list, name="user_list"),
    path("usuarios/crear/", views.user_create, name="user_create"),
    path("usuarios/<int:user_id>/estado/", views.user_toggle, name="user_toggle"),
    path("procedimientos/", views.procedure_list, name="procedure_list"),
    path("procedimientos/crear/", views.procedure_create, name="procedure_create"),
    path(
        "procedimientos/<int:procedure_id>/estado/",
        views.procedure_toggle,
        name="procedure_toggle",
    ),
    path("historial/", views.history_list, name="history_list"),
    path("historial/exportar/", views.history_export, name="history_export"),
]
