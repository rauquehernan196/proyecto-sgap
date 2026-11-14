from django.db import migrations


PROCEDURES = [
    ("Compra de materiales", ["Materiales requeridos", "Monto estimado"]),
    ("Viáticos", ["Destino", "Fechas del viaje", "Monto estimado"]),
    ("Permisos", ["Motivo", "Fecha(s) solicitada(s)"]),
    ("Acceso a áreas restringidas", ["Área", "Motivo", "Fecha y hora"]),
]


def create_initial_procedures(apps, schema_editor):
    Procedure = apps.get_model("sgap", "Procedure")
    for name, fields in PROCEDURES:
        Procedure.objects.get_or_create(name=name, defaults={"fields": fields})


class Migration(migrations.Migration):
    dependencies = [("sgap", "0001_initial")]

    operations = [
        migrations.RunPython(
            create_initial_procedures,
            reverse_code=migrations.RunPython.noop,
        )
    ]
