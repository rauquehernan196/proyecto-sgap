from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sgap", "0004_permissionrequest_requester_notified"),
    ]

    operations = [
        migrations.AddField(
            model_name="permissionrequest",
            name="approver_notified",
            field=models.BooleanField(
                default=True,
                verbose_name="nueva solicitud notificada al aprobador",
            ),
        ),
        migrations.AddField(
            model_name="permissionrequest",
            name="admin_notified",
            field=models.BooleanField(
                default=True,
                verbose_name="decisión notificada al administrador",
            ),
        ),
    ]
