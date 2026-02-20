from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from accounts.models import Company

class DiscountCampaign(models.Model):
    DISCOUNT_TYPES = (
        ('percentage', 'Porcentaje'),
        ('fixed', 'Monto Fijo'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=5, decimal_places=2, help_text="Para porcentaje: 20.00 = 20%, Para fijo: monto en COP")
    
    # Condiciones
    apply_to_trial_expired = models.BooleanField(default=False, help_text="Aplicar cuando el trial haya expirado")
    apply_to_new_users = models.BooleanField(default=False, help_text="Aplicar a usuarios nuevos")
    minimum_plan_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio mínimo del plan para aplicar descuento")
    
    # Vigencia
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    max_uses = models.IntegerField(null=True, blank=True, help_text="Máximo número de usos (opcional)")
    current_uses = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def is_valid(self):
        """Verifica si el descuento está activo y dentro del período de vigencia"""
        now = timezone.now()
        return (self.is_active and 
                self.start_date <= now <= self.end_date and
                (self.max_uses is None or self.current_uses < self.max_uses))
    
    def can_apply_to_user(self, company, trial=None):
        """Verifica si el descuento se puede aplicar a un usuario específico"""
        if not self.is_valid():
            return False
            
        # Verificar condición de trial expirado
        if self.apply_to_trial_expired:
            if not trial or trial.is_active:
                return False
                
        # Verificar condición de usuario nuevo (sin suscripciones previas)
        if self.apply_to_new_users:
            if hasattr(company, 'subscription'):
                return False
                
        return True
    
    def calculate_discount(self, original_price):
        """Calcula el monto del descuento"""
        if self.discount_type == 'percentage':
            return original_price * (self.discount_value / 100)
        else:  # fixed
            return min(self.discount_value, original_price)  # No puede ser mayor al precio original
    
    def __str__(self):
        if self.discount_type == 'percentage':
            return f"{self.name} - {self.discount_value}%"
        else:
            return f"{self.name} - ${self.discount_value}"

class Plan(models.Model):
    PLAN_TYPES = (
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    )
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField(blank=True)
    
    # Precios
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Límites
    max_inboxes = models.IntegerField(default=1)
    max_documents = models.IntegerField(default=10)
    max_users = models.IntegerField(default=3, help_text="Número máximo de usuarios/agentes permitidos")
    
    # Features (JSON)
    features = models.JSONField(default=dict, blank=True, help_text="Todas las características técnicas del plan (enviadas a Chatwoot API)")
    summary_features = models.JSONField(
        default=list, 
        blank=True,
        help_text="3-4 características destacadas para mostrar en tarjetas de planes. Formato: ['Feature 1', 'Feature 2', 'Feature 3']"
    )
    
    # Control
    is_active = models.BooleanField(default=True)
    trial_days = models.IntegerField(default=7)
    
    # Wompi
    wompi_plan_id = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['price_monthly']
    
    def __str__(self):
        return f"{self.name} - ${self.price_monthly}/mes"

class Subscription(models.Model):
    STATUS_CHOICES = (
        ('trial', 'Trial'),
        ('active', 'Activa'),
        ('pending', 'Pago Pendiente'),
        ('suspended', 'Suspendida'),
        ('past_due', 'Pago Vencido'),
        ('cancelled', 'Cancelada'),
        ('expired', 'Expirada'),
    )
    
    BILLING_CYCLES = (
        ('monthly', 'Mensual'),
        ('yearly', 'Anual'),
    )
    
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLES, default='monthly')
    
    # Fechas
    started_at = models.DateTimeField(auto_now_add=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Wompi
    wompi_subscription_id = models.CharField(max_length=255, blank=True)
    wompi_customer_email = models.EmailField(blank=True)
    wompi_payment_method_id = models.CharField(max_length=255, blank=True)
    payment_source_id = models.CharField(max_length=255, blank=True, help_text="ID de la fuente de pago para cobros automáticos")
    
    # Información de la tarjeta guardada (para mostrar al usuario)
    card_brand = models.CharField(max_length=50, blank=True, help_text="Marca de la tarjeta (VISA, MASTERCARD, etc)")
    card_last_four = models.CharField(max_length=4, blank=True, help_text="Últimos 4 dígitos de la tarjeta")
    card_exp_month = models.CharField(max_length=2, blank=True, help_text="Mes de expiración")
    card_exp_year = models.CharField(max_length=2, blank=True, help_text="Año de expiración")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.company.name} - {self.plan.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.pk:
            # Nueva suscripción
            if self.plan.trial_days > 0:
                self.trial_ends_at = timezone.now() + relativedelta(days=self.plan.trial_days)
            
            # Calcular período
            if self.billing_cycle == 'monthly':
                self.current_period_end = timezone.now() + relativedelta(months=1)
            else:
                self.current_period_end = timezone.now() + relativedelta(years=1)
        
        super().save(*args, **kwargs)

class Invoice(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('paid', 'Pagada'),
        ('failed', 'Fallida'),
        ('voided', 'Anulada'),
    )
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Wompi
    wompi_transaction_id = models.CharField(max_length=255, blank=True, unique=True)
    wompi_reference = models.CharField(max_length=255, blank=True)
    invoice_pdf_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Factura {self.id} - {self.subscription.company.name}"


class PendingSubscription(models.Model):
    """Modelo temporal para guardar información de suscripciones pendientes de pago"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    plan = models.ForeignKey('Plan', on_delete=models.CASCADE)
    user_email = models.EmailField()
    billing_cycle = models.CharField(max_length=10, choices=[('monthly', 'Mensual'), ('yearly', 'Anual')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_campaign = models.ForeignKey(DiscountCampaign, null=True, blank=True, on_delete=models.SET_NULL)
    wompi_reference = models.CharField(max_length=255, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Pending: {self.company.name} - {self.plan.name}"


class WebhookEvent(models.Model):
    """
    Modelo para registrar todos los webhooks recibidos de Wompi
    Garantiza idempotencia y permite auditoría
    """
    STATUS_CHOICES = (
        ('received', 'Recibido'),
        ('processing', 'Procesando'),
        ('processed', 'Procesado'),
        ('failed', 'Fallido'),
        ('duplicate', 'Duplicado'),
        ('invalid_signature', 'Firma Inválida'),
    )
    
    # Identificación del webhook
    event_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="ID único del evento de Wompi")
    event_type = models.CharField(max_length=50, help_text="Tipo de evento (ej: transaction.updated)")
    transaction_id = models.CharField(max_length=255, db_index=True, help_text="ID de la transacción en Wompi")
    
    # Datos completos del webhook
    payload = models.JSONField(help_text="Payload completo del webhook")
    signature = models.CharField(max_length=255, blank=True, help_text="Firma X-Event-Checksum recibida")
    
    # Estado del procesamiento
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    error_message = models.TextField(blank=True, help_text="Mensaje de error si falló el procesamiento")
    
    # Relación con objetos creados/actualizados
    subscription = models.ForeignKey(
        'Subscription', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='webhook_events',
        help_text="Suscripción afectada por este webhook"
    )
    invoice = models.ForeignKey(
        'Invoice', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='webhook_events',
        help_text="Factura creada/actualizada por este webhook"
    )
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True, help_text="Cuándo se recibió el webhook")
    processed_at = models.DateTimeField(null=True, blank=True, help_text="Cuándo se terminó de procesar")
    
    # Metadatos
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP desde donde se recibió el webhook")
    user_agent = models.CharField(max_length=500, blank=True, help_text="User-Agent del webhook")
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-received_at']),
        ]
    
    def __str__(self):
        return f"Webhook {self.event_id} - {self.event_type} - {self.status}"
    
    def mark_as_processing(self):
        """Marca el webhook como en procesamiento"""
        self.status = 'processing'
        self.save(update_fields=['status'])
    
    def mark_as_processed(self, subscription=None, invoice=None):
        """Marca el webhook como procesado exitosamente"""
        self.status = 'processed'
        self.processed_at = timezone.now()
        if subscription:
            self.subscription = subscription
        if invoice:
            self.invoice = invoice
        self.save(update_fields=['status', 'processed_at', 'subscription', 'invoice'])
    
    def mark_as_failed(self, error_message):
        """Marca el webhook como fallido"""
        self.status = 'failed'
        self.error_message = error_message
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'processed_at'])
    
    def mark_as_duplicate(self):
        """Marca el webhook como duplicado"""
        self.status = 'duplicate'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])
    
    def mark_as_invalid_signature(self):
        """Marca el webhook como con firma inválida"""
        self.status = 'invalid_signature'
        self.processed_at = timezone.now()
        self.error_message = "Firma X-Event-Checksum inválida"
        self.save(update_fields=['status', 'processed_at', 'error_message'])