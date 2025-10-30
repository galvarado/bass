# audit/apps.py
from django.apps import AppConfig

class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Auditoría"

    def ready(self):
        # registra los receivers
        from . import signals  # noqa: F401
        from . import auth_signals  # noqa: F401
