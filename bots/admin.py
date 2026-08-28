from django.contrib import admin
from .models import BotType, BotConfig, Document

@admin.register(BotType)
class BotTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'suggested_tone', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description', 'system_prompt']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['order', 'name']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'icon', 'is_active', 'order')
        }),
        ('Configuración del Bot', {
            'fields': ('system_prompt', 'suggested_tone'),
            'description': 'Define el comportamiento y características del bot'
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    # Acción para duplicar un tipo de bot
    actions = ['duplicate_bot_type']
    
    def duplicate_bot_type(self, request, queryset):
        for bot_type in queryset:
            bot_type.pk = None
            bot_type.name = f"{bot_type.name} (Copia)"
            bot_type.is_active = False  # Por seguridad, dejar inactivo
            bot_type.save()
        
        self.message_user(request, f"{queryset.count()} tipo(s) de bot duplicado(s) exitosamente")
    duplicate_bot_type.short_description = "Duplicar tipo(s) de bot seleccionado(s)"

@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'inbox_id', 'bot_type', 'tone', 'language', 'is_active', 'onboarding_completed', 'created_at']
    list_filter = ['bot_type', 'language', 'is_active', 'onboarding_completed', 'created_at']
    search_fields = ['name', 'company__name', 'inbox_id', 'tone', 'industry_sector']
    readonly_fields = ['created_at', 'updated_at', 'inbox_id']
    
    fieldsets = (
        ('Empresa e Inbox', {
            'fields': ('company', 'inbox_id', 'bot_type', 'name')
        }),
        ('Configuración del Bot', {
            'fields': ('tone', 'industry_sector', 'language', 'specialty')
        }),
        ('Contexto', {
            'fields': ('company_context', 'system_prompt', 'additional_context'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('is_active', 'onboarding_completed', 'created_at', 'updated_at')
        })
    )
    
    # Acción para marcar onboarding como completado
    actions = ['mark_onboarding_completed', 'mark_onboarding_pending']
    
    def mark_onboarding_completed(self, request, queryset):
        updated = queryset.update(onboarding_completed=True)
        self.message_user(request, f"{updated} bot(s) marcado(s) como onboarding completado")
    mark_onboarding_completed.short_description = "Marcar onboarding como completado"
    
    def mark_onboarding_pending(self, request, queryset):
        updated = queryset.update(onboarding_completed=False)
        self.message_user(request, f"{updated} bot(s) marcado(s) como onboarding pendiente")
    mark_onboarding_pending.short_description = "Marcar onboarding como pendiente"

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'get_company_name', 'file_type', 'file_size_mb', 'processing_status', 'chunks_created', 'uploaded_at']
    list_filter = ['processing_status', 'file_type', 'uploaded_at']
    search_fields = ['filename', 'bot_config__company__name', 'minio_path']
    readonly_fields = ['uploaded_at', 'file_size_bytes', 'chunks_created', 'minio_path']
    
    fieldsets = (
        ('Información del Documento', {
            'fields': ('bot_config', 'filename', 'file_type', 'file_size_bytes', 'minio_path')
        }),
        ('Estado de Procesamiento', {
            'fields': ('processing_status', 'chunks_created', 'error_message')
        }),
        ('Metadatos', {
            'fields': ('metadata', 'uploaded_at'),
            'classes': ('collapse',)
        })
    )
    
    # Acciones personalizadas
    actions = ['reprocess_documents', 'mark_as_failed']
    
    def get_company_name(self, obj):
        return obj.bot_config.company.name
    get_company_name.short_description = 'Empresa'
    get_company_name.admin_order_field = 'bot_config__company__name'
    
    def file_size_mb(self, obj):
        if obj.file_size_bytes:
            return f"{obj.file_size_bytes / 1024 / 1024:.2f} MB"
        return "N/A"
    file_size_mb.short_description = 'Tamaño'
    
    def reprocess_documents(self, request, queryset):
        updated = queryset.update(processing_status='pending', error_message='')
        self.message_user(request, f"{updated} documento(s) marcado(s) para reprocesamiento")
    reprocess_documents.short_description = "Marcar para reprocesamiento"
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(processing_status='failed')
        self.message_user(request, f"{updated} documento(s) marcado(s) como fallidos")
    mark_as_failed.short_description = "Marcar como fallido"