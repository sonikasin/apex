from django.contrib import admin
from .models import PropPlan, PlanStage, PaymentGatewaySetting

@admin.register(PropPlan)
class PropPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_size', 'price', 'leverage')
    list_filter = ('name', 'account_size')
    search_fields = ('name', 'account_size')

@admin.register(PlanStage)
class PlanStageAdmin(admin.ModelAdmin):
    list_display = ('plan', 'stage_type', 'profit_target', 'max_loss_percent')
    list_filter = ('stage_type', 'plan__name')
    search_fields = ('plan__name', 'stage_type')


@admin.register(PaymentGatewaySetting)
class PaymentGatewaySettingAdmin(admin.ModelAdmin):
    list_display = ('active_rial_gateway', 'updated_at')

    def has_add_permission(self, request):
        # تنها یک رکورد singleton مجاز است
        return not PaymentGatewaySetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False