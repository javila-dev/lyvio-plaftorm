from django.db import models
from accounts.models import Company

class BotType(models.Model):
    """Tipos de bot predefinidos con system prompts específicos"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    system_prompt = models.TextField(
        help_text="Prompt base del sistema para este tipo de bot"
    )
    icon = models.CharField(max_length=50, blank=True, help_text="Nombre del ícono FontAwesome")
    suggested_tone = models.CharField(max_length=255, blank=True, help_text="Tono sugerido")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Orden de aparición")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        
    def __str__(self):
        return self.name

class BotConfig(models.Model):
    LANGUAGE_CHOICES = (
        ('es-CO', 'Español Colombia'),
        ('es-MX', 'Español México'),
        ('es-ES', 'Español España'),
        ('en-US', 'English (US)'),
    )
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bots')
    inbox_id = models.IntegerField(unique=True)
    bot_type = models.ForeignKey(BotType, on_delete=models.PROTECT, related_name='bot_configs', null=True, blank=True)
    
    # Configuración del bot
    name = models.CharField(max_length=200, blank=True, help_text="Nombre personalizado del bot")
    system_prompt = models.TextField(blank=True, help_text="Prompt del sistema para este bot específico")
    specialty = models.TextField(blank=True, help_text="A qué se dedica la empresa")
    tone = models.CharField(max_length=255, blank=True, help_text="Tono de comunicación del bot")
    company_context = models.TextField(blank=True, help_text="Contexto detallado de la empresa")
    industry_sector = models.CharField(max_length=200, blank=True, help_text="Sector industrial de la empresa")
    services = models.JSONField(default=list, help_text="Lista de servicios")
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='es-CO')
    additional_context = models.TextField(blank=True, help_text="Contexto adicional")
    
    # Calendly integration
    calendly_usage_description = models.TextField(blank=True, help_text="Descripción de cuándo el bot debe usar Calendly para agendar")
    
    # Control
    is_active = models.BooleanField(default=True)
    onboarding_completed = models.BooleanField(default=False, help_text="Indica si el onboarding se completó exitosamente")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        if self.name:
            return f"{self.name} ({self.company.name})"
        return f"Bot {self.inbox_id} - {self.company.name}"
    
    def get_compiled_system_prompt(self):
        """
        Genera el system prompt final reemplazando las variables con la información del bot
        
        Variables disponibles (español e inglés):
        - {{nombre_bot}} / {{bot_name}}: Nombre personalizado del bot
        - {{nombre_empresa}} / {{company_name}}: Nombre de la empresa
        - {{sector_empresa}} / {{industry}}: Sector industrial
        - {{contexto_empresa}} / {{business_context}}: Contexto detallado de la empresa
        - {{tono}} / {{tone}}: Tono de comunicación deseado
        - {{especialidad}} / {{specialty}}: Especialidad del negocio
        - {{contexto_adicional}} / {{contact_info}} / {{special_cases}}: Información adicional
        
        Returns:
            str: System prompt con todas las variables reemplazadas
        """
        # Usar el system_prompt del BotType si existe, sino el del BotConfig
        base_prompt = ""
        if self.bot_type and self.bot_type.system_prompt:
            base_prompt = self.bot_type.system_prompt
        elif self.system_prompt:
            base_prompt = self.system_prompt
        else:
            # Prompt por defecto si no hay ninguno configurado
            base_prompt = """Eres {{nombre_bot}}, un asistente virtual de {{nombre_empresa}}. 
Tu objetivo es ayudar a los clientes de manera profesional y eficiente.
Tono: {{tono}}"""
        
        # Diccionario de variables a reemplazar (incluye variantes en español e inglés)
        bot_name = self.name or 'un asistente virtual'
        company_name = self.company.name or 'nuestra empresa'
        industry = self.industry_sector or 'nuestro sector'
        business_context = self.company_context or 'Información no disponible'
        tone = self.tone or 'profesional y amigable'
        specialty = self.specialty or 'servicios generales'
        additional_context = self.additional_context or ''
        
        variables = {
            # Variables en español
            '{{nombre_bot}}': bot_name,
            '{{nombre_empresa}}': company_name,
            '{{sector_empresa}}': industry,
            '{{contexto_empresa}}': business_context,
            '{{tono}}': tone,
            '{{especialidad}}': specialty,
            '{{contexto_adicional}}': additional_context,
            
            # Variables en inglés (para compatibilidad)
            '{{bot_name}}': bot_name,
            '{{company_name}}': company_name,
            '{{industry}}': industry,
            '{{business_context}}': business_context,
            '{{tone}}': tone,
            '{{specialty}}': specialty,
            '{{contact_info}}': additional_context,
            '{{special_cases}}': additional_context,
        }
        
        # Reemplazar todas las variables en el prompt
        compiled_prompt = base_prompt
        for variable, value in variables.items():
            compiled_prompt = compiled_prompt.replace(variable, value)
        
        return compiled_prompt

class Document(models.Model):
    # Límites y validaciones
    MAX_FILE_SIZE_KB = 80  # 80 KB por archivo
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_KB * 1024  # 81920 bytes
    # MAX_DOCUMENTS_PER_BOT se obtiene del plan de suscripción
    ALLOWED_FILE_TYPES = ['.txt', '.md']  # Solo archivos de texto plano y markdown
    
    bot_config = models.ForeignKey(BotConfig, on_delete=models.CASCADE, related_name='documents')
    filename = models.CharField(max_length=500)
    file_type = models.CharField(max_length=10, blank=True, default='', help_text="Extensión del archivo")
    minio_path = models.CharField(max_length=1000)
    file_size_bytes = models.BigIntegerField(default=0)
    chunks_created = models.IntegerField(default=0)
    processing_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ], default='pending')
    error_message = models.TextField(blank=True, help_text="Mensaje de error si falla el procesamiento")
    metadata = models.JSONField(default=dict, blank=True, help_text='Metadatos del documento (páginas, tokens, etc.)')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.filename} - {self.bot_config.company.name}"
    
    @property
    def file_size_kb(self):
        """Retorna el tamaño del archivo en KB"""
        return round(self.file_size_bytes / 1024, 2)
    
    @property
    def file_size_mb(self):
        """Retorna el tamaño del archivo en MB"""
        return round(self.file_size_bytes / (1024 * 1024), 2)
    
    @classmethod
    def get_max_documents_for_company(cls, company):
        """
        Obtiene el límite máximo de documentos según el plan de suscripción de la empresa
        
        Returns:
            int: Número máximo de documentos permitidos
        """
        # Verificar si la empresa tiene suscripción activa
        if hasattr(company, 'subscription') and company.subscription.plan:
            return company.subscription.plan.max_documents
        
        # Si está en trial, obtener el límite del plan trial
        if hasattr(company, 'trial') and getattr(company.trial, 'is_active', False):
            # Durante el trial, usar el límite del plan que probará
            trial = company.trial
            trial_plan = getattr(trial, 'plan', None)
            if trial_plan:
                return trial_plan.max_documents
        
        # Por defecto, si no tiene plan, límite mínimo
        return 5  # Límite por defecto muy restrictivo