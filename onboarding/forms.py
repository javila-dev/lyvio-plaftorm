from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div, HTML
from accounts.models import Company, User
from bots.models import BotConfig

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

class OnboardingCompanyForm(forms.Form):
    """Formulario combinado para empresa y contacto administrativo"""
    
    # Datos del administrador
    first_name = forms.CharField(
        max_length=150,
        label='Nombre',
        widget=forms.TextInput(attrs={
            'placeholder': 'Tu nombre',
            'class': 'input input-bordered w-full'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        label='Apellido',
        widget=forms.TextInput(attrs={
            'placeholder': 'Tu apellido',
            'class': 'input input-bordered w-full'
        })
    )
    
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'placeholder': 'tu@empresa.com',
            'class': 'input input-bordered w-full'
        })
    )
    
    # Datos de empresa
    company_name = forms.CharField(
        max_length=200,
        label='Nombre de la empresa',
        widget=forms.TextInput(attrs={
            'placeholder': 'Nombre de tu empresa',
            'class': 'input input-bordered w-full'
        })
    )
    
    phone = forms.CharField(
        max_length=30,
        required=True,
        label='Teléfono',
        widget=forms.TextInput(attrs={
            'placeholder': '+57 300 123 4567',
            'class': 'input input-bordered w-full'
        })
    )
    
    website = forms.URLField(
        required=False,
        label='Sitio web',
        widget=forms.URLInput(attrs={
            'placeholder': 'https://tuempresa.com',
            'class': 'input input-bordered w-full'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data['email']
        # Solo verificar si ya existe una empresa (el usuario se creará después de la activación)
        if Company.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe una empresa registrada con este email. Si olvidaste tu contraseña, contacta soporte.')
        return email

class CompanySetupForm(forms.ModelForm):
    """Formulario legacy - mantenido para compatibilidad"""
    class Meta:
        model = Company
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Nombre de tu empresa',
                'class': 'input input-bordered w-full'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Continuar', css_class='btn btn-primary btn-lg'))

class BotConfigForm(forms.ModelForm):
    # Campo para seleccionar tipo de bot
    bot_type = forms.ModelChoiceField(
        queryset=BotConfig.objects.none(),  # Se configura en __init__
        empty_label="Selecciona el tipo de bot",
        widget=forms.RadioSelect,
        label="Tipo de Bot",
        help_text="Selecciona el tipo que mejor se adapte a tu negocio"
    )
    
    services = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Un servicio por línea:\nChatbots inteligentes\nAutomatización de procesos\nIntegración con CRM',
            'rows': 6
        }),
        help_text='Lista tus servicios principales, uno por línea'
    )
    
    # Campo para archivos (integrado en el formulario) 
    files = MultipleFileField(
        required=False,
        label='Documentos de conocimiento',
        help_text='Sube archivos PDF, DOCX o TXT que el bot debe conocer (opcional)',
        widget=MultipleFileInput(attrs={
            'accept': '.pdf,.docx,.txt',
            'class': 'file-input file-input-bordered w-full'
        })
    )
    
    class Meta:
        model = BotConfig
        fields = ['bot_type', 'specialty', 'tone', 'language', 'services', 'additional_context']
        widgets = {
            'specialty': forms.Textarea(attrs={
                'placeholder': 'Ejemplo: Desarrollamos soluciones con IA para automatizar atención al cliente',
                'rows': 4,
                'class': 'textarea textarea-bordered w-full'
            }),
            'tone': forms.TextInput(attrs={
                'placeholder': 'Se auto-completará según el tipo de bot seleccionado',
                'readonly': True,
                'class': 'input input-bordered w-full'
            }),
            'additional_context': forms.Textarea(attrs={
                'placeholder': 'Horarios, políticas especiales, casos de éxito, etc.',
                'rows': 4,
                'class': 'textarea textarea-bordered w-full'
            })
        }
        labels = {
            'specialty': '¿A qué se dedica tu empresa?',
            'tone': 'Tono de comunicación del bot',
            'language': 'Idioma principal',
            'services': 'Servicios principales',
            'additional_context': 'Contexto adicional (opcional)'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Importar aquí para evitar circular import
        from bots.models import BotType
        
        # Configurar queryset para tipos de bot activos
        self.fields['bot_type'].queryset = BotType.objects.filter(is_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.attrs = {'enctype': 'multipart/form-data'}
        
        # Layout personalizado
        self.helper.layout = Layout(
            HTML('<h4 class="mb-3">Configuración del Bot</h4>'),
            'bot_type',
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Información de tu empresa</h5>'),
            'specialty',
            Row(
                Column('tone', css_class='col-md-6'),
                Column('language', css_class='col-md-6')
            ),
            'services',
            'additional_context',
            HTML('<hr class="my-4">'),
            HTML('<h5 class="mb-3">Documentos de conocimiento (Opcional)</h5>'),
            'files'
        )
        
        self.helper.add_input(Submit('submit', 'Finalizar Configuración', css_class='btn btn-success btn-lg mt-3'))
    
    def clean_services(self):
        services = self.cleaned_data['services']
        services_list = [s.strip() for s in services.split('\n') if s.strip()]
        return services_list

# SOLUCIÓN: Usar HTML directo sin widget personalizado
class DocumentUploadForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.attrs = {'enctype': 'multipart/form-data'}
        self.helper.add_input(Submit('submit', 'Finalizar Configuración', css_class='btn btn-success btn-lg'))