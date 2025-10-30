# audit/views.py
from django.views.generic import ListView
from django.db.models import Q
from .models import AuditLog

class AuditLogListView(ListView):
    model = AuditLog
    template_name = "audit/list.html"
    context_object_name = "logs"
    paginate_by = 25

    def get_queryset(self):
        qs = (AuditLog.objects
              .select_related("user", "content_type")
              .only("id","created_at","user__username","action","content_type__app_label","content_type__model",
                    "object_id","object_repr","changes","ip","path","method","user_agent"))
        q = (self.request.GET.get("q") or "").strip()
        action = (self.request.GET.get("action") or "").strip()
        model = (self.request.GET.get("model") or "").strip()
        date_from = (self.request.GET.get("date_from") or "").strip()
        date_to = (self.request.GET.get("date_to") or "").strip()

        if q:
            qs = qs.filter(
                Q(user__username__icontains=q) |
                Q(object_repr__icontains=q) |
                Q(path__icontains=q) |
                Q(tags__icontains=q)
            )
        if action:
            qs = qs.filter(action=action)
        if model:
            qs = qs.filter(content_type__model__icontains=model)

        # Si usas formato dd/mm/aaaa, conviértelo aquí o usa widgets en el form
        # (omitido por brevedad)

        return qs.order_by("-created_at")
