# audit/utils.py
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog

SENSITIVE = {"password", "token", "secret", "api_key", "authorization"}

def _mask(v):
    if v is None:
        return None
    s = str(v)
    return "*****" if s else s

def dict_diff(before: dict, after: dict):
    if before is None and after is None:
        return None
    before = before or {}
    after = after or {}
    out = {}
    for k in set(before) | set(after):
        b, a = before.get(k), after.get(k)
        if k in SENSITIVE:
            if b != a:
                out[k] = [_mask(b), _mask(a)]
        else:
            if b != a:
                out[k] = [b, a]
    return out or None

def model_to_dict(instance, include=None, exclude=None):
    if instance is None:
        return {}
    data = {}
    for f in instance._meta.fields:
        name = f.name
        if exclude and name in exclude:
            continue
        if include and name not in include:
            continue
        data[name] = getattr(instance, name, None)
    return data

def log_action(request=None, *, action: str, obj=None,
               before: dict|None=None, after: dict|None=None,
               include=None, exclude=None, changes: dict|None=None,
               tags: dict|None=None, object_repr: str|None=None):
    """
    Uso mínimo:
        log_action(request, action="export", changes={"count": 120})
        log_action(request, action="update", obj=operador, before=..., after=...)
    """
    ct = None
    object_id = None
    if obj is not None:
        ct = ContentType.objects.get_for_model(obj.__class__)
        object_id = str(obj.pk)
        if after is None:
            after = model_to_dict(obj, include=include, exclude=exclude)
        if object_repr is None:
            object_repr = str(obj)

    if changes is None:
        changes = dict_diff(before, after)

    return AuditLog.objects.create(
        user=getattr(request, "user", None) if request else None,
        action=action,
        content_type=ct,
        object_id=object_id,
        object_repr=object_repr or "",
        changes=changes,
        ip=(request.META.get("REMOTE_ADDR") if request else None),
        path=(request.path if request else ""),
        method=(request.method if request else ""),
        user_agent=(request.META.get("HTTP_USER_AGENT") if request else ""),
        tags=tags or {},
    )
