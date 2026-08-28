from django import forms
from .models import Plan


class PlanAdminForm(forms.ModelForm):
    """
    Formulario personalizado para el admin de Plan.
    Convierte el JSONField 'features' en checkboxes individuales para cada feature de Chatwoot.
    Basado en features disponibles en Chatwoot Platform API.
    """
    
    # Features de Chatwoot - Fila 1
    agent_bots = forms.BooleanField(required=False, label='🤖 Agent Bots', help_text='Permitir uso de bots y automatizaciones')
    agent_management = forms.BooleanField(required=False, label='👥 Agent Management', help_text='Gestión de agentes y permisos')
    auto_resolve_conversations = forms.BooleanField(required=False, label='✅ Auto Resolve Conversations', help_text='Auto-resolver conversaciones')
    
    # Features de Chatwoot - Fila 2
    automations = forms.BooleanField(required=False, label='⚙️ Automations', help_text='Automatizaciones y reglas')
    crm = forms.BooleanField(required=False, label='📊 CRM', help_text='Funcionalidades de CRM')
    crm_integration = forms.BooleanField(required=False, label='� CRM Integration', help_text='Integración con CRMs externos')
    
    # Features de Chatwoot - Fila 3
    campaigns = forms.BooleanField(required=False, label='📢 Campaigns', help_text='Campañas de mensajes')
    canned_responses = forms.BooleanField(required=False, label='� Canned Responses', help_text='Respuestas predefinidas')
    chatwoot_v4 = forms.BooleanField(required=False, label='🆕 Chatwoot V4', help_text='Features de Chatwoot V4')
    
    # Features de Chatwoot - Fila 4
    custom_attributes = forms.BooleanField(required=False, label='🏷️ Custom Attributes', help_text='Atributos personalizados')
    custom_reply_domain = forms.BooleanField(required=False, label='🌐 Custom Reply Domain', help_text='Dominio personalizado para respuestas')
    custom_reply_email = forms.BooleanField(required=False, label='✉️ Custom Reply Email', help_text='Email personalizado para respuestas')
    
    # Features de Chatwoot - Fila 5
    email_channel = forms.BooleanField(required=False, label='� Email Channel', help_text='Canal de email')
    email_continuity_on_api_channel = forms.BooleanField(required=False, label='📨 Email Continuity on API Channel', help_text='Continuidad de email en canal API')
    facebook_channel = forms.BooleanField(required=False, label='� Facebook Channel', help_text='Canal de Facebook Messenger')
    
    # Features de Chatwoot - Fila 6
    help_center = forms.BooleanField(required=False, label='📚 Help Center', help_text='Centro de ayuda y base de conocimiento')
    ip_lookup = forms.BooleanField(required=False, label='🌍 IP Lookup', help_text='Búsqueda de información de IP')
    inbound_emails = forms.BooleanField(required=False, label='📥 Inbound Emails', help_text='Emails entrantes')
    
    # Features de Chatwoot - Fila 7
    inbox_management = forms.BooleanField(required=False, label='� Inbox Management', help_text='Gestión de bandejas de entrada')
    instagram_channel = forms.BooleanField(required=False, label='� Instagram Channel', help_text='Canal de Instagram')
    integrations = forms.BooleanField(required=False, label='🔌 Integrations', help_text='Integraciones de terceros')
    
    # Features de Chatwoot - Fila 8
    labels = forms.BooleanField(required=False, label='🏷️ Labels', help_text='Sistema de etiquetas')
    linear_integration = forms.BooleanField(required=False, label='� Linear Integration', help_text='Integración con Linear')
    macros = forms.BooleanField(required=False, label='🎬 Macros', help_text='Macros y acciones rápidas')
    
    # Features de Chatwoot - Fila 9
    notion_integration = forms.BooleanField(required=False, label='📓 Notion Integration', help_text='Integración con Notion')
    quoted_email_reply = forms.BooleanField(required=False, label='💬 Quoted Email Reply', help_text='Respuestas de email citadas')
    reports = forms.BooleanField(required=False, label='� Reports', help_text='Reportes y analytics')
    
    # Features de Chatwoot - Fila 10
    team_management = forms.BooleanField(required=False, label='👥 Team Management', help_text='Gestión de equipos')
    voice_recorder = forms.BooleanField(required=False, label='� Voice Recorder', help_text='Grabación de voz')
    website_channel = forms.BooleanField(required=False, label='💬 Website Channel', help_text='Canal de widget web')
    
    # Features de Chatwoot - Fila 11
    whatsapp_campaign = forms.BooleanField(required=False, label='📱 WhatsApp Campaign', help_text='Campañas de WhatsApp')
    
    # Canales adicionales (no en imagen pero comunes)
    channel_api = forms.BooleanField(required=False, label='� API Channel', help_text='Canal API para integraciones')
    channel_whatsapp = forms.BooleanField(required=False, label='📱 WhatsApp Channel', help_text='Canal de WhatsApp')
    channel_sms = forms.BooleanField(required=False, label='💬 SMS Channel', help_text='Canal de SMS')
    channel_telegram = forms.BooleanField(required=False, label='✈️ Telegram Channel', help_text='Canal de Telegram')
    channel_line = forms.BooleanField(required=False, label='� Line Channel', help_text='Canal de Line')
    channel_twitter = forms.BooleanField(required=False, label='🐦 Twitter Channel', help_text='Canal de Twitter/X')
    
    class Meta:
        model = Plan
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        """
        Inicializa el formulario y pobla los checkboxes desde el JSONField 'features'.
        """
        super().__init__(*args, **kwargs)
        
        # Si estamos editando un plan existente, poblar los checkboxes
        if self.instance and self.instance.pk and self.instance.features:
            features = self.instance.features
            
            # Poblar todos los campos desde el diccionario features
            # Fila 1
            self.fields['agent_bots'].initial = features.get('agent_bots', False)
            self.fields['agent_management'].initial = features.get('agent_management', False)
            self.fields['auto_resolve_conversations'].initial = features.get('auto_resolve_conversations', False)
            
            # Fila 2
            self.fields['automations'].initial = features.get('automations', False)
            self.fields['crm'].initial = features.get('crm', False)
            self.fields['crm_integration'].initial = features.get('crm_integration', False)
            
            # Fila 3
            self.fields['campaigns'].initial = features.get('campaigns', False)
            self.fields['canned_responses'].initial = features.get('canned_responses', False)
            self.fields['chatwoot_v4'].initial = features.get('chatwoot_v4', False)
            
            # Fila 4
            self.fields['custom_attributes'].initial = features.get('custom_attributes', False)
            self.fields['custom_reply_domain'].initial = features.get('custom_reply_domain', False)
            self.fields['custom_reply_email'].initial = features.get('custom_reply_email', False)
            
            # Fila 5
            self.fields['email_channel'].initial = features.get('email_channel', False)
            self.fields['email_continuity_on_api_channel'].initial = features.get('email_continuity_on_api_channel', False)
            self.fields['facebook_channel'].initial = features.get('facebook_channel', False)
            
            # Fila 6
            self.fields['help_center'].initial = features.get('help_center', False)
            self.fields['ip_lookup'].initial = features.get('ip_lookup', False)
            self.fields['inbound_emails'].initial = features.get('inbound_emails', False)
            
            # Fila 7
            self.fields['inbox_management'].initial = features.get('inbox_management', False)
            self.fields['instagram_channel'].initial = features.get('instagram_channel', False)
            self.fields['integrations'].initial = features.get('integrations', False)
            
            # Fila 8
            self.fields['labels'].initial = features.get('labels', False)
            self.fields['linear_integration'].initial = features.get('linear_integration', False)
            self.fields['macros'].initial = features.get('macros', False)
            
            # Fila 9
            self.fields['notion_integration'].initial = features.get('notion_integration', False)
            self.fields['quoted_email_reply'].initial = features.get('quoted_email_reply', False)
            self.fields['reports'].initial = features.get('reports', False)
            
            # Fila 10
            self.fields['team_management'].initial = features.get('team_management', False)
            self.fields['voice_recorder'].initial = features.get('voice_recorder', False)
            self.fields['website_channel'].initial = features.get('website_channel', False)
            
            # Fila 11
            self.fields['whatsapp_campaign'].initial = features.get('whatsapp_campaign', False)
            
            # Canales adicionales
            self.fields['channel_api'].initial = features.get('channel_api', False)
            self.fields['channel_whatsapp'].initial = features.get('channel_whatsapp', False)
            self.fields['channel_sms'].initial = features.get('channel_sms', False)
            self.fields['channel_telegram'].initial = features.get('channel_telegram', False)
            self.fields['channel_line'].initial = features.get('channel_line', False)
            self.fields['channel_twitter'].initial = features.get('channel_twitter', False)
    
    def save(self, commit=True):
        """
        Guarda el formulario convirtiendo los checkboxes de vuelta al JSONField 'features'.
        """
        instance = super().save(commit=False)
        
        # Construir el diccionario de features desde los checkboxes
        # Incluye TODOS los features disponibles en Chatwoot Platform API
        features = {
            # Fila 1
            'agent_bots': self.cleaned_data.get('agent_bots', False),
            'agent_management': self.cleaned_data.get('agent_management', False),
            'auto_resolve_conversations': self.cleaned_data.get('auto_resolve_conversations', False),
            
            # Fila 2
            'automations': self.cleaned_data.get('automations', False),
            'crm': self.cleaned_data.get('crm', False),
            'crm_integration': self.cleaned_data.get('crm_integration', False),
            
            # Fila 3
            'campaigns': self.cleaned_data.get('campaigns', False),
            'canned_responses': self.cleaned_data.get('canned_responses', False),
            'chatwoot_v4': self.cleaned_data.get('chatwoot_v4', False),
            
            # Fila 4
            'custom_attributes': self.cleaned_data.get('custom_attributes', False),
            'custom_reply_domain': self.cleaned_data.get('custom_reply_domain', False),
            'custom_reply_email': self.cleaned_data.get('custom_reply_email', False),
            
            # Fila 5
            'email_channel': self.cleaned_data.get('email_channel', False),
            'email_continuity_on_api_channel': self.cleaned_data.get('email_continuity_on_api_channel', False),
            'facebook_channel': self.cleaned_data.get('facebook_channel', False),
            
            # Fila 6
            'help_center': self.cleaned_data.get('help_center', False),
            'ip_lookup': self.cleaned_data.get('ip_lookup', False),
            'inbound_emails': self.cleaned_data.get('inbound_emails', False),
            
            # Fila 7
            'inbox_management': self.cleaned_data.get('inbox_management', False),
            'instagram_channel': self.cleaned_data.get('instagram_channel', False),
            'integrations': self.cleaned_data.get('integrations', False),
            
            # Fila 8
            'labels': self.cleaned_data.get('labels', False),
            'linear_integration': self.cleaned_data.get('linear_integration', False),
            'macros': self.cleaned_data.get('macros', False),
            
            # Fila 9
            'notion_integration': self.cleaned_data.get('notion_integration', False),
            'quoted_email_reply': self.cleaned_data.get('quoted_email_reply', False),
            'reports': self.cleaned_data.get('reports', False),
            
            # Fila 10
            'team_management': self.cleaned_data.get('team_management', False),
            'voice_recorder': self.cleaned_data.get('voice_recorder', False),
            'website_channel': self.cleaned_data.get('website_channel', False),
            
            # Fila 11
            'whatsapp_campaign': self.cleaned_data.get('whatsapp_campaign', False),
            
            # Canales adicionales
            'channel_api': self.cleaned_data.get('channel_api', False),
            'channel_whatsapp': self.cleaned_data.get('channel_whatsapp', False),
            'channel_sms': self.cleaned_data.get('channel_sms', False),
            'channel_telegram': self.cleaned_data.get('channel_telegram', False),
            'channel_line': self.cleaned_data.get('channel_line', False),
            'channel_twitter': self.cleaned_data.get('channel_twitter', False),
        }
        
        # Asignar el diccionario al campo features
        instance.features = features
        
        if commit:
            instance.save()
        
        return instance
