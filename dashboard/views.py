import os
import logging
import hashlib
import time
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings as django_settings
from accounts.models import Company, User, ActivationToken
from bots.models import BotConfig, Document
from subscriptions.models import Subscription
from datetime import timedelta
from .serializers import serialize_companies_list, serialize_company_status

logger = logging.getLogger(__name__)

@login_required
def dashboard_home(request):
    """Dashboard principal del cliente"""
    try:
        # Obtener company del usuario autenticado
        if not request.user.company:
            return redirect('onboarding:company-registration')
        
        company = request.user.company
        trial = getattr(company, 'trial', None)
        bots = BotConfig.objects.filter(company=company)
        
        # Calcular métricas
        total_documents = Document.objects.filter(bot_config__company=company).count()
        
        # Obtener subscription si existe (para usuarios que han convertido)
        from subscriptions.models import Subscription
        try:
            subscription = Subscription.objects.get(company=company)
            is_trial = False
        except Subscription.DoesNotExist:
            subscription = None
            is_trial = True
        
        context = {
            'company': company,
            'trial': trial,
            'subscription': subscription,
            'is_trial': is_trial,
            'bots': bots,
            'total_documents': total_documents,
        }
        
        # Agregar métricas específicas del trial o subscription
        if trial and is_trial:
            context.update({
                'usage_percent': {
                    'messages': (trial.current_messages / trial.max_messages) * 100 if trial.max_messages > 0 else 0,
                    'conversations': (trial.current_conversations / trial.max_conversations) * 100 if trial.max_conversations > 0 else 0,
                    'documents': (trial.current_documents / trial.max_documents) * 100 if trial.max_documents > 0 else 0,
                },
                'limits': {
                    'messages': f"{trial.current_messages}/{trial.max_messages}",
                    'conversations': f"{trial.current_conversations}/{trial.max_conversations}",
                    'documents': f"{trial.current_documents}/{trial.max_documents}",
                }
            })
        
        return render(request, 'dashboard/home.html', context)
        
    except Exception:
        return redirect('onboarding:company-registration')

@login_required
def settings(request):
    """Configuración de la cuenta"""
    if not request.user.company:
        return redirect('onboarding:company-registration')
    
    company = request.user.company
    trial = getattr(company, 'trial', None)
    
    # Obtener subscription si existe
    from subscriptions.models import Subscription
    try:
        subscription = Subscription.objects.get(company=company)
    except Subscription.DoesNotExist:
        subscription = None
    
    return render(request, 'dashboard/settings.html', {
        'company': company,
        'trial': trial,
        'subscription': subscription,
        'is_trial': subscription is None
    })


def get_plan_status(company):
    """Helper function to get comprehensive plan status for a company"""
    from accounts.models import Trial
    from subscriptions.models import Subscription
    
    plan_info = {
        'status': 'sin_plan',
        'plan_name': 'Sin Plan',
        'expiry_date': None,
        'days_remaining': 0,
        'is_trial': False,
        'is_expired': False,
        'status_class': 'status-inactive',
        'resources': None,
        'admin_name': ''
    }
    
    # Obtener nombre del admin (del onboarding)
    admin_name_parts = []
    if company.admin_first_name:
        admin_name_parts.append(company.admin_first_name)
    if company.admin_last_name:
        admin_name_parts.append(company.admin_last_name)
    plan_info['admin_name'] = ' '.join(admin_name_parts) if admin_name_parts else 'No especificado'
    
    # Primero verificar si tiene suscripción activa (pagada)
    try:
        from subscriptions.models import Subscription
        subscription = Subscription.objects.filter(
            company=company,
            status='active'
        ).select_related('plan').first()
        
        if subscription:
            plan_info.update({
                'status': 'subscription_active',
                'plan_name': subscription.plan.name if subscription.plan else 'Plan Pagado',
                'expiry_date': subscription.current_period_end.date() if subscription.current_period_end else None,
                'days_remaining': (subscription.current_period_end.date() - timezone.now().date()).days if subscription.current_period_end else 999,
                'is_trial': False,
                'is_expired': False,
                'status_class': 'status-active',
                'resources': {
                    'type': 'subscription',
                    'plan_name': subscription.plan.name if subscription.plan else 'Plan Pagado',
                    'billing_cycle': subscription.billing_cycle,
                    'description': f'Plan {subscription.plan.name}' if subscription.plan else 'Plan Pagado'
                }
            })
            return plan_info
    except Exception as e:
        logger.warning(f"Error al verificar suscripción para {company.name}: {e}")
    
    try:
        # Si no tiene suscripción, verificar trial
        trial = company.trial
        if trial:
            now = timezone.now()
            is_expired = trial.end_date < now if trial.end_date else False
            days_remaining = (trial.end_date - now).days if trial.end_date and not is_expired else 0
            
            # Calcular porcentajes de uso
            messages_percent = (trial.current_messages / trial.max_messages * 100) if trial.max_messages > 0 else 0
            conversations_percent = (trial.current_conversations / trial.max_conversations * 100) if trial.max_conversations > 0 else 0
            documents_percent = (trial.current_documents / trial.max_documents * 100) if trial.max_documents > 0 else 0
            
            plan_info.update({
                'status': 'trial_expired' if is_expired else 'trial_active',
                'plan_name': f'Trial {trial.status.title()}' + (f' ({days_remaining} días)' if not is_expired else ' (Expirado)'),
                'expiry_date': trial.end_date,
                'days_remaining': max(0, days_remaining),
                'is_trial': True,
                'is_expired': is_expired,
                'status_class': 'status-expired' if is_expired else 'status-active',
                'resources': {
                    'type': 'trial',
                    'messages': {
                        'used': trial.current_messages,
                        'limit': trial.max_messages,
                        'percent': round(messages_percent, 1)
                    },
                    'conversations': {
                        'used': trial.current_conversations,
                        'limit': trial.max_conversations,
                        'percent': round(conversations_percent, 1)
                    },
                    'documents': {
                        'used': trial.current_documents,
                        'limit': trial.max_documents,
                        'percent': round(documents_percent, 1)
                    }
                }
            })
    except Exception as e:
        # Si no hay trial, mantener valores por defecto
        pass
    
    return plan_info


@staff_member_required
def admin_dashboard(request):
    """Dashboard administrativo para ver todas las cuentas"""
    
    # Filtros
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    # Query base de empresas con anotaciones
    companies = Company.objects.annotate(
        user_count=Count('users', distinct=True),
        bot_count=Count('bots', distinct=True),
        document_count=Count('bots__documents', distinct=True)
    ).select_related().prefetch_related(
        'users',
        'trial',
        'subscription'
    )
    
    # Aplicar filtros
    if status_filter == 'active':
        companies = companies.filter(users__isnull=False).distinct()
    elif status_filter == 'pending':
        companies = companies.filter(users__isnull=True)
    elif status_filter == 'with_bots':
        companies = companies.filter(bot_count__gt=0)
    elif status_filter == 'trial_active':
        # Empresas con trial activo
        try:
            from accounts.models import Trial
            active_trials = Trial.objects.filter(
                end_date__gte=timezone.now().date(),
                start_date__lte=timezone.now().date()
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=active_trials)
        except:
            companies = companies.none()
    elif status_filter == 'trial_expiring':
        # Empresas con trial que expira en los próximos 7 días
        try:
            from accounts.models import Trial
            expiring_trials = Trial.objects.filter(
                end_date__lte=timezone.now().date() + timedelta(days=7),
                end_date__gte=timezone.now().date()
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=expiring_trials)
        except:
            companies = companies.none()
    elif status_filter == 'trial_expired':
        # Empresas con trial expirado
        try:
            from accounts.models import Trial
            expired_trials = Trial.objects.filter(
                end_date__lt=timezone.now().date()
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=expired_trials)
        except:
            companies = companies.none()
    elif status_filter == 'subscription_active':
        # Empresas con suscripción pagada activa
        try:
            from subscriptions.models import Subscription
            active_subs = Subscription.objects.filter(
                is_active=True
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=active_subs)
        except:
            companies = companies.none()
    
    # Búsqueda
    if search:
        companies = companies.filter(
            Q(name__icontains=search) |
            Q(email__icontains=search) |
            Q(users__email__icontains=search)
        ).distinct()
    
    # Ordenar por fecha de creación descendente
    companies = companies.order_by('-created_at')
    
    # Paginación
    paginator = Paginator(companies, 20)
    page_number = request.GET.get('page')
    companies_page = paginator.get_page(page_number)
    
    # Estadísticas generales
    total_companies = Company.objects.count()
    active_companies = Company.objects.filter(users__isnull=False).distinct().count()
    pending_activation = Company.objects.filter(users__isnull=True).count()
    
    # Empresas registradas en los últimos 7 días
    recent_companies = Company.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Tokens de activación pendientes
    pending_tokens = ActivationToken.objects.filter(
        status='pending',
        expires_at__gte=timezone.now()
    ).count()
    
    # Tokens expirados en las últimas 24 horas
    expired_tokens = ActivationToken.objects.filter(
        status='pending',
        expires_at__lt=timezone.now(),
        expires_at__gte=timezone.now() - timedelta(days=1)
    ).count()
    
    # Intentar obtener estadísticas de trials
    try:
        from subscriptions.models import Trial
        active_trials = Trial.objects.filter(
            end_date__gte=timezone.now(),
            start_date__lte=timezone.now()
        ).count()
        
        expiring_trials = Trial.objects.filter(
            end_date__lte=timezone.now() + timedelta(days=7),
            end_date__gte=timezone.now()
        ).count()
    except:
        active_trials = 0
        expiring_trials = 0
    
    # Agregar información de planes a cada empresa
    companies_with_plan_info = []
    for company in companies_page:
        company.plan_info = get_plan_status(company)
        companies_with_plan_info.append(company)
    
    context = {
        'companies': companies_page,
        'status_filter': status_filter,
        'search': search,
        'stats': {
            'total_companies': total_companies,
            'active_companies': active_companies,
            'pending_activation': pending_activation,
            'recent_companies': recent_companies,
            'pending_tokens': pending_tokens,
            'expired_tokens': expired_tokens,
            'active_trials': active_trials,
            'expiring_trials': expiring_trials,
        }
    }
    
    return render(request, 'dashboard/admin_dashboard.html', context)


# ==================== API ENDPOINTS PARA N8N ====================

def validate_api_key(request):
    """Validar API key para acceso a endpoints"""
    # Intentar obtener API key de múltiples fuentes
    api_key = (
        request.headers.get('X-API-Key') or
        request.headers.get('X-Api-Key') or  # Variación de capitalización
        request.headers.get('x-api-key') or  # Minúsculas
        request.GET.get('api_key') or
        request.GET.get('apikey')
    )
    
    # Limpiar espacios si existe
    if api_key:
        api_key = api_key.strip()
    
    # Obtener la API key esperada de configuración (con fallbacks)
    expected_api_key = (
        getattr(settings, 'CHATWOOT_PLATFORM_TOKEN', None) or
        os.environ.get('CHATWOOT_PLATFORM_TOKEN', None)
    )
    
    # Debug: Log para troubleshooting
    print(f"DEBUG API Key - Received: '{api_key[:10] if api_key else 'None'}...'")
    print(f"DEBUG API Key - Expected: '{expected_api_key[:10] if expected_api_key else 'None'}...'")
    print(f"DEBUG API Key - Length received: {len(api_key) if api_key else 0}")
    print(f"DEBUG API Key - Length expected: {len(expected_api_key) if expected_api_key else 0}")
    print(f"DEBUG API Key - Settings value: {getattr(settings, 'CHATWOOT_PLATFORM_TOKEN', 'NOT_IN_SETTINGS')}")
    print(f"DEBUG API Key - OS environ value: {os.environ.get('CHATWOOT_PLATFORM_TOKEN', 'NOT_IN_OS')}")
    
    return bool(api_key and expected_api_key and api_key == expected_api_key)


def notify_n8n_subscription_reactivated(subscription):
    """
    Notificar a N8N que una suscripción fue reactivada para restaurar features en Chatwoot
    
    Esta función se llama inmediatamente después de que:
    - Escenario 1: Usuario reactiva durante grace period (sin pago)
    - Escenario 2: Usuario renueva después de expiración (con pago aprobado)
    
    N8N recibe la notificación y:
    1. Obtiene el plan de la suscripción
    2. Construye features y limits según el plan
    3. PATCH a Chatwoot para restaurar acceso completo
    
    Args:
        subscription: Subscription object que fue reactivado
    
    Returns:
        dict: Response del webhook N8N o None si falla
    """
    import requests
    
    webhook_url = os.environ.get('N8N_REACTIVATION_WEBHOOK_URL')
    
    if not webhook_url:
        logger.warning("N8N_REACTIVATION_WEBHOOK_URL no está configurado - saltando notificación")
        return None
    
    try:
        payload = {
            'event': 'subscription_reactivated',
            'subscription_id': subscription.id,
            'company_id': subscription.company.id,
            'company_name': subscription.company.name,
            'chatwoot_account_id': subscription.company.chatwoot_account_id,
            'plan_id': subscription.plan.id if subscription.plan else None,
            'plan_name': subscription.plan.name if subscription.plan else None,
            'billing_cycle': subscription.billing_cycle,
            'status': subscription.status,
            'current_period_start': subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            'reactivated_at': timezone.now().isoformat(),
            'platform_token': django_settings.LYVIO_PLATFORM_TOKEN  # Para que N8N llame a Chatwoot
        }
        
        logger.info(f"Notificando a N8N reactivación de subscription {subscription.id} para company {subscription.company.name}")
        
        # Headers con autenticación (mismo token que otros webhooks N8N)
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': django_settings.CHATWOOT_PLATFORM_TOKEN  # Token de autenticación para N8N
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=15  # Aumentado a 15 segundos para dar tiempo a que N8N llame a Chatwoot
        )
        
        if response.status_code == 200:
            logger.info(f"N8N respondió 200 OK para reactivación de subscription {subscription.id}")
            
            # Validar que N8N realmente procesó correctamente
            try:
                response_data = response.json() if response.content else {}
                
                # N8N debe retornar algo que indique éxito
                # Si el workflow de N8N tiene un nodo de respuesta, validarlo aquí
                if response_data.get('success') == False:
                    logger.error(f"N8N respondió 200 pero indicó fallo: {response_data}")
                    return None
                
                logger.info(f"N8N confirmó éxito en reactivación de subscription {subscription.id}: {response_data}")
                return response_data or {'success': True}
                
            except Exception as json_error:
                logger.warning(f"N8N respondió 200 pero sin JSON válido: {json_error}")
                # Si N8N responde 200 sin JSON, asumimos éxito
                return {'success': True}
        
        elif response.status_code == 401:
            logger.error(f"N8N rechazó la autenticación (401) para subscription {subscription.id} - Verificar X-API-Key")
            return None
        else:
            logger.error(f"N8N respondió con error {response.status_code} para reactivación de subscription {subscription.id}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout (15s) al esperar respuesta de N8N para reactivación de subscription {subscription.id}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Error de conexión con N8N para reactivación de subscription {subscription.id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado al notificar N8N para reactivación de subscription {subscription.id}: {e}")
        return None


@csrf_exempt
@require_http_methods(["GET"])
def api_companies_status(request):
    """
    API endpoint para obtener el estado de todas las empresas
    
    Uso desde N8N:
    GET /api/companies/status/?api_key=YOUR_API_KEY
    
    Headers:
    X-API-Key: YOUR_API_KEY
    
    Respuesta:
    {
        "success": true,
        "count": 10,
        "companies": [...]
    }
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'API key inválida o faltante',
            'message': 'Proporciona una API key válida en el header X-API-Key o parámetro api_key'
        }, status=401)
    
    try:
        # Obtener parámetros de filtro opcionales
        status_filter = request.GET.get('status', 'all')
        company_id = request.GET.get('company_id')
        include_inactive = request.GET.get('include_inactive', 'true').lower() == 'true'
        
        # Query base con optimizaciones
        companies = Company.objects.select_related().prefetch_related(
            'users',
            'trial',
            'subscription'
        )
        
        # Filtrar por empresa específica si se proporciona
        if company_id:
            try:
                company = companies.get(id=company_id)
                return JsonResponse({
                    'success': True,
                    'count': 1,
                    'company': serialize_company_status(company)
                })
            except Company.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Empresa no encontrada',
                    'company_id': company_id
                }, status=404)
        
        # Aplicar filtros de estado
        if status_filter == 'active':
            companies = companies.filter(users__isnull=False).distinct()
        elif status_filter == 'pending':
            companies = companies.filter(users__isnull=True)
        elif status_filter == 'trial_active':
            from accounts.models import Trial
            active_trials = Trial.objects.filter(
                end_date__gte=timezone.now().date(),
                status='active'
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=active_trials)
        elif status_filter == 'trial_expired':
            from accounts.models import Trial
            expired_trials = Trial.objects.filter(
                end_date__lt=timezone.now().date()
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=expired_trials)
        elif status_filter == 'subscription_active':
            active_subs = Subscription.objects.filter(
                status='active'
            ).values_list('company_id', flat=True)
            companies = companies.filter(id__in=active_subs)
        
        # Excluir inactivas si se especifica
        if not include_inactive:
            companies = companies.filter(is_active=True)
        
        # Ordenar por fecha de creación
        companies = companies.order_by('-created_at')
        
        # Serializar datos
        companies_data = serialize_companies_list(companies)
        
        return JsonResponse({
            'success': True,
            'count': len(companies_data),
            'timestamp': timezone.now().isoformat(),
            'filters_applied': {
                'status': status_filter,
                'include_inactive': include_inactive
            },
            'companies': companies_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_company_detail(request, company_id):
    """
    API endpoint para obtener detalles de una empresa específica
    
    Uso desde N8N:
    GET /api/companies/{id}/?api_key=YOUR_API_KEY
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'API key inválida o faltante'
        }, status=401)
    
    try:
        company = Company.objects.select_related().prefetch_related(
            'users',
            'trial',
            'subscription'
        ).get(id=company_id)
        
        company_data = serialize_company_status(company)
        
        return JsonResponse({
            'success': True,
            'company': company_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Company.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Empresa no encontrada',
            'company_id': company_id
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_companies_summary(request):
    """
    API endpoint para obtener resumen estadístico de empresas
    
    Uso desde N8N:
    GET /api/companies/summary/?api_key=YOUR_API_KEY
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'API key inválida o faltante'
        }, status=401)
    
    try:
        # Estadísticas básicas
        total_companies = Company.objects.count()
        active_companies = Company.objects.filter(users__isnull=False).distinct().count()
        pending_companies = Company.objects.filter(users__isnull=True).count()
        
        # Estadísticas de trials
        try:
            from accounts.models import Trial
            now = timezone.now()
            active_trials = Trial.objects.filter(
                end_date__gte=now.date(),
                status='active'
            ).count()
            expired_trials = Trial.objects.filter(
                end_date__lt=now.date()
            ).count()
            expiring_trials = Trial.objects.filter(
                end_date__lte=now.date() + timedelta(days=7),
                end_date__gte=now.date(),
                status='active'
            ).count()
        except:
            active_trials = expired_trials = expiring_trials = 0
        
        # Estadísticas de suscripciones
        try:
            active_subscriptions = Subscription.objects.filter(status='active').count()
        except:
            active_subscriptions = 0
        
        # Registros recientes
        recent_companies = Company.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        return JsonResponse({
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_companies': total_companies,
                'active_companies': active_companies,
                'pending_companies': pending_companies,
                'recent_registrations_7d': recent_companies,
                'trials': {
                    'active': active_trials,
                    'expired': expired_trials,
                    'expiring_soon': expiring_trials
                },
                'subscriptions': {
                    'active': active_subscriptions
                },
                'percentages': {
                    'activation_rate': round((active_companies / total_companies * 100), 2) if total_companies > 0 else 0,
                    'trial_conversion': round((active_subscriptions / (active_trials + expired_trials) * 100), 2) if (active_trials + expired_trials) > 0 else 0
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


# Funciones auxiliares para nombres de administrador
def get_admin_first_name_from_company(company):
    """Obtener primer nombre del administrador desde company o users"""
    # Primero intentar del modelo Company
    if company.admin_first_name and company.admin_first_name.strip():
        return company.admin_first_name.strip()
    
    # Si no, intentar del usuario administrador
    admin_user = company.users.filter(is_staff=True).first()
    if admin_user and admin_user.first_name and admin_user.first_name.strip():
        return admin_user.first_name.strip()
        
    # Si no hay admin, intentar del primer usuario
    first_user = company.users.first()
    if first_user and first_user.first_name and first_user.first_name.strip():
        return first_user.first_name.strip()
        
    return None


def get_admin_last_name_from_company(company):
    """Obtener apellido del administrador desde company o users"""
    # Primero intentar del modelo Company
    if company.admin_last_name and company.admin_last_name.strip():
        return company.admin_last_name.strip()
    
    # Si no, intentar del usuario administrador
    admin_user = company.users.filter(is_staff=True).first()
    if admin_user and admin_user.last_name and admin_user.last_name.strip():
        return admin_user.last_name.strip()
        
    # Si no hay admin, intentar del primer usuario
    first_user = company.users.first()
    if first_user and first_user.last_name and first_user.last_name.strip():
        return first_user.last_name.strip()
        
    return None


def get_admin_full_name(company):
    """Obtener nombre completo del administrador"""
    first_name = get_admin_first_name_from_company(company)
    last_name = get_admin_last_name_from_company(company)
    
    parts = []
    if first_name:
        parts.append(first_name)
    if last_name:
        parts.append(last_name)
    
    return ' '.join(parts) if parts else "No especificado"


@csrf_exempt
@require_http_methods(["GET"])
def api_trials_active(request):
    """
    API endpoint para obtener todas las cuentas con trial activo
    
    Perfecto para ejecutar desde N8N para:
    - Monitorear el estado de todos los trials activos
    - Identificar trials próximos a vencer
    - Segmentar por días restantes hasta expiración
    - Enviar notificaciones preventivas
    
    Uso desde N8N:
    GET /api/trials/active/?api_key=YOUR_API_KEY
    GET /api/trials/active/?api_key=YOUR_API_KEY&days_until_expiry=7  (solo los que vencen en 7 días o menos)
    GET /api/trials/active/?api_key=YOUR_API_KEY&include_expired=true  (incluir también expirados)
    
    Parámetros opcionales:
    - days_until_expiry: Filtrar solo trials que vencen en X días o menos
    - include_expired: true/false - incluir trials expirados (default: false)
    
    Respuesta incluye todas las cuentas que:
    - Tienen trial marcado como 'active'
    - La empresa está activa
    - Con información de días restantes hasta expiración
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'API key inválida o faltante'
        }, status=401)
    
    try:
        from accounts.models import Trial
        
        # Obtener parámetros opcionales
        days_until_expiry = request.GET.get('days_until_expiry')
        include_expired = request.GET.get('include_expired', 'false').lower() == 'true'
        
        # Fecha actual
        today = timezone.now().date()
        
        # Buscar trials activos
        trial_filter = {'status': 'active'}
        
        # Si no incluir expirados, filtrar por fecha
        if not include_expired:
            trial_filter['end_date__date__gte'] = today
        
        # Si se especifica días hasta expiración, filtrar por eso
        if days_until_expiry:
            try:
                days_limit = int(days_until_expiry)
                if days_limit >= 0:
                    future_date = today + timedelta(days=days_limit)
                    trial_filter['end_date__date__lte'] = future_date
            except (ValueError, TypeError):
                pass
        
        # Buscar trials que:
        # 1. Están marcados como 'active'
        # 2. Opcionalmente no han expirado aún
        # 3. La empresa está activa
        active_trials = Trial.objects.filter(
            **trial_filter
        ).select_related('company').prefetch_related('company__users')
        
        # Filtrar solo empresas activas
        active_trials = active_trials.filter(
            company__is_active=True
        )
        
        companies_to_process = []
        
        for trial in active_trials:
            company = trial.company
            
            # Calcular días restantes hasta expiración
            days_remaining = (trial.end_date.date() - today).days if trial.end_date else 0
            
            # Determinar estado del trial
            if days_remaining < 0:
                trial_status_desc = f"Expirado hace {abs(days_remaining)} días"
                urgency_level = "expired"
            elif days_remaining == 0:
                trial_status_desc = "Expira HOY"
                urgency_level = "critical"
            elif days_remaining <= 3:
                trial_status_desc = f"Expira en {days_remaining} días"
                urgency_level = "high"
            elif days_remaining <= 7:
                trial_status_desc = f"Expira en {days_remaining} días"
                urgency_level = "medium"
            else:
                trial_status_desc = f"Expira en {days_remaining} días"
                urgency_level = "low"
            
            # Serializar información completa del trial activo
            company_data = {
                'company_id': company.id,
                'company_name': company.name,
                'company_email': company.email,
                'admin_name': get_admin_full_name(company),
                'admin_first_name': get_admin_first_name_from_company(company),
                'admin_last_name': get_admin_last_name_from_company(company),
                'admin_phone': company.phone,
                
                # Datos del trial activo
                'trial_id': trial.id,
                'trial_start_date': trial.start_date.strftime('%Y-%m-%d') if trial.start_date else None,
                'trial_end_date': trial.end_date.strftime('%Y-%m-%d') if trial.end_date else None,
                'trial_status': trial.status,
                'days_remaining': days_remaining,
                'trial_status_description': trial_status_desc,
                'urgency_level': urgency_level,
                
                # Uso actual de recursos
                'current_resources': {
                    'messages_used': trial.current_messages,
                    'messages_limit': trial.max_messages,
                    'messages_percentage': round((trial.current_messages / trial.max_messages * 100), 1) if trial.max_messages > 0 else 0,
                    'conversations_used': trial.current_conversations,
                    'conversations_limit': trial.max_conversations,
                    'conversations_percentage': round((trial.current_conversations / trial.max_conversations * 100), 1) if trial.max_conversations > 0 else 0,
                    'documents_used': trial.current_documents,
                    'documents_limit': trial.max_documents,
                    'documents_percentage': round((trial.current_documents / trial.max_documents * 100), 1) if trial.max_documents > 0 else 0
                },
                
                # Información de contacto
                'contact_info': {
                    'primary_email': company.email,
                    'admin_email': company.users.filter(is_staff=True).first().email if company.users.filter(is_staff=True).exists() else None,
                    'phone': company.phone,
                    'chatwoot_account_id': company.chatwoot_account_id,
                    'chatwoot_access_token': company.chatwoot_access_token
                },
                
                # Métricas de engagement
                'engagement_metrics': {
                    'days_active': (today - trial.start_date.date()).days if trial.start_date else 0,
                    'has_users': company.users.exists(),
                    'user_count': company.users.count(),
                    'has_bots': BotConfig.objects.filter(company=company).exists(),
                    'bot_count': BotConfig.objects.filter(company=company).count()
                },
                
                # Fechas importantes
                'registration_date': company.created_at.strftime('%Y-%m-%d'),
                'is_trial_active': days_remaining >= 0,
                'needs_attention': urgency_level in ['critical', 'high', 'expired']
            }
            
            companies_to_process.append(company_data)
        
        # Estadísticas de trials activos
        stats = {
            'total_active_trials': len(companies_to_process),
            'date_checked': today.strftime('%Y-%m-%d'),
            'timestamp': timezone.now().isoformat(),
            'filters_applied': {
                'days_until_expiry': days_until_expiry,
                'include_expired': include_expired
            },
            'by_urgency_level': {
                'expired': len([c for c in companies_to_process if c['urgency_level'] == 'expired']),
                'critical': len([c for c in companies_to_process if c['urgency_level'] == 'critical']),  # Expira hoy
                'high': len([c for c in companies_to_process if c['urgency_level'] == 'high']),        # 1-3 días
                'medium': len([c for c in companies_to_process if c['urgency_level'] == 'medium']),    # 4-7 días
                'low': len([c for c in companies_to_process if c['urgency_level'] == 'low'])           # >7 días
            },
            'by_usage_level': {
                'low_usage': len([c for c in companies_to_process if c['current_resources']['messages_percentage'] < 25]),
                'medium_usage': len([c for c in companies_to_process if 25 <= c['current_resources']['messages_percentage'] < 75]),
                'high_usage': len([c for c in companies_to_process if c['current_resources']['messages_percentage'] >= 75])
            },
            'engagement_stats': {
                'with_users': len([c for c in companies_to_process if c['engagement_metrics']['has_users']]),
                'with_bots': len([c for c in companies_to_process if c['engagement_metrics']['has_bots']]),
                'no_engagement': len([c for c in companies_to_process if not c['engagement_metrics']['has_users'] and not c['engagement_metrics']['has_bots']])
            },
            'by_days_remaining': {}
        }
        
        # Estadísticas por días restantes
        for c in companies_to_process:
            days_remaining = c['days_remaining']
            if days_remaining not in stats['by_days_remaining']:
                stats['by_days_remaining'][days_remaining] = 0
            stats['by_days_remaining'][days_remaining] += 1
        
        return JsonResponse({
            'success': True,
            'active_trials': companies_to_process,
            'query_parameters': {
                'days_until_expiry': days_until_expiry,
                'include_expired': include_expired
            },
            'stats': stats,
            'actions_needed': {
                'follow_up_urgency': {
                    'expired': f'{stats["by_urgency_level"]["expired"]} empresas ya expiradas necesitan seguimiento inmediato',
                    'critical': f'{stats["by_urgency_level"]["critical"]} empresas expiran HOY - contactar urgentemente',
                    'high': f'{stats["by_urgency_level"]["high"]} empresas expiran en 1-3 días - contactar pronto',
                    'medium': f'{stats["by_urgency_level"]["medium"]} empresas expiran en 4-7 días - seguimiento preventivo'
                },
                'conversion_opportunities': f'Contactar {stats["by_usage_level"]["high_usage"]} empresas con alto uso para conversión',
                'engagement_recovery': f'Reactivar {stats["engagement_stats"]["no_engagement"]} empresas sin engagement'
            },
            'next_steps_for_n8n': [
                f'Iterar sobre active_trials array ({len(companies_to_process)} empresas encontradas)',
                'Para cada empresa: enviar comunicación basada en urgency_level y días restantes',
                'Priorizar empresas con days_remaining <= 3 días y alto uso de recursos',
                'Para high_usage + urgencia crítica/alta: crear lead calificado para ventas',
                'Para empresas ya expiradas: proceso de seguimiento o desactivación según engagement'
            ]
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Error al procesar trials activos',
            'message': str(e),
            'date_checked': timezone.now().date().strftime('%Y-%m-%d')
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_active_subscriptions(request):
    """
    API endpoint para obtener suscripciones activas con información de cobro
    
    Uso desde N8N para cobros recurrentes:
    GET /dashboard/api/subscriptions/active/?api_key=YOUR_API_KEY
    
    Parámetros opcionales:
    - days_until_renewal: Filtrar por días hasta próximo cobro (ej: 0 para hoy, 1 para mañana)
    - include_all: true/false - incluir todas las suscripciones o solo las próximas a renovar
    
    Respuesta incluye:
    - payment_source_id: Para realizar el cobro en Wompi
    - next_billing_date: Fecha del próximo cobro
    - amount: Monto a cobrar
    - customer_email: Email del cliente
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'No autorizado',
            'message': 'API key inválida o faltante'
        }, status=401)
    
    try:
        # Obtener parámetros
        days_until_renewal = request.GET.get('days_until_renewal')
        include_all = request.GET.get('include_all', 'false').lower() == 'true'
        
        # Obtener suscripciones activas
        subscriptions = Subscription.objects.filter(
            status='active'
        ).select_related('company', 'plan').order_by('current_period_end')
        
        # Filtrar por días hasta renovación si se especifica
        if days_until_renewal is not None and not include_all:
            try:
                days = int(days_until_renewal)
                target_date = timezone.now().date() + timedelta(days=days)
                # Buscar suscripciones que renuevan en esa fecha
                subscriptions = subscriptions.filter(
                    current_period_end__date=target_date
                )
            except ValueError:
                pass
        
        # Serializar datos
        subscriptions_data = []
        for sub in subscriptions:
            # Calcular días hasta próximo cobro
            days_until_billing = (sub.current_period_end.date() - timezone.now().date()).days if sub.current_period_end else None
            
            # Calcular monto a cobrar según billing_cycle
            if sub.billing_cycle == 'yearly' and sub.plan.price_yearly:
                amount = float(sub.plan.price_yearly)
            else:
                amount = float(sub.plan.price_monthly)
            
            subscription_info = {
                'subscription_id': sub.id,
                'company_id': sub.company.id,
                'company_name': sub.company.name,
                
                # Información de cobro (CRÍTICO para N8N)
                'payment_source_id': sub.payment_source_id,
                'wompi_customer_email': sub.wompi_customer_email,
                'next_billing_date': sub.current_period_end.date().strftime('%Y-%m-%d') if sub.current_period_end else None,
                'days_until_billing': days_until_billing,
                'amount_to_charge': amount,
                'currency': 'COP',
                
                # Información del plan
                'plan_id': sub.plan.id if sub.plan else None,
                'plan_name': sub.plan.name if sub.plan else None,
                'billing_cycle': sub.billing_cycle,
                
                # Información de la tarjeta guardada
                'card_info': {
                    'brand': sub.card_brand,
                    'last_four': sub.card_last_four,
                    'exp_month': sub.card_exp_month,
                    'exp_year': sub.card_exp_year
                },
                
                # Fechas importantes
                'subscription_started': sub.started_at.strftime('%Y-%m-%d') if sub.started_at else None,
                'current_period_start': sub.current_period_start.strftime('%Y-%m-%d') if sub.current_period_start else None,
                'current_period_end': sub.current_period_end.strftime('%Y-%m-%d') if sub.current_period_end else None,
                
                # Estado
                'status': sub.status,
                'is_ready_for_billing': days_until_billing is not None and days_until_billing <= 0,
                
                # Información de contacto
                'company_email': sub.company.email,
                'company_phone': sub.company.phone,
                'admin_name': f"{sub.company.admin_first_name or ''} {sub.company.admin_last_name or ''}".strip() or 'No especificado',
                
                # Información del administrador (para N8N/Chatwoot)
                'admin_first_name': sub.company.admin_first_name or '',
                'admin_last_name': sub.company.admin_last_name or '',
                'admin_phone': sub.company.phone or '',  # El teléfono está en company.phone
                
                # Chatwoot integration
                'chatwoot_account_id': sub.company.chatwoot_account_id,
                'chatwoot_access_token': sub.company.chatwoot_access_token
            }
            
            subscriptions_data.append(subscription_info)
        
        # Calcular estadísticas
        total_subscriptions = len(subscriptions_data)
        ready_for_billing = sum(1 for s in subscriptions_data if s['is_ready_for_billing'])
        total_revenue_pending = sum(s['amount_to_charge'] for s in subscriptions_data if s['is_ready_for_billing'])
        
        # Agrupar por días hasta cobro
        by_days_until_billing = {}
        for sub in subscriptions_data:
            days = sub['days_until_billing']
            if days is not None:
                if days not in by_days_until_billing:
                    by_days_until_billing[days] = 0
                by_days_until_billing[days] += 1
        
        return JsonResponse({
            'success': True,
            'count': total_subscriptions,
            'timestamp': timezone.now().isoformat(),
            'query_parameters': {
                'days_until_renewal': days_until_renewal,
                'include_all': include_all
            },
            'stats': {
                'total_active_subscriptions': total_subscriptions,
                'ready_for_billing_today': ready_for_billing,
                'total_revenue_pending': round(total_revenue_pending, 2),
                'by_days_until_billing': by_days_until_billing
            },
            'subscriptions': subscriptions_data,
            'instructions_for_n8n': {
                'how_to_charge': 'Usa payment_source_id con Wompi API para crear transacción recurrente',
                'amount_field': 'amount_to_charge (ya calculado según billing_cycle)',
                'customer_email': 'wompi_customer_email para identificar al cliente en Wompi',
                'filter_ready': 'Filtra por is_ready_for_billing=true para cobrar hoy'
            }
        })
        
    except Exception as e:
        logger.error(f"Error en api_active_subscriptions: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_subscription_by_chatwoot(request):
    """
    API endpoint para obtener información de una suscripción usando el chatwoot_account_id
    
    Uso desde N8N/Chatwoot:
    GET /dashboard/api/subscriptions/by-chatwoot-account/?chatwoot_account_id=123456&api_key=YOUR_API_KEY
    
    Parámetros requeridos:
    - chatwoot_account_id: ID de la cuenta en Chatwoot
    
    Respuesta incluye:
    - Información completa de la suscripción
    - Detalles del plan actual
    - Información de facturación
    - Estado de la cuenta
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'No autorizado',
            'message': 'API key inválida o faltante'
        }, status=401)
    
    try:
        # Obtener parámetro
        chatwoot_account_id = request.GET.get('chatwoot_account_id')
        
        if not chatwoot_account_id:
            return JsonResponse({
                'success': False,
                'error': 'Parámetro faltante',
                'message': 'Se requiere el parámetro chatwoot_account_id'
            }, status=400)
        
        try:
            chatwoot_account_id = int(chatwoot_account_id)
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Parámetro inválido',
                'message': 'chatwoot_account_id debe ser un número entero'
            }, status=400)
        
        # Buscar la empresa con ese chatwoot_account_id
        try:
            company = Company.objects.get(chatwoot_account_id=chatwoot_account_id)
        except Company.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No encontrado',
                'message': f'No se encontró ninguna empresa con chatwoot_account_id={chatwoot_account_id}'
            }, status=404)
        
        # Buscar la suscripción de la empresa
        try:
            subscription = Subscription.objects.select_related('company', 'plan').get(company=company)
        except Subscription.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Sin suscripción',
                'message': f'La empresa "{company.name}" no tiene una suscripción activa',
                'company_info': {
                    'company_id': company.id,
                    'company_name': company.name,
                    'company_email': company.email,
                    'chatwoot_account_id': company.chatwoot_account_id,
                    'has_trial': hasattr(company, 'trial')
                }
            }, status=404)
        
        # Calcular días hasta próximo cobro
        days_until_billing = None
        if subscription.current_period_end:
            days_until_billing = (subscription.current_period_end.date() - timezone.now().date()).days
        
        # Calcular monto según billing_cycle
        if subscription.billing_cycle == 'yearly' and subscription.plan.price_yearly:
            amount = float(subscription.plan.price_yearly)
        else:
            amount = float(subscription.plan.price_monthly)
        
        # Serializar datos completos de la suscripción
        subscription_data = {
            'subscription_id': subscription.id,
            'status': subscription.status,
            
            # Información de la empresa
            'company': {
                'company_id': company.id,
                'company_name': company.name,
                'company_email': company.email,
                'company_phone': company.phone,
                'admin_first_name': company.admin_first_name or '',
                'admin_last_name': company.admin_last_name or '',
                'admin_full_name': f"{company.admin_first_name or ''} {company.admin_last_name or ''}".strip() or 'No especificado',
                'chatwoot_account_id': company.chatwoot_account_id,
                'chatwoot_access_token': company.chatwoot_access_token,
                # Cal.com integration
                'calendar_provider': company.calendar_provider if company.calendar_provider else None,
                'calendar_api_key': company.calendar_api_key if company.calendar_api_key else None,
                'calendar_event_id': company.calendar_event_id if company.calendar_event_id else None,
                'calendar_username': company.calendar_username if company.calendar_username else None,
                'calendar_event_slug': company.calendar_event_slug if company.calendar_event_slug else None,
                'calendar_booking_url': company.calendar_booking_url if company.calendar_booking_url else None,
                'has_calendar_integration': bool(company.calendar_api_key and company.calendar_booking_url),
            },
            
            # Información del plan
            'plan': {
                'plan_id': subscription.plan.id if subscription.plan else None,
                'plan_name': subscription.plan.name if subscription.plan else None,
                'plan_type': subscription.plan.plan_type if subscription.plan else None,
                'billing_cycle': subscription.billing_cycle,
                'price_monthly': float(subscription.plan.price_monthly) if subscription.plan else None,
                'price_yearly': float(subscription.plan.price_yearly) if subscription.plan else None,
                'current_price': amount,
            },
            
            # Información de facturación
            'billing': {
                'payment_source_id': subscription.payment_source_id,
                'wompi_customer_email': subscription.wompi_customer_email,
                'next_billing_date': subscription.current_period_end.date().strftime('%Y-%m-%d') if subscription.current_period_end else None,
                'days_until_billing': days_until_billing,
                'amount_to_charge': amount,
                'currency': 'COP',
                'is_ready_for_billing': days_until_billing is not None and days_until_billing <= 0,
            },
            
            # Información de la tarjeta
            'payment_method': {
                'card_brand': subscription.card_brand,
                'card_last_four': subscription.card_last_four,
                'card_exp_month': subscription.card_exp_month,
                'card_exp_year': subscription.card_exp_year,
            },
            
            # Fechas importantes
            'dates': {
                'subscription_started': subscription.started_at.strftime('%Y-%m-%d') if subscription.started_at else None,
                'current_period_start': subscription.current_period_start.strftime('%Y-%m-%d') if subscription.current_period_start else None,
                'current_period_end': subscription.current_period_end.strftime('%Y-%m-%d') if subscription.current_period_end else None,
                'created_at': subscription.created_at.strftime('%Y-%m-%d %H:%M:%S') if subscription.created_at else None,
            }
        }
        
        # Obtener información de BotConfig(s) de la empresa
        bot_configs = BotConfig.objects.filter(company=company).prefetch_related('documents', 'bot_type')
        
        # Obtener límite de documentos según el plan de la empresa
        max_documents_allowed = Document.get_max_documents_for_company(company)
        
        bots_data = []
        for bot in bot_configs:
            # Contar documentos por estado
            total_documents = bot.documents.count()
            documents_completed = bot.documents.filter(processing_status='completed').count()
            documents_processing = bot.documents.filter(processing_status='processing').count()
            documents_failed = bot.documents.filter(processing_status='failed').count()
            
            bot_info = {
                'bot_id': bot.id,
                'bot_name': bot.name,  # Nombre personalizado del bot
                'inbox_id': bot.inbox_id,
                'is_active': bot.is_active,
                'onboarding_completed': bot.onboarding_completed,
                
                # Tipo de bot
                'bot_type': {
                    'id': bot.bot_type.id if bot.bot_type else None,
                    'name': bot.bot_type.name if bot.bot_type else None,
                    'description': bot.bot_type.description if bot.bot_type else None,
                } if bot.bot_type else None,
                
                # Configuración
                'config': {
                    'name': bot.name,  # Nombre personalizado
                    'system_prompt_template': bot.bot_type.system_prompt if bot.bot_type else bot.system_prompt,  # Template original sin compilar
                    'system_prompt_compiled': bot.get_compiled_system_prompt(),  # Prompt final con variables reemplazadas
                    'tone': bot.tone,
                    'industry_sector': bot.industry_sector,
                    'language': bot.language,
                    'company_context': bot.company_context[:200] + '...' if len(bot.company_context) > 200 else bot.company_context,  # Truncar para no enviar texto muy largo
                    'specialty': bot.specialty,
                    'additional_context': bot.additional_context[:200] + '...' if len(bot.additional_context) > 200 else bot.additional_context,
                    'calendly_usage_description': bot.calendly_usage_description if bot.calendly_usage_description else None,
                },
                
                # Documentos
                'documents': {
                    'total': total_documents,
                    'completed': documents_completed,
                    'processing': documents_processing,
                    'failed': documents_failed,
                    'max_allowed': max_documents_allowed,
                    'can_upload_more': total_documents < max_documents_allowed,
                },
                
                # Fechas
                'created_at': bot.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': bot.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            bots_data.append(bot_info)
        
        return JsonResponse({
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'query': {
                'chatwoot_account_id': chatwoot_account_id
            },
            'subscription': subscription_data,
            'bots': {
                'total_bots': len(bots_data),
                'bots': bots_data
            }
        })
        
    except Exception as e:
        logger.error(f"Error en api_subscription_by_chatwoot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_subscription_charge_payload(request, subscription_id):
    """
    Genera el payload listo para enviar a Wompi para cobrar una suscripción
    
    Uso desde N8N:
    GET /dashboard/api/subscriptions/{subscription_id}/charge-payload/?api_key=YOUR_API_KEY
    
    Retorna:
    - url: URL de Wompi para POST
    - headers: Headers requeridos (Authorization, etc)
    - payload: Body JSON listo para enviar
    - subscription_info: Info adicional para logs/tracking
    
    N8N puede tomar este payload y enviarlo directamente a Wompi
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'No autorizado',
            'message': 'API key inválida o faltante'
        }, status=401)
    
    try:
        # Obtener la suscripción
        subscription = Subscription.objects.select_related('company', 'plan').get(
            id=subscription_id,
            status='active'
        )
        
        # Calcular monto según billing_cycle
        if subscription.billing_cycle == 'yearly' and subscription.plan.price_yearly:
            amount = float(subscription.plan.price_yearly)
        else:
            amount = float(subscription.plan.price_monthly)
        
        amount_in_cents = int(amount * 100)
        
        # Generar referencia única
        timestamp = int(time.time())
        reference = f"LYVIO-REC-{subscription.id}-{timestamp}"
        
        # Calcular firma de integridad
        currency = "COP"
        integrity_secret = getattr(settings, 'WOMPI_INTEGRITY_SECRET', None) or os.environ.get('WOMPI_INTEGRITY_SECRET', '')
        integrity_string = f"{reference}{amount_in_cents}{currency}{integrity_secret}"
        signature = hashlib.sha256(integrity_string.encode()).hexdigest()
        
        # Construir payload para Wompi
        wompi_payload = {
            "amount_in_cents": amount_in_cents,
            "currency": currency,
            "signature": signature,
            "customer_email": subscription.wompi_customer_email,
            "reference": reference,
            "payment_source_id": subscription.payment_source_id,
            "payment_method": {
                "installments": 1
            }
        }
        
        # Determinar URL según ambiente
        test_mode = getattr(settings, 'WOMPI_TEST_MODE', True)
        wompi_url = "https://sandbox.wompi.co/v1/transactions" if test_mode else "https://production.wompi.co/v1/transactions"
        
        # Headers requeridos
        private_key = getattr(settings, 'WOMPI_PRIVATE_KEY', None) or os.environ.get('WOMPI_PRIVATE_KEY', '')
        wompi_headers = {
            "Authorization": f"Bearer {private_key}",
            "Content-Type": "application/json"
        }
        
        # Calcular días hasta próximo cobro
        days_until_billing = (subscription.current_period_end.date() - timezone.now().date()).days if subscription.current_period_end else None
        
        return JsonResponse({
            'success': True,
            'subscription_id': subscription.id,
            'timestamp': timezone.now().isoformat(),
            
            # PAYLOAD LISTO PARA N8N
            'wompi_request': {
                'method': 'POST',
                'url': wompi_url,
                'headers': wompi_headers,
                'body': wompi_payload
            },
            
            # Información adicional para tracking
            'subscription_info': {
                'company_id': subscription.company.id,
                'company_name': subscription.company.name,
                'plan_name': subscription.plan.name if subscription.plan else None,
                'billing_cycle': subscription.billing_cycle,
                'amount': amount,
                'amount_in_cents': amount_in_cents,
                'currency': currency,
                'next_billing_date': subscription.current_period_end.strftime('%Y-%m-%d') if subscription.current_period_end else None,
                'days_until_billing': days_until_billing,
                'customer_email': subscription.wompi_customer_email,
                'payment_source_id': subscription.payment_source_id,
                'card_info': {
                    'brand': subscription.card_brand,
                    'last_four': subscription.card_last_four,
                    'exp_month': subscription.card_exp_month,
                    'exp_year': subscription.card_exp_year
                }
            },
            
            # Instrucciones para N8N
            'instructions': {
                'how_to_use': 'Usa el objeto wompi_request para hacer POST a Wompi',
                'example_curl': f"curl -X POST {wompi_url} -H 'Authorization: Bearer PRIVATE_KEY' -H 'Content-Type: application/json' -d '{json.dumps(wompi_payload)}'",
                'next_steps': [
                    '1. Enviar wompi_request.body a wompi_request.url con wompi_request.headers',
                    '2. Si response.data.status == "APPROVED": registrar Invoice y extender period_end',
                    '3. Si response.data.status == "DECLINED": marcar subscription como past_due',
                    '4. Guardar transaction_id para tracking'
                ]
            }
        })
        
    except Subscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Suscripción no encontrada',
            'message': f'No existe suscripción activa con ID {subscription_id}'
        }, status=404)
    except Exception as e:
        logger.error(f"Error generando payload de cobro: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_debug_auth(request):
    """Endpoint temporal para debug de autenticación"""
    api_key_received = request.headers.get('X-API-Key') or request.GET.get('api_key')
    
    # Obtener expected_api_key usando la misma lógica que validate_api_key
    expected_api_key = (
        getattr(settings, 'CHATWOOT_PLATFORM_TOKEN', None) or
        os.environ.get('CHATWOOT_PLATFORM_TOKEN', None)
    )
    
    return JsonResponse({
        'debug_info': {
            'api_key_received': api_key_received[:10] + "..." if api_key_received else None,
            'api_key_received_full_length': len(api_key_received) if api_key_received else 0,
            'expected_api_key': expected_api_key[:10] + "..." if expected_api_key else None,
            'expected_api_key_full_length': len(expected_api_key) if expected_api_key else 0,
            'settings_value': getattr(settings, 'CHATWOOT_PLATFORM_TOKEN', 'NOT_IN_SETTINGS')[:10] + "..." if getattr(settings, 'CHATWOOT_PLATFORM_TOKEN', None) else None,
            'os_environ_value': os.environ.get('CHATWOOT_PLATFORM_TOKEN', 'NOT_IN_OS')[:10] + "..." if os.environ.get('CHATWOOT_PLATFORM_TOKEN', None) else None,
            'headers_available': list(request.headers.keys()),
            'get_params': list(request.GET.keys()),
            'validation_result': api_key_received and expected_api_key and api_key_received == expected_api_key,
            'keys_match': api_key_received == expected_api_key if api_key_received and expected_api_key else False
        }
    })


@csrf_exempt
@require_http_methods(["GET"])
def api_verify_transaction(request, subscription_id):
    """
    Verifica el estado de una transacción de cobro y retorna si fue procesada exitosamente
    
    Uso desde N8N (para polling después de enviar cobro a Wompi):
    GET /dashboard/api/subscriptions/{subscription_id}/verify-transaction/?transaction_id=abc123&api_key=YOUR_API_KEY
    
    Retorna:
    - transaction_processed: Si Wompi procesó la transacción (true/false)
    - transaction_status: Estado final (APPROVED, DECLINED, PENDING, etc)
    - invoice_created: Si se creó la factura en Lyvio
    - subscription_updated: Si se extendió el period_end
    
    N8N puede hacer polling cada 2-3 segundos hasta recibir transaction_processed=true
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'No autorizado',
            'message': 'API key inválida o faltante'
        }, status=401)
    
    transaction_id = request.GET.get('transaction_id')
    if not transaction_id:
        return JsonResponse({
            'success': False,
            'error': 'Parámetro faltante',
            'message': 'Se requiere transaction_id como query parameter'
        }, status=400)
    
    try:
        from subscriptions.models import Invoice
        
        # Buscar la suscripción
        subscription = Subscription.objects.select_related('company', 'plan').get(
            id=subscription_id
        )
        
        # Buscar si ya existe una factura para esta transacción (señal de que el webhook procesó)
        invoice = Invoice.objects.filter(wompi_transaction_id=transaction_id).first()
        
        if invoice:
            # La transacción fue procesada exitosamente
            return JsonResponse({
                'success': True,
                'transaction_processed': True,
                'transaction_status': 'APPROVED',
                'invoice_created': True,
                'invoice_id': invoice.id,
                'invoice_amount': float(invoice.amount) if invoice.amount else None,
                'invoice_paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None,
                'subscription_updated': True,
                'subscription_info': {
                    'id': subscription.id,
                    'status': subscription.status,
                    'current_period_end': subscription.current_period_end.strftime('%Y-%m-%d') if subscription.current_period_end else None,
                    'company_name': subscription.company.name,
                    'plan_name': subscription.plan.name if subscription.plan else None
                },
                'message': 'Transacción procesada exitosamente por webhook'
            })
        else:
            # La transacción aún no ha sido procesada (webhook no ha llegado o transacción DECLINED)
            # Intentar consultar directamente a Wompi para verificar el estado
            from subscriptions.wompi_service import WompiService
            wompi_service = WompiService()
            
            try:
                transaction_data = wompi_service.get_transaction_status(transaction_id)
                transaction_status = transaction_data.get('status')
                
                return JsonResponse({
                    'success': True,
                    'transaction_processed': transaction_status in ['APPROVED', 'DECLINED', 'ERROR', 'VOIDED'],
                    'transaction_status': transaction_status,
                    'invoice_created': False,
                    'subscription_updated': False,
                    'subscription_info': {
                        'id': subscription.id,
                        'status': subscription.status,
                        'current_period_end': subscription.current_period_end.strftime('%Y-%m-%d') if subscription.current_period_end else None,
                        'company_name': subscription.company.name,
                        'plan_name': subscription.plan.name if subscription.plan else None
                    },
                    'wompi_transaction_data': {
                        'id': transaction_data.get('id'),
                        'status': transaction_status,
                        'amount_in_cents': transaction_data.get('amount_in_cents'),
                        'reference': transaction_data.get('reference'),
                        'payment_method_type': transaction_data.get('payment_method', {}).get('type'),
                        'created_at': transaction_data.get('created_at')
                    },
                    'message': f"Transacción en estado {transaction_status}. {'Webhook aún no ha procesado.' if transaction_status == 'APPROVED' else 'Transacción no aprobada.'}"
                })
            except Exception as wompi_error:
                # No se pudo consultar Wompi (posiblemente transacción muy reciente)
                return JsonResponse({
                    'success': True,
                    'transaction_processed': False,
                    'transaction_status': 'PENDING',
                    'invoice_created': False,
                    'subscription_updated': False,
                    'subscription_info': {
                        'id': subscription.id,
                        'status': subscription.status,
                        'company_name': subscription.company.name
                    },
                    'message': f"Transacción aún no procesada. Continuar polling. Error Wompi: {str(wompi_error)}"
                })
        
    except Subscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Suscripción no encontrada',
            'message': f'No existe suscripción con ID {subscription_id}'
        }, status=404)
    except Exception as e:
        logger.error(f"Error verificando transacción {transaction_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST", "PUT"])
def api_suspend_subscription(request, subscription_id):
    """
    API endpoint para suspender una suscripción por fallo de pago
    
    Uso desde N8N cuando no se puede cobrar después de varios intentos:
    POST /dashboard/api/subscriptions/{subscription_id}/suspend/?api_key=YOUR_API_KEY
    
    Body (opcional):
    {
        "reason": "payment_failed",  // Razón de la suspensión
        "failed_transaction_id": "abc123",  // ID de transacción fallida
        "notes": "3 intentos fallidos de cobro"  // Notas adicionales
    }
    
    Qué hace:
    - Cambia status de 'active' a 'suspended'
    - Registra la razón y fecha de suspensión
    - Mantiene toda la información de la suscripción intacta
    - Permite reactivación posterior cuando se actualice el método de pago
    
    NO hace:
    - NO elimina la suscripción
    - NO elimina el acceso del usuario (eso se hace en otro endpoint)
    - NO modifica el billing cycle o fechas
    """
    # Validar API key
    if not validate_api_key(request):
        return JsonResponse({
            'success': False,
            'error': 'No autorizado',
            'message': 'API key inválida o faltante'
        }, status=401)
    
    try:
        # Obtener la suscripción
        subscription = Subscription.objects.select_related('company', 'plan').get(
            id=subscription_id
        )
        
        # Verificar que esté activa
        if subscription.status != 'active':
            return JsonResponse({
                'success': False,
                'error': 'Estado inválido',
                'message': f'La suscripción ya está en estado: {subscription.status}',
                'current_status': subscription.status
            }, status=400)
        
        # Obtener datos del body (si existen)
        try:
            body_data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except json.JSONDecodeError:
            body_data = {}
        
        reason = body_data.get('reason', 'payment_failed')
        failed_transaction_id = body_data.get('failed_transaction_id', '')
        notes = body_data.get('notes', '')
        
        # Guardar estado anterior
        previous_status = subscription.status
        
        # Suspender suscripción
        subscription.status = 'suspended'
        subscription.save()
        
        logger.info(f"🚫 Suscripción {subscription_id} SUSPENDIDA por N8N")
        logger.info(f"   Empresa: {subscription.company.name}")
        logger.info(f"   Razón: {reason}")
        logger.info(f"   Estado anterior: {previous_status}")
        if failed_transaction_id:
            logger.info(f"   Transacción fallida: {failed_transaction_id}")
        if notes:
            logger.info(f"   Notas: {notes}")
        
        # TODO: Aquí podrías crear un registro en una tabla de "SuspensionHistory"
        # para tener un historial de suspensiones y reactivaciones
        
        return JsonResponse({
            'success': True,
            'message': f'Suscripción {subscription_id} suspendida exitosamente',
            'subscription': {
                'id': subscription.id,
                'company_id': subscription.company.id,
                'company_name': subscription.company.name,
                'company_email': subscription.company.email,
                'previous_status': previous_status,
                'current_status': subscription.status,
                'plan_name': subscription.plan.name if subscription.plan else None,
                'billing_cycle': subscription.billing_cycle,
                'payment_source_id': subscription.payment_source_id,
                'current_period_end': subscription.current_period_end.strftime('%Y-%m-%d') if subscription.current_period_end else None,
                'chatwoot_account_id': subscription.company.chatwoot_account_id
            },
            'suspension_info': {
                'reason': reason,
                'failed_transaction_id': failed_transaction_id,
                'notes': notes,
                'suspended_at': timezone.now().isoformat()
            },
            'next_steps': {
                'to_reactivate': f'POST /dashboard/api/subscriptions/{subscription_id}/reactivate/',
                'to_cancel': f'POST /dashboard/api/subscriptions/{subscription_id}/cancel/',
                'notify_user': 'Envía notificación al usuario vía Chatwoot sobre suspensión'
            }
        })
        
    except Subscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Suscripción no encontrada',
            'message': f'No existe suscripción con ID {subscription_id}'
        }, status=404)
    except Exception as e:
        logger.error(f"Error suspendiendo suscripción {subscription_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_cancelled_subscriptions_to_suspend(request):
    """
    API endpoint para N8N: Devuelve suscripciones canceladas cuyo período ya expiró
    y necesitan ser suspendidas en Chatwoot
    
    GET /dashboard/api/subscriptions/cancelled-to-suspend/
    
    Headers requeridos:
        X-API-Key: Token para autenticar la petición desde N8N
    
    Response:
        {
            "count": 2,
            "subscriptions": [
                {
                    "subscription_id": 123,
                    "company_id": 456,
                    "company_name": "Empresa XYZ",
                    "chatwoot_account_id": 789,
                    "plan_name": "Starter",
                    "cancelled_at": "2024-10-15T10:30:00Z",
                    "current_period_end": "2024-11-01T00:00:00Z",
                    "days_expired": 4
                }
            ]
        }
    """
    try:
        # Validar API Key
        api_key = request.headers.get('X-API-Key')
        expected_key = django_settings.CHATWOOT_PLATFORM_TOKEN
        
        if not api_key or api_key != expected_key:
            logger.warning("❌ Intento de acceso no autorizado al endpoint de suscripciones canceladas")
            return JsonResponse({
                'success': False,
                'error': 'No autorizado',
                'message': 'API Key inválida o faltante'
            }, status=401)
        
        logger.info("🔍 N8N consultando suscripciones canceladas para suspender...")
        
        # Buscar TODAS las suscripciones canceladas
        now = timezone.now()
        
        cancelled_subscriptions = Subscription.objects.filter(
            status='cancelled'
        ).select_related('company', 'plan').order_by('current_period_end')
        
        subscriptions_data = []
        for sub in cancelled_subscriptions:
            # Verificar si el período ya expiró
            period_expired = sub.current_period_end < now if sub.current_period_end else True
            days_remaining = (sub.current_period_end - now).days if sub.current_period_end and not period_expired else 0
            
            subscriptions_data.append({
                'chatwoot_account_id': sub.company.chatwoot_account_id,
                'suspension_date': sub.current_period_end.isoformat() if sub.current_period_end else now.isoformat(),
                'company_name': sub.company.name,
                'period_expired': period_expired,
                'days_remaining': max(0, days_remaining),
                'should_suspend_now': period_expired  # Para que N8N filtre
            })
        
        # Separar por estado
        to_suspend_now = [s for s in subscriptions_data if s['should_suspend_now']]
        pending_suspension = [s for s in subscriptions_data if not s['should_suspend_now']]
        
        logger.info(f"✅ Se encontraron {len(subscriptions_data)} suscripciones canceladas")
        logger.info(f"   - {len(to_suspend_now)} listas para suspender AHORA")
        logger.info(f"   - {len(pending_suspension)} pendientes (aún tienen acceso)")
        
        for sub_data in to_suspend_now:
            logger.info(f"   [SUSPENDER] {sub_data['company_name']} (Chatwoot ID: {sub_data['chatwoot_account_id']})")
        
        for sub_data in pending_suspension:
            logger.info(f"   [PENDIENTE] {sub_data['company_name']} - {sub_data['days_remaining']} días restantes")
        
        return JsonResponse({
            'success': True,
            'total_cancelled': len(subscriptions_data),
            'ready_to_suspend': len(to_suspend_now),
            'pending_suspension': len(pending_suspension),
            'platform_token': django_settings.LYVIO_PLATFORM_TOKEN,
            'accounts_to_suspend': subscriptions_data,
            'note': 'Filtra por should_suspend_now=true para suspender solo las que ya expiraron'
        })
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo suscripciones canceladas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': 'Error interno del servidor',
            'message': str(e)
        }, status=500)