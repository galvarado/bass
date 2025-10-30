# audit/signals.py
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from .middleware import get_current_request
from .models import AuditLog  # tu modelo
from .utils import model_snapshot, diff

# Configuración (elige una estrategia)
AUDIT_INCLUDE = getattr(settings, "AUDIT_INCLUDE", None)  # p.ej. {"operators.Operator", "orders.Order"}
AUDIT_EXCLUDE = set(getattr(settings, "AUDIT_EXCLUDE", {
    "audit.AuditLog", "contenttypes.ContentType", "sessions.Session",
}))

FIELDS_INCLUDE = getattr(settings, "AUDIT_FIELDS_INCLUDE", {})  # {"operators.Operator": ["first_name", ...]}
FIELDS_EXCLUDE = getattr(settings, "AUDIT_FIELDS_EXCLUDE", {})  # {"app.Model": ["big_blob", ...]}

def _label_for(instance):
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"

def _should_track(instance):
    label = _label_for(instance)
    if AUDIT_INCLUDE is not None:
        return label in AUDIT_INCLUDE
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

@receiver(pre_save, dispatch_uid="audit_pre_save", weak=False)
def audit_pre_save(sender, instance, **kwargs):
    if sender is AuditLog:  # nunca te audites a ti mismo
        return
    if not _should_track(instance):
        return
    if instance.pk:
        include = _include_fields(instance)
        exclude = _exclude_fields(instance)
        instance._audit_before = model_snapshot(instance.__class__.objects.get(pk=instance.pk), include, exclude)
    else:
        instance._audit_before = None

@receiver(post_save, dispatch_uid="audit_post_save", weak=False)
def audit_post_save(sender, instance, created, **kwargs):
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

    # Si no hubo cambios “materiales”, no registres
    if not created and not changes:
        return

    ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)
    ctx = _common_ctx()

    AuditLog.objects.create(
        user=ctx["user"],
        action=action,
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

@receiver(pre_delete, dispatch_uid="audit_pre_delete", weak=False)
def audit_pre_delete(sender, instance, **kwargs):
    if sender is AuditLog:
        return
    if not _should_track(instance):
        return
    include = _include_fields(instance)
    exclude = _exclude_fields(instance)
    instance._audit_before = model_snapshot(instance, include, exclude)

@receiver(post_delete, dispatch_uid="audit_post_delete", weak=False)
def audit_post_delete(sender, instance, **kwargs):
    if sender is AuditLog:
        return
    if not _should_track(instance):
        return
    ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)
    ctx = _common_ctx()
    AuditLog.objects.create(
        user=ctx["user"],
        action="soft_delete",  # o "delete" si es borrado real
        content_type=ct,
        object_id=str(instance.pk),
        object_repr=str(instance),
        changes=getattr(instance, "_audit_before", None),
        ip=ctx["ip"],
        path=ctx["path"],
        method=ctx["method"],
        user_agent=ctx["user_agent"],
        tags={"module": instance._meta.app_label},
    )
