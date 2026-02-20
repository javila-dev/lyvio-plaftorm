"""
Vistas para el sistema de autenticación SSO con Chatwoot
"""
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

def chatwoot_login_callback(request):
    """
    Callback del login de Chatwoot
    Maneja el token de autenticación y redirige apropiadamente
    """
    chatwoot_token = request.GET.get('token') or request.GET.get('chatwoot_token')
    redirect_to = request.GET.get('redirect_to', '/bot-builder/')
    
    if not chatwoot_token:
        messages.error(request, 'Token de autenticación no recibido desde Chatwoot')
        return redirect('chatwoot_login_required')
    
    # Autenticar con el token de Chatwoot
    user = authenticate(request, chatwoot_token=chatwoot_token)
    
    if user:
        login(request, user)
        messages.success(request, f'Bienvenido {user.first_name}!')
        
        # Redirigir a donde el usuario quería ir originalmente
        return redirect(redirect_to)
    else:
        messages.error(request, 'No se pudo validar tu sesión de Chatwoot. Intenta nuevamente.')
        return redirect('chatwoot_login_required')

def chatwoot_login_required(request):
    """
    Página que explica el proceso de login y redirige a Chatwoot
    """
    return render(request, 'auth/chatwoot_login_required.html', {
        'chatwoot_login_url': get_chatwoot_login_url(request)
    })

def logout_view(request):
    """
    Logout que redirige al login de Lyvio (Chatwoot)
    """
    logout(request)
    messages.info(request, 'Sesión cerrada correctamente')
    
    # Redirigir a la página principal de Lyvio
    lyvio_url = getattr(settings, 'CHATWOOT_API_URL', 'https://app.lyvio.io')
    return redirect(lyvio_url)

@csrf_exempt
def chatwoot_session_check(request):
    """
    API endpoint para verificar si la sesión sigue válida
    Usado por JavaScript para validar sessions periódicamente
    """
    if request.method == 'POST':
        if request.user.is_authenticated:
            return JsonResponse({
                'authenticated': True,
                'user': {
                    'id': request.user.id,
                    'email': request.user.email,
                    'name': request.user.get_full_name()
                }
            })
        else:
            return JsonResponse({
                'authenticated': False,
                'login_url': get_chatwoot_login_url(request)
            })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

from .webhook_security import validate_webhook_api_key

@csrf_exempt
@validate_webhook_api_key
def chatwoot_auth_webhook(request):
    """
    Webhook que recibe tokens de autenticación desde N8N/Chatwoot
    Usado cuando el usuario completa el setup y necesita ser autenticado
    
    Payload esperado:
    {
        "token": "jwt_token_from_chatwoot",
        "user_email": "usuario@empresa.com",
        "user_name": "Nombre Usuario",
        "chatwoot_user_id": 1234,
        "chatwoot_account_id": 5678,
        "redirect_url": "/bot-builder/"
    }
    """
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            
            # Extraer datos principales
            token = data.get('token')
            user_email = data.get('user_email')
            user_name = data.get('user_name', '')
            chatwoot_user_id = data.get('chatwoot_user_id')
            chatwoot_account_id = data.get('chatwoot_account_id')
            redirect_url = data.get('redirect_url', '/bot-builder/')
            
            # Validaciones
            if not token:
                return JsonResponse({'error': 'Token requerido'}, status=400)
            
            if not user_email:
                return JsonResponse({'error': 'Email de usuario requerido'}, status=400)
            
            # Opcional: Verificar que el usuario existe en nuestra base de datos
            try:
                from accounts.models import User
                user = User.objects.get(email=user_email)
                
                # Actualizar IDs de Chatwoot si se proporcionaron
                if chatwoot_user_id and not user.chatwoot_user_id:
                    user.chatwoot_user_id = chatwoot_user_id
                    user.save()
                
                if chatwoot_account_id and user.company and not user.company.chatwoot_account_id:
                    user.company.chatwoot_account_id = chatwoot_account_id
                    user.company.save()
                
            except User.DoesNotExist:
                logger.warning(f"Usuario {user_email} no encontrado en base de datos local")
                # Continuar anyway - el backend de autenticación lo manejará
            
            # Generar URL de autenticación
            from urllib.parse import urlencode
            callback_url = request.build_absolute_uri('/auth/chatwoot/callback/')
            
            params = {
                'token': token,
                'redirect_to': redirect_url
            }
            
            auth_url = f"{callback_url}?{urlencode(params)}"
            
            logger.info(f"URL de autenticación generada para {user_email}")
            
            return JsonResponse({
                'success': True,
                'auth_url': auth_url,
                'user_email': user_email,
                'redirect_to': redirect_url,
                'message': 'URL de autenticación generada correctamente'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
        except Exception as e:
            logger.error(f"Error en webhook de autenticación: {e}")
            return JsonResponse({'error': 'Error procesando webhook'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def get_chatwoot_login_url(request):
    """
    Genera URL de login de Chatwoot con callback apropiado
    """
    from urllib.parse import urlencode
    
    callback_url = request.build_absolute_uri('/auth/chatwoot/callback/')
    redirect_to = request.GET.get('next', request.get_full_path())
    
    params = {
        'redirect_uri': callback_url,
        'state': redirect_to,  # Para recordar dónde redirigir después
        'client_id': getattr(settings, 'CHATWOOT_CLIENT_ID', 'lyvio-bot-builder')
    }
    
    chatwoot_login_url = getattr(settings, 'CHATWOOT_LOGIN_URL', 'https://app.chatwoot.com/app/login')
    return f"{chatwoot_login_url}?{urlencode(params)}"