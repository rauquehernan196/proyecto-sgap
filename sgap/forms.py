import re
from datetime import datetime

from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import PermissionRequest, Procedure, User


RESTRICTED_AREAS = (
    "Bodega o almacén",
    "Sala de servidores / TI",
    "Archivo",
    "Laboratorio",
    "Taller",
    "Oficina de administración",
    "Sala eléctrica",
    "Planta de producción",
)


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput,
        strip=False,
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role"]
        labels = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "Correo electrónico",
            "role": "Rol",
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = user.email.strip().lower()
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ProcedureForm(forms.ModelForm):
    field_names = forms.CharField(
        label="Campos del formulario",
        help_text="Escribe los nombres separados por comas.",
        widget=forms.TextInput(attrs={"placeholder": "Motivo, Fecha solicitada"}),
    )

    class Meta:
        model = Procedure
        fields = ["name", "active"]
        labels = {"name": "Nombre", "active": "Habilitado"}

    def clean_field_names(self):
        names = [name.strip() for name in self.cleaned_data["field_names"].split(",")]
        if not names or any(not name for name in names):
            raise forms.ValidationError("Completa todos los nombres de campos.")
        if len(set(names)) != len(names):
            raise forms.ValidationError("Cada campo debe tener un nombre distinto.")
        return names

    def clean(self):
        cleaned_data = super().clean()
        if "field_names" in cleaned_data:
            self.instance.fields = cleaned_data["field_names"]
        return cleaned_data

    def save(self, commit=True):
        procedure = super().save(commit=False)
        procedure.fields = self.cleaned_data["field_names"]
        if commit:
            procedure.save()
        return procedure


class RequestCreateForm(forms.Form):
    procedure = forms.ModelChoiceField(
        queryset=Procedure.objects.none(),
        label="Tipo de procedimiento",
    )

    def __init__(self, *args, procedures=None, procedure=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["procedure"].queryset = procedures or Procedure.objects.none()
        self.selected_procedure = procedure
        if procedure is not None:
            self.fields["procedure"].initial = procedure
            for index, field_label in enumerate(procedure.fields):
                normalized_label = field_label.strip().casefold()
                if normalized_label == "fecha y hora":
                    self.fields[f"detail_{index}"] = forms.CharField(
                        label=field_label,
                        max_length=16,
                        widget=forms.TextInput(
                            attrs={
                                "placeholder": "DD/MM/AAAA HH:MM",
                                "inputmode": "numeric",
                                "autocomplete": "off",
                                "data-datetime-mask": "true",
                            }
                        ),
                    )
                elif normalized_label == "área":
                    self.fields[f"detail_{index}"] = forms.ChoiceField(
                        label=field_label,
                        choices=[("", "Selecciona un área")]
                        + [(area, area) for area in RESTRICTED_AREAS],
                    )
                else:
                    self.fields[f"detail_{index}"] = forms.CharField(
                        label=field_label,
                        max_length=2000,
                        widget=forms.Textarea(attrs={"rows": 2}),
                    )

    def clean(self):
        cleaned_data = super().clean()
        chosen = cleaned_data.get("procedure")
        if self.selected_procedure and chosen != self.selected_procedure:
            self.add_error("procedure", "Selecciona un procedimiento válido.")
        if self.selected_procedure:
            for index, label in enumerate(self.selected_procedure.fields):
                field_name = f"detail_{index}"
                value = cleaned_data.get(field_name)
                if label.strip().casefold() != "fecha y hora" or value is None:
                    continue
                if not re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", value):
                    self.add_error(
                        field_name,
                        "Usa el formato DD/MM/AAAA HH:MM.",
                    )
                    continue
                try:
                    datetime.strptime(value, "%d/%m/%Y %H:%M")
                except ValueError:
                    self.add_error(
                        field_name,
                        "Ingresa una fecha y hora válidas.",
                    )
        return cleaned_data

    def detail_values(self):
        if not self.is_valid() or self.selected_procedure is None:
            return {}
        return {
            label: self.cleaned_data[f"detail_{index}"].strip()
            for index, label in enumerate(self.selected_procedure.fields)
        }


class RequestDecisionForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(
            (PermissionRequest.Status.APPROVED, "Aprobar"),
            (PermissionRequest.Status.REJECTED, "Rechazar"),
        )
    )
