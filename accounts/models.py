from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta

class Company(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    
    # Admin contact info (temporal, until user is created)
    admin_first_name = models.CharField(max_length=150, blank=True)
    admin_last_name = models.CharField(max_length=150, blank=True)
    admin_temp_password = models.CharField(max_length=255, blank=True)  # Temporal para N8N
    
    # Chatwoot integration
    chatwoot_account_id = models.IntegerField(null=True, blank=True)
    chatwoot_access_token = models.TextField(blank=True)  # Token de acceso de Chatwoot para APIs
    
    # Trial management
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Cal.com integration
    calendar_provider = models.CharField(max_length=50, default='calcom', blank=True)
    calendar_api_key = models.TextField(blank=True)  # API key de Cal.com
    calendar_event_id = models.CharField(max_length=50, blank=True)  # Event ID numérico de Cal.com
    calendar_username = models.CharField(max_length=255, blank=True)  # Username extraído de la URL
    calendar_event_slug = models.CharField(max_length=255, blank=True)  # Slug del evento extraído de la URL
    calendar_booking_url = models.TextField(blank=True)  # URL completa de agendamiento
    
    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

class User(AbstractUser):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    chatwoot_user_id = models.IntegerField(null=True, blank=True)
    email = models.EmailField(unique=True)
    
    # Usar email como username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.email

class Trial(models.Model):
    """Modelo para manejar períodos de prueba gratuita"""
    TRIAL_STATUS_CHOICES = [
        ('active', 'Activo'),
        ('expired', 'Expirado'),
        ('converted', 'Convertido a pago'),
        ('cancelled', 'Cancelado'),
    ]
    
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='trial')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=TRIAL_STATUS_CHOICES, default='active')
    
    # Límites del trial
    max_messages = models.IntegerField(default=1000)  # Mensajes máximos por mes
    max_conversations = models.IntegerField(default=100)  # Conversaciones máximas por mes
    max_documents = models.IntegerField(default=10)  # Documentos máximos para entrenamiento
    
    # Contadores actuales
    current_messages = models.IntegerField(default=0)
    current_conversations = models.IntegerField(default=0)
    current_documents = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Asociar opcionalmente a un Plan (no obligatorio para evitar romper lógica existente)
    try:
        # Import localmente para evitar circular imports al cargar models
        from subscriptions.models import Plan as _Plan
    except Exception:
        _Plan = None
    plan = models.ForeignKey(
        'subscriptions.Plan' if _Plan is None else _Plan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Plan asociado cuando el trial está ligado a un plan concreto'
    )
    
    def save(self, *args, **kwargs):
        if not self.end_date:
            # Trial de 14 días por defecto
            self.end_date = timezone.now() + timedelta(days=14)
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        return (
            self.status == 'active' and 
            timezone.now() < self.end_date and
            self.current_messages < self.max_messages and
            self.current_conversations < self.max_conversations
        )
    
    @property
    def days_remaining(self):
        if self.end_date > timezone.now():
            return (self.end_date - timezone.now()).days
        return 0
    
    def __str__(self):
        plan_part = f" - Plan: {self.plan.name}" if getattr(self, 'plan', None) else ''
        return f"Trial {self.company.name} - {self.status}{plan_part}"


class ActivationToken(models.Model):
    """Modelo para tokens de activación de cuenta vía email"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('used', 'Used'), 
        ('expired', 'Expired'),
    ]
    
    email = models.EmailField(unique=True)
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'accounts_activation_tokens'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Token expira en 24 horas
            self.expires_at = timezone.now() + timedelta(hours=24)
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    @property
    def is_valid(self):
        return (
            self.status == 'pending' and 
            timezone.now() < self.expires_at
        )
    
    def mark_as_used(self):
        self.status = 'used'
        self.used_at = timezone.now()
        self.save()
    
    def mark_as_expired(self):
        self.status = 'expired'
        self.save()
    
    @classmethod
    def create_for_email(cls, email):
        """Crea o actualiza un token para el email dado"""
        # Marcar tokens existentes como expirados
        cls.objects.filter(email=email, status='pending').update(status='expired')
        
        # Crear nuevo token
        return cls.objects.create(email=email)
    
    def __str__(self):
        return f"ActivationToken for {self.email} - {self.status}"


class BillingInfo(models.Model):
    """Información de facturación asociada a una Company."""
    ID_TYPE_CHOICES = [
        ('NIT', 'NIT'),
        ('CC', 'Cédula de Ciudadanía'),
        ('PP', 'Pasaporte'),
        ('CE', 'Cédula de Extranjería'),
        ('NUIP', 'NUIP'),
    ]

    KIND_OF_PERSON_CHOICES = [
        ('LEGAL_ENTITY', 'Persona Juridica'),
        ('PERSON_ENTITY', 'Persona Natural'),
        ('OTHER_ENTITY', 'Otra'),
    ]

    REGIME_CHOICES = [
        ('COMMON_REGIME', 'Responsable de IVA'),
        ('SIMPLIFIED_REGIME', 'No responsable de IVA'),
        ('NATIONAL_CONSUMPTION_TAX', 'Impuesto Nacional al Consumo - INC'),
        ('NOT_REPONSIBLE_FOR_CONSUMPTION', 'No responsable de INC'),
        ('INC_IVA_RESPONSIBLE', 'Responsable de IVA e INC'),
        ('SPECIAL_REGIME', 'Régimen especial'),
    ]

    company = models.OneToOneField('Company', on_delete=models.CASCADE, related_name='billing_info')
    name = models.CharField(max_length=150, blank=True)
    id_type = models.CharField(max_length=10, choices=ID_TYPE_CHOICES)
    id_number = models.CharField(max_length=64)
    id_dv = models.CharField(max_length=8, blank=True, null=True)
    kind_of_person = models.CharField(max_length=20, choices=KIND_OF_PERSON_CHOICES, default='PERSON_ENTITY')
    regime = models.CharField(max_length=50, choices=REGIME_CHOICES, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BillingInfo for {self.company.name}"