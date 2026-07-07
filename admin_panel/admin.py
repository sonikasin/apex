from django.contrib import admin
from .models import AdminActionLog


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user_email', 'category', 'action_description',
                    'method', 'path', 'status_code', 'ip_address')
    list_filter = ('category', 'method', 'is_superuser', 'created_at')
    search_fields = ('user_email', 'path', 'action_description', 'post_data', 'ip_address', 'object_id')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in AdminActionLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
