from django.views.generic import ListView
from django.db.models import Q
from django.utils.dateparse import parse_datetime, parse_date
from .models import AuditLog

class AuditListView(ListView):
    model = AuditLog
    template_name = "audit/list.html"
    context_object_name = "logs"
    paginate_by = 25

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user").all()
        q = (self.request.GET.get("q") or "").strip()
        action = (self.request.GET.get("action") or "").strip()
        model = (self.request.GET.get("model") or "").strip()
        dfrom = self.request.GET.get("from")
        dto = self.request.GET.get("to")

        if q:
            qs = qs.filter(
                Q(object_repr__icontains=q) |
                Q(user__username__icontains=q) |
                Q(path__icontains=q) |
                Q(tags__icontains=q)
            )
        if action:
            qs = qs.filter(action=action)
        if model:
            qs = qs.filter(content_type__model__iexact=model)

        # rango de fechas
        if dfrom:
            try:
                qs = qs.filter(created_at__gte=parse_datetime(dfrom) or parse_date(dfrom))
            except Exception:
                pass
        if dto:
            try:
                qs = qs.filter(created_at__lte=parse_datetime(dto) or parse_date(dto))
            except Exception:
                pass

        return qs.order_by("-created_at")