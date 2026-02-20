from django.contrib import admin
from django.utils.html import format_html
from .models import Plan, Subscription, Invoice, DiscountCampaign, PendingSubscription, WebhookEvent
from .forms import PlanAdminForm

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanAdminForm
    list_display = ['name', 'plan_type', 'price_monthly', 'price_yearly', 'max_inboxes', 'is_active']
    list_editable = ['is_active']
    list_filter = ['plan_type', 'is_active']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'slug', 'plan_type', 'description', 'is_active')
        }),
        ('Precios', {
            'fields': ('price_monthly', 'price_yearly', 'trial_days')
        }),
        ('Límites y Capacidad', {
            'fields': ('max_inboxes', 'max_documents', 'max_users')
        }),
        ('📝 Características Destacadas', {
            'fields': ('summary_features',),
            'description': 'Lista de 3-4 características principales para mostrar en las tarjetas de planes. Formato JSON: ["Feature 1", "Feature 2", "Feature 3"]'
        }),
        ('🤖 Core Features', {
            'fields': (
                'agent_bots',
                'agent_management',
                'auto_resolve_conversations',
                'automations',
                'chatwoot_v4',
            ),
            'classes': ('collapse',),
            'description': 'Funcionalidades principales de Chatwoot.'
        }),
        ('📊 CRM & Business Tools', {
            'fields': (
                'crm',
                'crm_integration',
                'campaigns',
                'canned_responses',
                'macros',
                'reports',
            ),
            'classes': ('collapse',),
            'description': 'Herramientas de CRM y gestión de negocio.'
        }),
        ('🔌 Canales de Comunicación', {
            'fields': (
                'email_channel',
                'website_channel',
                'facebook_channel',
                'instagram_channel',
                'channel_whatsapp',
                'channel_api',
                'channel_telegram',
                'channel_sms',
                'channel_twitter',
                'channel_line',
            ),
            'classes': ('collapse',),
            'description': 'Canales de comunicación disponibles.'
        }),
        ('✉️ Email Features', {
            'fields': (
                'inbound_emails',
                'custom_reply_email',
                'custom_reply_domain',
                'email_continuity_on_api_channel',
                'quoted_email_reply',
            ),
            'classes': ('collapse',),
            'description': 'Funcionalidades relacionadas con email.'
        }),
        ('👥 Team & Collaboration', {
            'fields': (
                'team_management',
                'inbox_management',
                'custom_attributes',
                'labels',
            ),
            'classes': ('collapse',),
            'description': 'Gestión de equipos y colaboración.'
        }),
        ('🔗 Integraciones', {
            'fields': (
                'integrations',
                'linear_integration',
                'notion_integration',
            ),
            'classes': ('collapse',),
            'description': 'Integraciones con herramientas externas.'
        }),
        ('📱 Advanced Features', {
            'fields': (
                'help_center',
                'voice_recorder',
                'whatsapp_campaign',
                'ip_lookup',
            ),
            'classes': ('collapse',),
            'description': 'Características avanzadas adicionales.'
        }),
        ('Integración Wompi', {
            'fields': ('wompi_plan_id',)
        }),
    )

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan', 'status_badge', 'billing_cycle', 'current_period_end']
    list_filter = ['status', 'billing_cycle', 'plan']
    search_fields = ['company__name', 'wompi_subscription_id']
    readonly_fields = ['started_at', 'created_at', 'updated_at']
    actions = ['cancel_subscriptions', 'activate_subscriptions']
    
    def status_badge(self, obj):
        colors = {
            'trial': 'blue',
            'active': 'green',
            'past_due': 'orange',
            'cancelled': 'red',
            'expired': 'gray',
            'pending': 'purple',
        }
        # Usar string simple en lugar de format_html
        return obj.get_status_display()
    status_badge.short_description = 'Estado'
    
    def cancel_subscriptions(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(status='cancelled', cancelled_at=timezone.now())
        self.message_user(request, "{} suscripciones canceladas".format(count))
    cancel_subscriptions.short_description = "Cancelar suscripciones seleccionadas"
    
    def activate_subscriptions(self, request, queryset):
        count = queryset.update(status='active')
        self.message_user(request, "{} suscripciones activadas".format(count))
    activate_subscriptions.short_description = "Activar suscripciones seleccionadas"

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'subscription', 'amount', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'created_at']
    search_fields = ['subscription__company__name', 'wompi_reference']
    readonly_fields = ['created_at']

@admin.register(DiscountCampaign)
class DiscountCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_badge', 'validity_period', 'conditions', 'usage_info', 'is_active']
    list_editable = ['is_active']
    list_filter = ['discount_type', 'is_active', 'apply_to_trial_expired', 'apply_to_new_users']
    search_fields = ['name', 'description']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']
    
    def discount_badge(self, obj):
        if obj.discount_type == 'percentage':
            return "{}%".format(obj.discount_value)
        else:
            return "${}".format(obj.discount_value)
    discount_badge.short_description = 'Descuento'
    
    def validity_period(self, obj):
        if obj.start_date and obj.end_date:
            return "{} - {}".format(
                obj.start_date.strftime('%d/%m/%Y'),
                obj.end_date.strftime('%d/%m/%Y')
            )
        return "Sin fechas definidas"
    validity_period.short_description = 'Período de Vigencia'
    
    def conditions(self, obj):
        conditions = []
        if obj.apply_to_trial_expired:
            conditions.append("Trial expirado")
        if obj.apply_to_new_users:
            conditions.append("Usuarios nuevos")
        if obj.minimum_plan_price:
            conditions.append("Plan min. ${}".format(obj.minimum_plan_price))
        return ", ".join(conditions) if conditions else "Sin condiciones"
    conditions.short_description = 'Condiciones'
    
    def usage_info(self, obj):
        if obj.max_uses:
            percentage = (obj.current_uses / obj.max_uses) * 100
            return "{}/{} ({}%)".format(obj.current_uses, obj.max_uses, int(percentage))
        return "{}/∞".format(obj.current_uses)
    usage_info.short_description = 'Uso'


@admin.register(PendingSubscription)
class PendingSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['company', 'plan', 'billing_cycle', 'amount', 'user_email', 'created_at']
    list_filter = ['billing_cycle', 'plan']
    search_fields = ['company__name', 'user_email', 'wompi_reference']
    readonly_fields = ['created_at']


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'event_id_short',
        'event_type',
        'transaction_id_short',
        'status_badge',
        'subscription_link',
        'invoice_link',
        'received_at',
        'processing_time'
    ]
    list_filter = ['status', 'event_type', 'received_at']
    search_fields = ['event_id', 'transaction_id', 'subscription__id', 'invoice__id']
    readonly_fields = [
        'event_id',
        'event_type',
        'transaction_id',
        'payload',
        'signature',
        'subscription',
        'invoice',
        'received_at',
        'processed_at',
        'ip_address',
        'user_agent'
    ]
    
    fieldsets = (
        ('Identificación', {
            'fields': ('event_id', 'event_type', 'transaction_id')
        }),
        ('Datos del Webhook', {
            'fields': ('payload', 'signature'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('status', 'error_message')
        }),
        ('Referencias', {
            'fields': ('subscription', 'invoice')
        }),
        ('Metadatos', {
            'fields': ('received_at', 'processed_at', 'ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def event_id_short(self, obj):
        """Muestra versión corta del event_id"""
        if obj.event_id:
            return f"{obj.event_id[:20]}..." if len(obj.event_id) > 20 else obj.event_id
        return "-"
    event_id_short.short_description = 'Event ID'
    
    def transaction_id_short(self, obj):
        """Muestra versión corta del transaction_id"""
        if obj.transaction_id:
            return f"{obj.transaction_id[:20]}..." if len(obj.transaction_id) > 20 else obj.transaction_id
        return "-"
    transaction_id_short.short_description = 'Transaction ID'
    
    def status_badge(self, obj):
        """Muestra el estado con colores"""
        colors = {
            'received': '#9CA3AF',      # Gris
            'processing': '#3B82F6',    # Azul
            'processed': '#10B981',     # Verde
            'failed': '#EF4444',        # Rojo
            'duplicate': '#F59E0B',     # Amarillo
            'invalid_signature': '#DC2626'  # Rojo oscuro
        }
        icons = {
            'received': '📥',
            'processing': '⏳',
            'processed': '✅',
            'failed': '❌',
            'duplicate': '🔄',
            'invalid_signature': '🚫'
        }
        color = colors.get(obj.status, '#6B7280')
        icon = icons.get(obj.status, '❓')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def subscription_link(self, obj):
        """Link a la suscripción relacionada"""
        if obj.subscription:
            url = f'/admin/subscriptions/subscription/{obj.subscription.id}/change/'
            return format_html(
                '<a href="{}" target="_blank">Suscripción #{}</a>',
                url,
                obj.subscription.id
            )
        return "-"
    subscription_link.short_description = 'Suscripción'
    
    def invoice_link(self, obj):
        """Link a la factura relacionada"""
        if obj.invoice:
            url = f'/admin/subscriptions/invoice/{obj.invoice.id}/change/'
            return format_html(
                '<a href="{}" target="_blank">Factura #{}</a>',
                url,
                obj.invoice.id
            )
        return "-"
    invoice_link.short_description = 'Factura'
    
    def processing_time(self, obj):
        """Calcula el tiempo de procesamiento"""
        if obj.processed_at and obj.received_at:
            delta = obj.processed_at - obj.received_at
            seconds = delta.total_seconds()
            if seconds < 1:
                return f"{int(seconds * 1000)}ms"
            elif seconds < 60:
                return f"{seconds:.1f}s"
            else:
                minutes = int(seconds / 60)
                remaining_seconds = int(seconds % 60)
                return f"{minutes}m {remaining_seconds}s"
        return "-"
    processing_time.short_description = 'Tiempo proc.'
    
    def has_add_permission(self, request):
        """No permitir crear webhooks manualmente"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Permitir eliminar solo si hay más de 1000 registros"""
        if WebhookEvent.objects.count() > 1000:
            return True
        return False