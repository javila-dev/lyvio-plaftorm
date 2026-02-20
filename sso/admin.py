from django.contrib import admin
from django.utils.html import format_html
from .models import SSOToken


@admin.register(SSOToken)
class SSOTokenAdmin(admin.ModelAdmin):
    """
    Admin interface para gestionar tokens SSO.
    """
    list_display = [
        'token_preview',
        'email',
        'chatwoot_account_id',
        'used',
        'is_expired',
        'created_at',
        'expires_at',
        'used_at'
    ]
    list_filter = [
        'used',
        'created_at',
        'expires_at'
    ]
    search_fields = [
        'email',
        'token',
        'request_id',
        'chatwoot_account_id',
        'chatwoot_user_id'
    ]
    readonly_fields = [
        'token',
        'email',
        'chatwoot_account_id',
        'chatwoot_user_id',
        'request_id',
        'created_at',
        'expires_at',
        'used',
        'used_at'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def token_preview(self, obj):
        """Muestra preview del token (primeros 16 caracteres)"""
        return f"{obj.token[:16]}..."
    token_preview.short_description = 'Token'
    
    def is_expired(self, obj):
        """Indica visualmente si el token está expirado"""
        from django.utils import timezone
        if timezone.now() > obj.expires_at:
            return format_html('<span style="color: red;">✗ Expirado</span>')
        return format_html('<span style="color: green;">✓ Válido</span>')
    is_expired.short_description = 'Estado'
    
    def has_add_permission(self, request):
        """No permitir crear tokens desde admin (solo vía API)"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Permitir eliminar tokens solo a superusers"""
        return request.user.is_superuser
