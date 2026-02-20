import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import SSOToken
from accounts.models import Company
from subscriptions.models import Subscription

User = get_user_model()
logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def generate_sso_token(request):
    """
    Endpoint: POST /api/sso/generate-token/
    
    Genera un token temporal de SSO para autenticación desde Chatwoot vía n8n.
    
    INPUT JSON (campos REQUERIDOS):
    {
        "account_id": "1",
        "shared_secret": "xxx",
        "timestamp": 1234567890,
        "request_id": "sso-xxx-yyy"
    }
    
    INPUT JSON (campos OPCIONALES):
    {
        "email": "user@example.com",
        "chatwoot_user_id": "123"
    }
    
    OUTPUT éxito:
    {
        "success": true,
        "sso_token": "token_temporal_unico",
        "redirect_url": "http://localhost:8000/sso/login?token=xxx",
        "expires_at": "2025-10-17T12:00:00Z"
    }
    
    OUTPUT error:
    {
        "success": false,
        "error": "mensaje de error"
    }
    """
    try:
        # Parse JSON body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.warning("SSO Token Generation: Invalid JSON")
            return JsonResponse({
                "success": False,
                "error": "Invalid JSON format"
            }, status=400)
        
        # Extraer campos REQUERIDOS
        account_id = data.get('account_id')
        shared_secret = data.get('shared_secret')
        timestamp = data.get('timestamp')
        request_id = data.get('request_id')
        
        # Extraer campos OPCIONALES
        email = data.get('email', '')
        chatwoot_user_id = data.get('chatwoot_user_id', '')
        
        # Validar campos obligatorios (solo los esenciales)
        if not all([account_id, shared_secret, timestamp, request_id]):
            logger.warning(f"SSO Token Generation: Missing required fields")
            return JsonResponse({
                "success": False,
                "error": "Missing required fields: account_id, shared_secret, timestamp, request_id"
            }, status=400)
        
        # Validación 1: Verificar shared_secret
        expected_secret = getattr(settings, 'SSO_SHARED_SECRET', None)
        if not expected_secret:
            logger.error("SSO Token Generation: SSO_SHARED_SECRET not configured")
            return JsonResponse({
                "success": False,
                "error": "SSO not properly configured"
            }, status=500)
        
        if shared_secret != expected_secret:
            logger.warning(f"SSO Token Generation: Invalid shared secret for account {account_id}")
            return JsonResponse({
                "success": False,
                "error": "Invalid shared secret"
            }, status=403)
        
        # Validación 2: Verificar timestamp (no mayor a 30 segundos)
        max_age = getattr(settings, 'SSO_MAX_TIMESTAMP_AGE_SECONDS', 30)
        try:
            request_time = timezone.datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            time_diff = (timezone.now() - request_time).total_seconds()
            
            if abs(time_diff) > max_age:
                logger.warning(f"SSO Token Generation: Timestamp too old ({time_diff}s) for account {account_id}")
                return JsonResponse({
                    "success": False,
                    "error": f"Timestamp is too old or in the future (max {max_age} seconds)"
                }, status=400)
        except (ValueError, OSError):
            logger.warning(f"SSO Token Generation: Invalid timestamp for account {account_id}")
            return JsonResponse({
                "success": False,
                "error": "Invalid timestamp format"
            }, status=400)
        
        # Validación 3: Verificar request_id único (prevenir replay attacks)
        if SSOToken.objects.filter(request_id=request_id).exists():
            logger.warning(f"SSO Token Generation: Duplicate request_id {request_id} for account {account_id}")
            return JsonResponse({
                "success": False,
                "error": "Duplicate request_id - possible replay attack"
            }, status=400)
        
        # Email NO es requerido - se puede omitir
        # Si se proporciona email, NO crear/validar usuario aquí
        # El usuario se creará/validará en el momento del login

        
        # Generar token SSO seguro
        sso_token = secrets.token_hex(32)  # 64 caracteres hexadecimales
        
        # Calcular tiempo de expiración
        expiry_minutes = getattr(settings, 'SSO_TOKEN_EXPIRY_MINUTES', 5)
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        
        # Guardar token en la base de datos
        try:
            with transaction.atomic():
                token_obj = SSOToken.objects.create(
                    token=sso_token,
                    email=email,  # Puede estar vacío
                    chatwoot_account_id=account_id,
                    chatwoot_user_id=chatwoot_user_id,  # Puede estar vacío
                    request_id=request_id,
                    expires_at=expires_at
                )
                logger.info(f"SSO Token Generation: Created token for account {account_id}, expires at {expires_at}")
        except IntegrityError as e:
            logger.error(f"SSO Token Generation: Database error for account {account_id}: {str(e)}")
            return JsonResponse({
                "success": False,
                "error": "Failed to create SSO token"
            }, status=500)

        
        # Construir URL de redirect
        redirect_url = f"{request.scheme}://{request.get_host()}/sso/login?token={sso_token}"
        
        # Respuesta exitosa
        return JsonResponse({
            "success": True,
            "sso_token": sso_token,
            "redirect_url": redirect_url,
            "expires_at": expires_at.isoformat()
        }, status=201)
        
    except Exception as e:
        logger.exception(f"SSO Token Generation: Unexpected error: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": "Internal server error"
        }, status=500)


@require_http_methods(["GET"])
def sso_login(request):
    """
    Endpoint: GET /sso/login?token=xxx
    
    Valida el token SSO e inicia sesión del usuario.
    
    INPUT: token (query param)
    
    VALIDACIONES:
    - Token existe en BD
    - No está expirado (< 5 minutos)
    - No ha sido usado previamente
    - Si el token tiene email, buscar/crear usuario
    
    ACCIONES:
    - Si hay email: Buscar/crear usuario y hacer login
    - Si NO hay email: Marcar token como usado y redirigir (para custom auth)
    - Marcar token como usado
    - Redirigir a /dashboard o URL personalizada
    
    OUTPUT:
    - Redirect 302 a /dashboard si éxito
    - Redirect 302 a /login?error=invalid_token si falla
    """
    token_value = request.GET.get('token')
    
    if not token_value:
        logger.warning("SSO Login: No token provided")
        return redirect(f"{settings.LOGIN_URL}?error=missing_token")
    
    try:
        # Buscar el token en la base de datos
        try:
            token_obj = SSOToken.objects.get(token=token_value)
        except SSOToken.DoesNotExist:
            logger.warning(f"SSO Login: Token not found: {token_value[:10]}...")
            return redirect(f"{settings.LOGIN_URL}?error=invalid_token")
        
        # Validación 1: Verificar que no ha sido usado
        if token_obj.used:
            email_info = token_obj.email if token_obj.email else f"account {token_obj.chatwoot_account_id}"
            logger.warning(f"SSO Login: Token already used for {email_info}")
            return redirect(f"{settings.LOGIN_URL}?error=token_already_used")
        
        # Validación 2: Verificar que no está expirado
        if timezone.now() > token_obj.expires_at:
            email_info = token_obj.email if token_obj.email else f"account {token_obj.chatwoot_account_id}"
            logger.warning(f"SSO Login: Token expired for {email_info}")
            return redirect(f"{settings.LOGIN_URL}?error=token_expired")
        
        # Si el token NO tiene email, buscar la compañía por chatwoot_account_id
        # y validar que tenga suscripción activa
        if not token_obj.email:
            try:
                # Buscar la compañía por chatwoot_account_id
                company = Company.objects.get(chatwoot_account_id=token_obj.chatwoot_account_id)
                logger.info(f"SSO Login: Found company {company.name} for account {token_obj.chatwoot_account_id}")
                
                # Verificar que la compañía tenga una suscripción o un trial activo
                subscription = None
                trial_fallback = False
                try:
                    subscription = company.subscription
                    logger.info(f"SSO Login: Company {company.name} has subscription: {subscription.status}")
                except Subscription.DoesNotExist:
                    # Si no hay suscripción, permitir acceso si existe un trial activo
                    trial = getattr(company, 'trial', None)
                    if trial and getattr(trial, 'is_active', False):
                        trial_fallback = True
                        logger.info(f"SSO Login: Company {company.name} has no subscription but has active trial")
                    else:
                        logger.warning(f"SSO Login: Company {company.name} has no subscription and no active trial")
                        return redirect(f"{settings.LOGIN_URL}?error=no_subscription")
                
                # Buscar si hay un usuario principal de esa compañía
                # (el primer usuario o usuario admin)
                try:
                    user = company.users.filter(is_active=True).first()
                    if not user:
                        logger.warning(f"SSO Login: No active users found for company {company.name}")
                        return redirect(f"{settings.LOGIN_URL}?error=no_active_user")
                    
                    # Iniciar sesión con ese usuario
                    with transaction.atomic():
                        token_obj.mark_as_used()
                        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                        logger.info(f"SSO Login: Successfully logged in {user.email} from company {company.name}")
                    
                    # Redirigir al dashboard
                    redirect_url = getattr(settings, 'SSO_REDIRECT_URL', '/dashboard')
                    return redirect(redirect_url)
                    
                except Exception as e:
                    logger.exception(f"SSO Login: Error during login for company {company.name}: {str(e)}")
                    return redirect(f"{settings.LOGIN_URL}?error=login_failed")
                    
            except Company.DoesNotExist:
                logger.warning(f"SSO Login: Company not found for chatwoot_account_id {token_obj.chatwoot_account_id}")
                return redirect(f"{settings.LOGIN_URL}?error=company_not_found")
        
        # Si hay email, buscar/crear usuario y hacer login estándar
        try:
            user = User.objects.get(email=token_obj.email)
        except User.DoesNotExist:
            # Crear usuario si no existe (por seguridad adicional)
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=token_obj.email,
                        username=token_obj.email,
                        is_active=True
                    )
                    logger.info(f"SSO Login: Created new user {token_obj.email}")
            except IntegrityError:
                logger.error(f"SSO Login: Failed to create user {token_obj.email}")
                return redirect(f"{settings.LOGIN_URL}?error=user_creation_failed")
        
        # Verificar que el usuario está activo
        if not user.is_active:
            logger.warning(f"SSO Login: Inactive user {token_obj.email}")
            return redirect(f"{settings.LOGIN_URL}?error=user_inactive")
        
        # Iniciar sesión del usuario
        try:
            with transaction.atomic():
                # Marcar token como usado ANTES de hacer login
                token_obj.mark_as_used()
                
                # Hacer login del usuario
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                logger.info(f"SSO Login: Successfully logged in {user.email}")
        except Exception as e:
            logger.exception(f"SSO Login: Error during login for {user.email}: {str(e)}")
            return redirect(f"{settings.LOGIN_URL}?error=login_failed")
        
        # Redirigir al dashboard
        redirect_url = getattr(settings, 'SSO_REDIRECT_URL', '/dashboard')
        return redirect(redirect_url)
        
    except Exception as e:
        logger.exception(f"SSO Login: Unexpected error: {str(e)}")
        return redirect(f"{settings.LOGIN_URL}?error=internal_error")
