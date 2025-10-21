from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
from django.core.serializers.json import DjangoJSONEncoder


class AuditLog(models.Model):
    ACTIONS = [
        ("create",      "Creación"),
        ("update",      "Actualización"),
        ("soft_delete", "Eliminación"),
        ("restore",     "Restauración"),
        ("login",       "Inicio de sesión"),
        ("logout",      "Cierre de sesión"),
        ("export",      "Exportación"),
        ("import",      "Importación"),
        ("permission",  "Cambio de permisos"),
        ("other",       "Otra"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="audit_logs")
    action = models.CharField(max_length=32, choices=ACTIONS)

    # Target genérico (opcional)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=64, null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    object_repr = models.CharField(max_length=255, blank=True)  # snapshot legible
    # Cambios (diff) o payload libre de la acción
    changes = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    # Request context
    ip = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=8, blank=True)
    user_agent = models.TextField(blank=True)

    # Etiquetas (para agrupar: módulo, entorno, tenant, etc.)
    tags    = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(default=now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        who = self.user.get_username() if self.user else "anon"
        target = self.object_repr or f"{self.content_type}:{self.object_id}" if self.content_type_id else ""
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {who} {self.action} {target}"