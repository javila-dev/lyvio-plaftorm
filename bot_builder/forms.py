from django import forms
from bots.models import BotConfig, BotType

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class BotBuilderForm(forms.ModelForm):
    """Formulario para configurar bot en el bot builder"""
    
    files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'file-input file-input-bordered w-full',
            'accept': '.pdf,.doc,.docx,.txt,.md'
        }),
        required=False,
        help_text='Selecciona archivos para entrenar el bot (PDF, DOC, DOCX, TXT, MD)'
    )
    
    # Campos de Calendly
    enable_calendly = forms.BooleanField(
        required=False,
        label='Habilitar integración con Calendly',
        widget=forms.CheckboxInput(attrs={
            'class': 'checkbox checkbox-primary',
            'id': 'enable_calendly'
        }),
        help_text='Permite que el bot agende citas usando tu cuenta de Calendly'
    )
    
    calendly_token = forms.CharField(
        required=False,
        label='Token de acceso de Calendly',
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Ingresa tu Personal Access Token de Calendly',
            'id': 'calendly_token'
        }),
        help_text='<a href="https://calendly.com/integrations/api_webhooks" target="_blank" class="link link-primary">Obtén tu token aquí</a>'
    )
    
    calendly_organization_uri = forms.CharField(
        required=False,
        label='URI de organización de Calendly',
        widget=forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'https://api.calendly.com/organizations/XXXXXX',
            'id': 'calendly_organization_uri'
        }),
        help_text='URI de tu organización en Calendly'
    )
    
    calendly_usage_description = forms.CharField(
        required=False,
        label='¿Cuándo debe el bot agendar con Calendly?',
        widget=forms.Textarea(attrs={
            'class': 'textarea textarea-bordered w-full',
            'placeholder': 'Ej: Cuando el cliente solicite una reunión, demostración del producto, asesoría personalizada, o consulta técnica.',
            'rows': 3,
            'id': 'calendly_usage_description'
        }),
        help_text='Describe en qué situaciones el bot debe ofrecer agendar una cita'
    )
    
    class Meta:
        model = BotConfig
        fields = ['bot_type', 'specialty', 'tone', 'language', 'calendly_usage_description', 'files']
        widgets = {
            'specialty': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered w-full',
                'placeholder': 'Ej: Vendemos productos de tecnología...',
                'rows': 3
            }),
            'tone': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'Ej: Amigable y profesional'
            }),
            'bot_type': forms.Select(attrs={
                'class': 'select select-bordered w-full'
            }),
            'language': forms.Select(attrs={
                'class': 'select select-bordered w-full'
            })
        }
        labels = {
            'specialty': 'Especialidad de la Empresa',
            'tone': 'Tono de Comunicación',
            'bot_type': 'Tipo de Bot',
            'language': 'Idioma'
        }
    
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        # Cargar tipos de bot disponibles
        self.fields['bot_type'].queryset = BotType.objects.filter(is_active=True)
        self.fields['bot_type'].empty_label = "Selecciona el tipo de bot..."
        
        # Pre-cargar datos de Calendly si existen
        if self.company:
            if self.company.calendly_token:
                self.fields['calendly_token'].initial = self.company.calendly_token
                self.fields['enable_calendly'].initial = True
            if self.company.calendly_organization_uri:
                self.fields['calendly_organization_uri'].initial = self.company.calendly_organization_uri
        
        # Ocultar el campo calendly_usage_description del modelo ya que usamos el del form
        if 'calendly_usage_description' in self.fields:
            self.fields['calendly_usage_description'].widget = forms.HiddenInput()