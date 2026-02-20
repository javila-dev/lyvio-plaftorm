"""
Sistema de autenticación unificado con Chatwoot
"""
import requests
import logging
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Company, User

logger = logging.getLogger(__name__)

class ChatwootAuthBackend(BaseBackend):
    """
    Backend de autenticación que valida contra Chatwoot
    """
    
    def authenticate(self, request, chatwoot_token=None, **kwargs):
        """
        Autentica usuario usando token de Chatwoot
        """
        if not chatwoot_token:
            return None
            
        try:
            # Validar token contra API de Chatwoot
            user_data = self.validate_chatwoot_token(chatwoot_token)
            if not user_data:
                return None
            
            # Buscar o crear usuario local
            user = self.get_or_create_user(user_data)
            return user
            
        except Exception as e:
            logger.error(f"Error en autenticación Chatwoot: {e}")
            return None
    
    def validate_chatwoot_token(self, token):
        """
        Valida token contra API de Chatwoot y obtiene datos del usuario
        """
        try:
            chatwoot_api_url = getattr(settings, 'CHATWOOT_API_URL', 'https://app.chatwoot.com')
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Obtener información del usuario actual
            response = requests.get(
                f'{chatwoot_api_url}/api/v1/profile',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Token inválido en Chatwoot: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error conectando con Chatwoot: {e}")
            return None
    
    def get_or_create_user(self, chatwoot_user_data):
        """
        Obtiene o crea usuario local basado en datos de Chatwoot
        """
        email = chatwoot_user_data.get('email')
        if not email:
            return None
        
        try:
            # Buscar usuario existente
            user = User.objects.get(email=email)
            
            # Actualizar datos si es necesario
            user.first_name = chatwoot_user_data.get('name', '').split(' ')[0]
            user.last_name = ' '.join(chatwoot_user_data.get('name', '').split(' ')[1:])
            user.save()
            
            return user
            
        except User.DoesNotExist:
            # Crear nuevo usuario (esto solo debería pasar en casos edge)
            logger.warning(f"Usuario {email} no existe localmente pero sí en Chatwoot")
            return None
    
    def get_user(self, user_id):
        """
        Obtiene usuario por ID (requerido por Django)
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class ChatwootSessionMiddleware:
    """
    Middleware que maneja la sincronización de sesiones con Chatwoot
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Verificar si necesita autenticación con Chatwoot
        if self.needs_chatwoot_auth(request):
            return self.handle_chatwoot_auth(request)
        
        response = self.get_response(request)
        return response
    
    def needs_chatwoot_auth(self, request):
        """
        Determina si la request necesita autenticación con Chatwoot
        """
        # Rutas que requieren autenticación
        protected_paths = [
            '/bot-builder',
            '/dashboard',
        ]
        
        # Si ya está autenticado en Django, no necesita re-autenticar
        if request.user.is_authenticated:
            return False
        
        # Excluir rutas de autenticación para evitar loops
        auth_paths = [
            '/auth/',
            '/accounts/',
            '/admin/',
        ]
        
        if any(request.path.startswith(path) for path in auth_paths):
            return False
        
        # Si la ruta requiere autenticación
        return any(request.path.startswith(path) for path in protected_paths)
    
    def handle_chatwoot_auth(self, request):
        """
        Maneja la autenticación con Chatwoot
        """
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Verificar si viene con token de Chatwoot
        chatwoot_token = request.GET.get('chatwoot_token')
        
        if chatwoot_token:
            # Intentar autenticar con el token
            from django.contrib.auth import authenticate, login
            
            user = authenticate(request, chatwoot_token=chatwoot_token)
            if user:
                login(request, user)
                # Redirigir sin el token en la URL
                clean_url = request.path
                return redirect(clean_url)
        
        # Si no hay token o es inválido, redirigir a Chatwoot
        return self.redirect_to_chatwoot_login(request)
    
    def redirect_to_chatwoot_login(self, request):
        """
        Redirige a la página de login requerido
        """
        from django.shortcuts import redirect
        from urllib.parse import urlencode
        
        # Redirigir a nuestra página de login que explica el proceso
        params = {
            'next': request.get_full_path()
        }
        
        redirect_url = f"/auth/chatwoot/required/?{urlencode(params)}"
        return redirect(redirect_url)