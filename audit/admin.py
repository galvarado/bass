# audit/admin.py
from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at","user","action","content_type","object_id","object_repr")
    list_filter = ("action","content_type","created_at")
    search_fields = ("object_repr","path","user__username","user__email")
    readonly_fields = ("created_at","user","action","content_type","object_id","object_repr",
                       "changes","ip","path","method","user_agent","tags")
