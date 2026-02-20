from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Company, Trial, ActivationToken

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'company', 'is_staff', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'company__name']
    list_filter = ['is_staff', 'company', 'date_joined']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Company Info', {'fields': ('company', 'phone', 'chatwoot_user_id')}),
    )

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'is_active', 'chatwoot_account_id', 'created_at']
    search_fields = ['name', 'email']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Trial)
class TrialAdmin(admin.ModelAdmin):
    list_display = ['company', 'status', 'start_date', 'end_date', 'days_remaining_display', 'usage_summary']
    search_fields = ['company__name', 'company__email']
    list_filter = ['status', 'start_date', 'end_date']
    readonly_fields = ['created_at', 'updated_at', 'days_remaining_display']
    
    def days_remaining_display(self, obj):
        return f"{obj.days_remaining} días"
    days_remaining_display.short_description = "Días restantes"
    
    def usage_summary(self, obj):
        return f"{obj.current_messages}/{obj.max_messages} msgs, {obj.current_conversations}/{obj.max_conversations} convs"
    usage_summary.short_description = "Uso actual"


@admin.register(ActivationToken)
class ActivationTokenAdmin(admin.ModelAdmin):
    list_display = ['email', 'status', 'created_at', 'expires_at', 'used_at', 'is_valid_display']
    search_fields = ['email']
    list_filter = ['status', 'created_at', 'expires_at']
    readonly_fields = ['token', 'created_at', 'used_at', 'is_valid_display']
    
    def is_valid_display(self, obj):
        return obj.is_valid
    is_valid_display.short_description = "Válido"
    is_valid_display.boolean = True