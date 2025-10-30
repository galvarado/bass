# audit/utils.py
from django.forms.models import model_to_dict as _m2d

DEFAULT_EXCLUDE = {"password", "last_login", "date_joined"}

def model_snapshot(instance, include=None, exclude=None):
    if include:
        data = {k: getattr(instance, k, None) for k in include}
    else:
        data = _m2d(instance)
    exclude = set(exclude or ()) | DEFAULT_EXCLUDE
    for k in exclude:
        data.pop(k, None)
    return data

def diff(before, after):
    changes = {}
    keys = set(before.keys()) | set(after.keys())
    for k in keys:
        if before.get(k) != after.get(k):
            changes[k] = {"before": before.get(k), "after": after.get(k)}
    return changes
