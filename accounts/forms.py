from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import BillingInfo

class ChatwootLoginForm(forms.Form):
    """
    Formulario de login que autentica contra Chatwoot
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'tu.email@empresa.com',
            'autofocus': True
        }),
        label='Email de Chatwoot'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Tu contraseña de Chatwoot'
        }),
        label='Contraseña'
    )
    
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
    
    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        
        if email and password:
            # Autenticar contra Chatwoot
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password
            )
            
            if self.user_cache is None:
                raise ValidationError(
                    'Email o contraseña incorrectos. Asegúrate de usar las mismas credenciales de Chatwoot.',
                    code='invalid_login'
                )
            elif not self.user_cache.is_active:
                raise ValidationError(
                    'Esta cuenta está desactivada.',
                    code='inactive'
                )
        
        return self.cleaned_data
    
    def get_user(self):
        return self.user_cache


class BillingForm(forms.ModelForm):
    class Meta:
        model = BillingInfo
        fields = [
            'name', 'id_type', 'id_number', 'id_dv',
            'kind_of_person', 'regime', 'phone', 'email'
        ]
        widgets = {
            'id_type': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'kind_of_person': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'regime': forms.Select(attrs={'class': 'select select-bordered w-full'}),
            'name': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'id_number': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'id_dv': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'phone': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'email': forms.EmailInput(attrs={'class': 'input input-bordered w-full'}),
        }

    def clean(self):
        cleaned = super().clean()
        id_type = cleaned.get('id_type')
        id_dv = cleaned.get('id_dv')
        id_number = cleaned.get('id_number')

        if id_type == 'NIT' and not id_dv:
            self.add_error('id_dv', 'El dígito verificador (IdDV) es requerido para NIT')

        # Si es NIT, validar que el dígito verificador coincida
        if id_type == 'NIT' and id_number and id_dv:
            # calcular DV esperado
            def compute_nit_dv(nit):
                nit_digits = [int(ch) for ch in nit if ch.isdigit()]
                nit_digits.reverse()
                weights = [3,7,13,17,19,23,29,37,41,43,47,53,59,67,71]
                total = 0
                for i, d in enumerate(nit_digits):
                    if i < len(weights):
                        total += d * weights[i]
                remainder = total % 11
                dv = 11 - remainder
                if dv == 11:
                    return 0
                if dv == 10:
                    return 1
                return dv

            try:
                expected = compute_nit_dv(str(id_number))
                # id_dv puede venir como string con caracteres; normalizamos a int
                provided = int(''.join(ch for ch in str(id_dv) if ch.isdigit()))
                if expected != provided:
                    self.add_error('id_dv', 'El dígito verificador (IdDV) no coincide con el NIT')
            except ValueError:
                self.add_error('id_dv', 'IdDV inválido')

        # Normalizar id_number (quitar espacios y guiones)
        if id_number:
            cleaned['id_number'] = ''.join(ch for ch in id_number if ch.isalnum())

        return cleaned