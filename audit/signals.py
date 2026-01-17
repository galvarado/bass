# audit/signals.py
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from .middleware import get_current_request
from .models import AuditLog
from .utils import model_snapshot, diff

import datetime
from django.db.models.fields.files import FieldFile, ImageFieldFile

# ============================================================
# Config
# ============================================================

AUDIT_INCLUDE = getattr(settings, "AUDIT_INCLUDE", None)
AUDIT_EXCLUDE = set(getattr(settings, "AUDIT_EXCLUDE", {
    "audit.AuditLog",
    "contenttypes.ContentType",
    "sessions.Session",
    "accounts.Profile",   # 👈 agregamos profile para que no moleste
}))

FIELDS_INCLUDE = getattr(settings, "AUDIT_FIELDS_INCLUDE", {})
FIELDS_EXCLUDE = getattr(settings, "AUDIT_FIELDS_EXCLUDE", {})

# ============================================================
# Helpers
# ============================================================

def to_jsonable(value):
    """
    Convierte cualquier valor que pueda venir del snapshot/diff
    a algo que sí pueda ir a un JSONField.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, (FieldFile, ImageFieldFile)):
        return value.name or None
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    return str(value)


def _label_for(instance):
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"


def _should_track(instance):
    label = _label_for(instance)
    if AUDIT_INCLUDE is not None:
    # solo lo que está en include
        return label in AUDIT_INCLUDE
    # todo menos lo excluido
    return label not in AUDIT_EXCLUDE


def _include_fields(instance):
    return FIELDS_INCLUDE.get(_label_for(instance))


def _exclude_fields(instance):
    return FIELDS_EXCLUDE.get(_label_for(instance), ())


def _common_ctx():
    req = get_current_request()
    user = getattr(req, "user", None) if req else None
    return {
        "user": user if (user and user.is_authenticated) else None,
        "ip": getattr(req, "META", {}).get("REMOTE_ADDR") if req else None,
        "path": getattr(req, "path", "") if req else "",
        "method": getattr(req, "method", "") if req else "",
        "user_agent": (req.META.get("HTTP_USER_AGENT") if req else "") or "",
    }

# ============================================================
# pre_save
# ============================================================

@receiver(pre_save, dispatch_uid="audit_pre_save", weak=False)
def audit_pre_save(sender, instance, **kwargs):
    if sender is AuditLog:
        return
    if not _should_track(instance):
        return
    if instance.pk:
        include = _include_fields(instance)
        exclude = _exclude_fields(instance)
        prev = instance.__class__.objects.get(pk=instance.pk)
        instance._audit_before = model_snapshot(prev, include, exclude)
    else:
        instance._audit_before = None

# ============================================================
# post_save
# ============================================================

@receiver(post_save, dispatch_uid="audit_post_save", weak=False)
def audit_post_save(sender, instance, created, **kwargs):
    # Do not audit while running migrations/management commands that touch core tables.
    if any(cmd in sys.argv for cmd in ("migrate", "makemigrations", "collectstatic")):
        return
    if sender is AuditLog:
        return
    if not _should_track(instance):
        return

    include = _include_fields(instance)
    exclude = _exclude_fields(instance)
    after = model_snapshot(instance, include, exclude)
    before = getattr(instance, "_audit_before", None)

    action = "create" if created else "update"
    changes = after if created else diff(before or {}, after)

    if not created and not changes:
        return

    safe_changes = to_jsonable(changes)

    ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)
    ctx = _common_ctx()

    AuditLog.objects.create(
        user=ctx["user"],
        action=action,
        content_type=ct,
        object_id=str(instance.pk),
        object_repr=str(instance),
        changes=safe_changes,
        ip=ctx["ip"],
        path=ctx["path"],
        method=ctx["method"],
        user_agent=ctx["user_agent"],
        tags={"module": instance._meta.app_label},
    )

# ============================================================
# pre_delete
# ============================================================

@receiver(pre_delete, dispatch_uid="audit_pre_delete", weak=False)
def audit_pre_delete(sender, instance, **kwargs):
    if sender is AuditLog:
        return
    if not _should_track(instance):
        return
    include = _include_fields(instance)
    exclude = _exclude_fields(instance)
    before = model_snapshot(instance, include, exclude)
    # 👇 guardamos ya limpio
    instance._audit_before = to_jsonable(before)

# ============================================================
# post_delete
# ============================================================

@receiver(post_delete, dispatch_uid="audit_post_delete", weak=False)
def audit_post_delete(sender, instance, **kwargs):
    if sender is AuditLog:
        return
    if not _should_track(instance):
        return

    ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)
    ctx = _common_ctx()

    # 👇 leer lo que guardamos en pre_delete, pero otra vez limpio por si acaso
    changes = getattr(instance, "_audit_before", None)
    changes = to_jsonable(changes)

    AuditLog.objects.create(
        user=ctx["user"],
        action="soft_delete",  # o "delete"
        content_type=ct,
        object_id=str(instance.pk),
        object_repr=str(instance),
        changes=changes,
        ip=ctx["ip"],
        path=ctx["path"],
        method=ctx["method"],
        user_agent=ctx["user_agent"],
        tags={"module": instance._meta.app_label},
    )
