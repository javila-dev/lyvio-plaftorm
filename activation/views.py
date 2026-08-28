from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from accounts.models import ActivationToken, User, Company, Trial
from onboarding.forms import OnboardingCompanyForm
from bots.services import N8NService
import asyncio
import logging

logger = logging.getLogger(__name__)





def activate_account(request, token):
    """Procesa la activación de cuenta via token"""
    token_obj = get_object_or_404(ActivationToken, token=token)
    
    # Verificar si el token es válido
    if not token_obj.is_valid:
        if token_obj.status == 'used':
            messages.error(request, 'Este enlace de activación ya ha sido utilizado.')
        else:
            messages.error(request, 'Este enlace de activación ha expirado.')
        return redirect('activation:activation_error')
    
    # Verificar si ya existe un usuario con este email
    if User.objects.filter(email=token_obj.email).exists():
        messages.error(request, 'Ya existe una cuenta con este email.')
        return redirect('activation:activation_error')
    
    if request.method == 'POST':
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validaciones
        if not password or len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'activation/create_password.html', {
                'token': token,
                'email': token_obj.email,
            })
        
        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'activation/create_password.html', {
                'token': token,
                'email': token_obj.email,
            })
        
        try:
            # Buscar la company por email
            company = Company.objects.get(email=token_obj.email)
            
            # PRIMERO: Preparar datos y enviar a N8N ANTES de crear usuario
            try:
                n8n_service = N8NService()
                full_name = f"{company.admin_first_name} {company.admin_last_name}".strip()
                
                # Obtener información del trial
                try:
                    trial = Trial.objects.get(company=company)
                    
                    # Obtener features del plan si existe
                    plan_features = {}
                    plan_limits = {}
                    
                    if trial.plan:
                        # Usar features y limits del plan asociado al trial
                        plan_features = trial.plan.features if trial.plan.features else {}
                        plan_limits = {
                            'max_inboxes': trial.plan.max_inboxes,
                            'max_users': trial.plan.max_users,
                        }
                    
                    trial_info = {
                        'plan_name': trial.plan.name if trial.plan else 'Trial',
                        'trial_start_date': trial.start_date.isoformat() if trial.start_date else timezone.now().isoformat(),
                        'trial_end_date': trial.end_date.isoformat() if trial.end_date else (timezone.now() + timedelta(days=30)).isoformat(),
                        'trial_days_remaining': trial.days_remaining if hasattr(trial, 'days_remaining') else 30,
                        'max_messages': trial.max_messages,
                        'max_conversations': trial.max_conversations,
                        'max_documents': trial.max_documents,
                        'features': plan_features,  # Features del plan
                        'limits': plan_limits,  # Límites del plan
                    }
                    logger.info(f"🎯 Trial encontrado para {company.name}: {trial.start_date} - {trial.end_date}")
                    if trial.plan:
                        logger.info(f"🎯 Plan trial: {trial.plan.name} con {len(plan_features)} features")
                except Trial.DoesNotExist:
                    # Crear fechas de trial por defecto si no existe
                    start_date = timezone.now()
                    end_date = start_date + timedelta(days=30)
                    trial_info = {
                        'plan_name': 'Trial (sin plan configurado)',
                        'trial_start_date': start_date.isoformat(),
                        'trial_end_date': end_date.isoformat(),
                        'trial_days_remaining': 30,
                        'max_messages': 1000,
                        'max_conversations': 100,
                        'max_documents': 10,
                        'features': {},
                        'limits': {},
                    }
                    logger.warning(f"🎯 Trial NO encontrado para {company.name}, usando fechas por defecto")
                
                # Preparar datos para N8N SIN crear usuario aún
                activation_data = {
                    # Datos del usuario
                    'user_email': token_obj.email,
                    'user_name': full_name,
                    'user_password': password,
                    'user_first_name': company.admin_first_name,
                    'user_last_name': company.admin_last_name,
                    'user_phone': company.phone or '',  # Usar el teléfono de la empresa como teléfono del usuario admin
                    
                    # Datos de la empresa
                    'company_name': company.name,
                    'company_email': company.email,
                    'company_phone': company.phone,
                    'company_website': company.website or '',
                    'company_address': company.address or '',
                    'company_id': company.id,
                    
                    # Fechas y metadatos
                    'registration_date': company.created_at.isoformat(),
                    'activation_date': timezone.now().isoformat(),
                    'activation_token': token_obj.token,
                    
                    # URLs y configuración
                    'platform_url': settings.SITE_URL,
                    'callback_url': f"{settings.SITE_URL}/activation/webhook-callback/",
                    
                    # Información del trial/plan
                    **trial_info,
                }
                
                # Ejecutar webhook y ESPERAR respuesta exitosa
                logger.info(f"Enviando webhook de activación para {token_obj.email}")
                webhook_response = asyncio.run(n8n_service.activate_account_webhook(activation_data))
                
                # Procesar respuesta de N8N (array con datos de Chatwoot)
                if not webhook_response or not isinstance(webhook_response, list) or len(webhook_response) == 0:
                    error_msg = f"Respuesta inválida de N8N: {webhook_response}"
                    logger.error(f"Webhook falló para {token_obj.email}: {error_msg}")
                    messages.error(request, f'Error al crear tu cuenta en Chatwoot. Intenta nuevamente o contacta soporte.')
                    return render(request, 'activation/create_password.html', {
                        'token': token,
                        'email': token_obj.email,
                        'name': full_name,
                        'error': 'webhook_failed'
                    })
                
                # Extraer datos de Chatwoot del primer elemento del array
                chatwoot_data = webhook_response[0]

                # Fallbacks robustos: la respuesta del webhook puede devolver claves distintas
                chatwoot_sso_url = chatwoot_data.get('url') or chatwoot_data.get('sso_url') or chatwoot_data.get('login_url')

                # account_id a veces viene como 'account_id', 'account', o incluso 'id' dependiendo del workflow de n8n
                chatwoot_account_id = (
                    chatwoot_data.get('account_id')
                    or chatwoot_data.get('account')
                    or chatwoot_data.get('accountId')
                    or chatwoot_data.get('id')
                )

                # user_id puede venir como 'user_id' o 'userId'
                chatwoot_user_id = chatwoot_data.get('user_id') or chatwoot_data.get('userId') or chatwoot_data.get('chatwoot_user_id')

                # agent id / resource id — usar 'agent_id' o 'id' según lo disponible
                chatwoot_agent_id = chatwoot_data.get('agent_id') or chatwoot_data.get('id') or chatwoot_data.get('agentId')

                chatwoot_access_token = chatwoot_data.get('access_token') or chatwoot_data.get('token') or ''  # Token de acceso de Chatwoot

                # 🐛 DEBUG: Verificar datos extraídos (más explícito)
                logger.debug("🔍 Datos extraídos del webhook: %s", chatwoot_data)
                print(f"🔍 Datos extraídos del webhook: {chatwoot_data}")
                print(f"   SSO URL: {chatwoot_sso_url}")
                print(f"   Account ID: {chatwoot_account_id}")
                print(f"   User ID: {chatwoot_user_id}")
                print(f"   Agent ID: {chatwoot_agent_id}")
                print(f"   Access Token: {chatwoot_access_token[:20]}..." if chatwoot_access_token else "   Access Token: (vacío)")

                # Validación: al menos SSO URL y algún identificador de cuenta deben existir
                if not chatwoot_sso_url or not chatwoot_account_id:
                    error_msg = f"Datos incompletos de Chatwoot: {chatwoot_data}"
                    logger.error(f"Webhook falló para {token_obj.email}: {error_msg}")
                    # Añadir detalles al mensaje mostrado para facilitar debugging en staging (no exponer en prod)
                    messages.error(request, f'Error en la configuración de Chatwoot. Detalles: respuesta incompleta del servicio externo.')
                    context = {
                        'token': token,
                        'email': token_obj.email,
                        'name': full_name,
                        'error': 'webhook_failed',
                    }
                    # Incluir la respuesta raw del webhook solo en DEBUG para no filtrar datos sensibles en producción
                    from django.conf import settings as _settings
                    if getattr(_settings, 'DEBUG', False):
                        context['webhook_response'] = chatwoot_data
                    return render(request, 'activation/create_password.html', context)
                
                logger.info(f"Webhook exitoso para {token_obj.email}. Account ID: {chatwoot_account_id}, User ID: {chatwoot_user_id}")
                logger.info(f"URL de SSO generada: {chatwoot_sso_url}")
                
            except Exception as e:
                logger.error(f"Error crítico en webhook para {token_obj.email}: {str(e)}")
                messages.error(request, 'Error de conexión al crear tu cuenta. Verifica tu conexión e intenta nuevamente.')
                return render(request, 'activation/create_password.html', {
                    'token': token,
                    'email': token_obj.email,
                    'name': full_name,
                    'error': 'connection_failed'
                })
            
            # SEGUNDO: Si N8N fue exitoso, AHORA crear usuario y proceder con activación local
            try:
                # CREAR USUARIO SOLO DESPUÉS de webhook exitoso
                user = User.objects.create_user(
                    username=token_obj.email,
                    email=token_obj.email,
                    password=password,
                    first_name=company.admin_first_name,
                    last_name=company.admin_last_name,
                    company=company
                )
                
                # Guardar chatwoot_user_id en el usuario
                user.chatwoot_user_id = chatwoot_user_id
                user.save()
                
                logger.info(f"User {user.email} created with chatwoot_user_id={chatwoot_user_id}")
                
                # Marcar token como usado SOLO después de crear usuario
                token_obj.status = 'used'
                token_obj.save()
                
                # Guardar IDs y token devueltos por Chatwoot
                company.chatwoot_account_id = chatwoot_account_id
                company.chatwoot_access_token = chatwoot_access_token
                company.save()
                
                # Login automático tras activación exitosa (PRIMERO)
                login(request, user)
                
                # Guardar URL de SSO en la sesión DESPUÉS del login
                # (login() crea una nueva sesión, así que debemos guardar después)
                request.session['chatwoot_sso_url'] = chatwoot_sso_url
                request.session['chatwoot_account_id'] = chatwoot_account_id
                request.session['chatwoot_user_id'] = chatwoot_user_id
                request.session['chatwoot_agent_id'] = chatwoot_agent_id
                request.session.save()  # Forzar guardado inmediato
                
                # 🐛 DEBUG: Verificar que se guardó en sesión
                print(f"🔐 Sesión después de guardar:")
                print(f"   SSO URL en sesión: {request.session.get('chatwoot_sso_url')}")
                print(f"   SSO URL original: {chatwoot_sso_url}")
                print(f"   Son iguales: {request.session.get('chatwoot_sso_url') == chatwoot_sso_url}")
                
                logger.info(f"Activación completa exitosa para {user.email}")
                # No crear mensaje de éxito aquí para evitar que aparezca en la vista de loading
                
            except Exception as e:
                logger.error(f"Error en activación local después de webhook exitoso para {token_obj.email}: {str(e)}")
                messages.error(request, 'Tu cuenta de Chatwoot fue creada, pero hubo un error completando la activación local. Contacta soporte.')
                return render(request, 'activation/create_password.html', {
                    'token': token,
                    'email': token_obj.email,
                    'name': full_name,
                    'error': 'local_activation_failed'
                })
            
            # Si tenemos SSO URL del webhook, ir a página de loading que redirigirá
            if request.session.get('chatwoot_sso_url'):
                sso_url = request.session.get('chatwoot_sso_url')
                print(f"🚀 Preparando redirección a SSO URL: {sso_url}")
                logger.info(f"Redirigiendo a SSO: {sso_url}")
                # Ir a página de éxito que hará el redirect con delay
                return redirect('activation:activation_success')
            else:
                print(f"⚠️ No hay SSO URL en la sesión, redirigiendo a activation_success")
                logger.warning(f"No se encontró SSO URL en la sesión para {token_obj.email}")
            
            # Si no hay SSO URL, redirigir a la página de éxito (fallback)
            return redirect('activation:activation_success')
            
        except Company.DoesNotExist:
            messages.error(request, 'No se encontró la empresa asociada a este email.')
            return redirect('activation:activation_error')
        except Exception as e:
            logger.error(f"Error activating account for {token_obj.email}: {str(e)}")
            messages.error(request, 'Error al activar la cuenta. Intenta nuevamente.')
            company = Company.objects.filter(email=token_obj.email).first()
            admin_name = f"{company.admin_first_name} {company.admin_last_name}".strip() if company else ""
            return render(request, 'activation/create_password.html', {
                'token': token,
                'email': token_obj.email,
                'name': admin_name,
            })
    
    # GET request - mostrar formulario
    try:
        company = Company.objects.get(email=token_obj.email)
        return render(request, 'activation/create_password.html', {
            'token': token,
            'email': token_obj.email,
            'company_name': company.name,
            'admin_name': f"{company.admin_first_name} {company.admin_last_name}".strip(),
        })
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró la empresa asociada a este email.')
        return redirect('activation:activation_error')


def email_sent(request):
    """Página de confirmación de envío de email"""
    return render(request, 'activation/email_sent.html')


def activation_success(request):
    """Página de éxito tras activación"""
    # 🐛 DEBUG: Verificar sesión antes de renderizar
    sso_url = request.session.get('chatwoot_sso_url', '')
    print(f"🎯 activation_success view:")
    print(f"   SSO URL desde sesión: {sso_url}")
    print(f"   Usuario autenticado: {request.user.is_authenticated}")
    print(f"   Usuario: {request.user}")
    
    response = render(request, 'activation/activation_success.html')
    # Evitar caché del navegador
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def activation_error(request):
    """Página de error en activación"""
    return render(request, 'activation/activation_error.html')


def send_activation_email(email, company_name):
    """Función para enviar email de activación desde cualquier parte de la app"""
    from accounts.models import ActivationToken
    import threading
    
    try:
        logger.info(f"Starting activation email process for {email}")
        
        # Crear token de activación
        token = ActivationToken.create_for_email(email)
        logger.info(f"Created activation token for {email}: {token.token[:10]}...")
        
        # Generar URL de activación
        activation_url = f"{settings.SITE_URL}/activation/activate/{token.token}/"
        logger.warning(f"DESARROLLO - Link de activación para {email}: {activation_url}")
        
        # Función para enviar email en hilo separado
        def send_email_async():
            try:
                # CRITICAL: Establecer variables de entorno correctas para SMTP
                import os
                os.environ['EMAIL_USE_TLS'] = 'False'
                os.environ['EMAIL_USE_SSL'] = 'True'
                
                # Forzar recarga de la configuración de email
                from django.core.mail import get_connection
                connection = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host='smtp.hostinger.com',
                    port=465,
                    username='contacto@lyvio.io',
                    password='AN5Hy2mbPXpp!',
                    use_ssl=True,
                    use_tls=False,
                )
                
                # Preparar contexto del email
                context = {
                    'company_name': company_name,
                    'activation_url': activation_url,
                    'expires_hours': 24,
                }
                
                # Renderizar template del email
                html_content = render_to_string('activation/email_activation.html', context)
                
                # Enviar email con conexión específica
                subject = f'Activa tu cuenta en Lyvio - {company_name}'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [email]
                
                send_mail(
                    subject=subject,
                    message=f'Activa tu cuenta haciendo clic en: {activation_url}',
                    from_email=from_email,
                    recipient_list=recipient_list,
                    html_message=html_content,
                    fail_silently=False,  # Cambiar a False para ver errores
                    connection=connection  # Usar conexión específica
                )
                
                logger.info(f"Activation email sent successfully to {email}")
                
            except Exception as e:
                logger.error(f"Error sending email to {email}: {str(e)}")
        
        # Enviar email en hilo separado para no bloquear
        thread = threading.Thread(target=send_email_async)
        thread.daemon = True
        thread.start()
        
        logger.info(f"Email dispatch initiated for {email}")
        return True
        
    except Exception as e:
        logger.error(f"Error in activation email process for {email}: {str(e)}")
        return False
