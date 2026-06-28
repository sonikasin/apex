from django.contrib import admin
from .models import PropPlan, PlanStage

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