"""
Decoradores y utilidades para validar webhooks seguros
"""
from functools import wraps
from django.http import JsonResponse
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def validate_webhook_api_key(view_func):
    """
    Decorador que valida el API key en requests de webhook
    Verifica tanto X-API-Key como Authorization header
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Obtener API key de headers
        api_key_header = request.headers.get('X-API-Key')
        auth_header = request.headers.get('Authorization', '')
        
        # Extraer token del Authorization header si existe
        auth_token = None
        if auth_header.startswith('Bearer '):
            auth_token = auth_header.split('Bearer ')[1]
        
        # API key esperado
        expected_api_key = getattr(settings, 'N8N_WEBHOOK_API_KEY', '')
        
        # Validar que el API key coincida
        if not expected_api_key:
            logger.error("N8N_WEBHOOK_API_KEY no configurado en settings")
            return JsonResponse({
                'success': False,
                'error': 'Webhook API key not configured'
            }, status=500)
        
        # Verificar que al menos uno de los métodos de autenticación sea correcto
        valid_api_key = api_key_header == expected_api_key
        valid_auth_token = auth_token == expected_api_key
        
        if not (valid_api_key or valid_auth_token):
            logger.warning(f"Webhook request with invalid API key from {request.META.get('REMOTE_ADDR', 'unknown')}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid API key'
            }, status=401)
        
        logger.info(f"Webhook request authenticated successfully from {request.META.get('REMOTE_ADDR', 'unknown')}")
        return view_func(request, *args, **kwargs)
    
    return wrapper

def get_client_ip(request):
    """
    Obtiene la IP real del cliente considerando proxies
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip