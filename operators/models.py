from django.db import models
from django.core.validators import RegexValidator, EmailValidator

RFC_REGEX = r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$'

class Operator(models.Model):
    first_name = models.CharField("Nombre(s)", max_length=80)
    last_name_paterno = models.CharField("Apellido paterno", max_length=80)
    last_name_materno = models.CharField("Apellido materno", max_length=80, blank=True)
    rfc = models.CharField(
        "RFC",
        max_length=13,
        unique=False,
        blank=True,
        null=True,
        validators=[RegexValidator(RFC_REGEX, message="RFC inválido")],
    )
    license_number = models.CharField("No. de Licencia", max_length=30, unique=True)
    license_expires_at = models.DateField("Vigencia de licencia")
    phone = models.CharField("Teléfono", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True, validators=[EmailValidator()])
    active = models.BooleanField("Activo", default=True)
    deleted = models.BooleanField("Eliminado", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Operador"
        verbose_name_plural = "Operadores"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name_paterno} {self.last_name_materno or ''}".strip()
