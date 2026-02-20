from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.contrib.auth import login
import asyncio
import uuid
import logging

from accounts.models import Company, User, Trial
from bots.models import BotConfig, Document
from bots.services import N8NService
from activation.views import send_activation_email
from .forms import BotConfigForm, OnboardingCompanyForm

logger = logging.getLogger(__name__)

def company_registration(request):
    """Paso 1: Registro de empresa y envío de email de activación (sin autenticación)"""
    if request.method == 'POST':
        logger.info("POST request received for company registration")
        form = OnboardingCompanyForm(request.POST)
        logger.info(f"Form is valid: {form.is_valid()}")
        if form.is_valid():
            logger.info("Starting company registration process")
            try:
                with transaction.atomic():
                    email = form.cleaned_data['email']
                    company_name = form.cleaned_data['company_name']
                    
                    # Verificar si ya existe una empresa con este email
                    if Company.objects.filter(email=email).exists():
                        messages.error(request, 'Ya existe una cuenta registrada con este email. Si olvidaste tu contraseña, contacta soporte.')
                        return render(request, 'onboarding/company_registration.html', {
                            'form': form,
                            'step': 1,
                            'total_steps': 3
                        })
                    
                    # Crear empresa (SIN usuario todavía)
                    company = Company.objects.create(
                        name=company_name,
                        email=email,
                        phone=form.cleaned_data.get('phone', ''),
                        website=form.cleaned_data.get('website', ''),
                        admin_first_name=form.cleaned_data.get('first_name', ''),
                        admin_last_name=form.cleaned_data.get('last_name', '')
                    )
                    
                    # Crear trial inmediatamente
                    Trial.objects.create(
                        company=company,
                        status='active',
                        max_messages=1000,
                        max_conversations=100,
                        max_documents=10
                    )
                    
                    # Enviar email de activación
                    logger.info(f"About to send activation email to {email}")
                    try:
                        email_sent = send_activation_email(email, company_name)
                        logger.info(f"Email send result: {email_sent}")
                        if email_sent:
                            # No crear mensaje aquí para evitar que aparezca en otras vistas
                            return redirect('activation:activation_email_sent')
                        else:
                            # Email falló pero no romper el flujo
                            messages.warning(request, f'Hubo un problema enviando el email de activación. Contacta soporte para obtener tu enlace de activación.')
                            return redirect('activation:activation_email_sent')
                    except Exception as email_error:
                        logger.error(f"Error crítico enviando email a {email}: {email_error}")
                        messages.warning(request, f'Registro completado. Hubo un problema enviando el email de activación a {email}. Contacta soporte para obtener tu enlace de activación.')
                        return redirect('activation:activation_email_sent')
                    
            except Exception as e:
                logger.error(f"Error creando empresa/usuario: {e}")
                messages.error(request, 'Hubo un error al procesar tu registro. Intenta nuevamente.')
                
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = OnboardingCompanyForm()
    
    return render(request, 'onboarding/company_registration.html', {
        'form': form,
        'step': 1,
        'total_steps': 3  # Simplificado a 3 pasos: Registro → Configuración → Completado
    })


@require_http_methods(["GET", "POST"])
def bot_config(request):
    """Paso 2: Configuración del bot + documentos (requiere autenticación tras registro)"""
    if not request.user.is_authenticated:
        messages.error(request, 'Sesión expirada. Inicia el proceso nuevamente.')
        return redirect('onboarding:company-registration')
        
    # Obtener company del usuario autenticado
    if not request.user.company:
        messages.error(request, 'Empresa no encontrada')
        return redirect('onboarding:company-registration')
    
    company = request.user.company
    
    if request.method == 'POST':
        form = BotConfigForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Crear Trial si no existe
                    trial, created = Trial.objects.get_or_create(
                        company=company,
                        defaults={
                            'status': 'active',
                            'max_messages': 1000,
                            'max_conversations': 100,
                            'max_documents': 10
                        }
                    )
                    
                    # 2. Crear config del bot
                    bot = form.save(commit=False)
                    bot.company = company
                    
                    # Usar el system prompt del tipo de bot seleccionado
                    if bot.bot_type:
                        bot.system_prompt = bot.bot_type.system_prompt
                    
                    bot.save()
                    
                    # 3. Procesar archivos subidos
                    uploaded_files = []
                    files = request.FILES.getlist('files')
                    
                    if files:
                        # Verificar límite de documentos del trial
                        if len(files) + trial.current_documents > trial.max_documents:
                            messages.error(request, f'Límite de documentos excedido. Máximo {trial.max_documents} documentos en trial.')
                            return render(request, 'onboarding/bot_config.html', {
                                'form': form,
                                'company': company,
                                'trial': trial,
                                'step': 2,
                                'total_steps': 3
                            })
                        
                        # Simular MinIO guardando los datos en Document con estructura: company_id/filename
                        for file in files:
                            document = Document.objects.create(
                                bot_config=bot,
                                filename=file.name,
                                minio_path=f"{company.id}/{file.name}",
                                file_size_bytes=file.size if hasattr(file, 'size') else 0
                            )
                            uploaded_files.append(document.minio_path)
                        
                        # Actualizar contador de documentos
                        trial.current_documents += len(files)
                        trial.save()
                    
                    # 4. Enviar webhook a n8n para crear Chatwoot async
                    n8n_service = N8NService()
                    
                    webhook_data = {
                        'action': 'setup_chatwoot_trial',
                        'company': {
                            'id': company.id,
                            'name': company.name,
                            'email': company.email
                        },
                        'admin_user': {
                            'id': request.user.id,
                            'email': request.user.email,
                            'first_name': request.user.first_name,
                            'last_name': request.user.last_name
                        },
                        'bot_config': {
                            'id': bot.id,
                            'bot_type': bot.bot_type.name if bot.bot_type else 'General',
                            'system_prompt': bot.system_prompt,
                            'specialty': bot.specialty,
                            'tone': bot.tone,
                            'language': bot.language,
                            'services': bot.services,
                            'additional_context': bot.additional_context
                        },
                        'trial': {
                            'start_date': trial.start_date.isoformat(),
                            'end_date': trial.end_date.isoformat(),
                            'days_remaining': trial.days_remaining,
                            'limits': {
                                'messages': trial.max_messages,
                                'conversations': trial.max_conversations,
                                'documents': trial.max_documents
                            }
                        },
                        'documents': [
                            {
                                'filename': doc.filename,
                                'minio_path': doc.minio_path,
                                'size': doc.file_size_bytes
                            } for doc in Document.objects.filter(bot_config=bot)
                        ]
                    }
                    
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        loop.run_until_complete(
                            n8n_service.complete_onboarding_webhook(webhook_data)
                        )
                        
                        loop.close()
                        
                        messages.success(request, f'¡Configuración completa! Tu trial de {trial.days_remaining} días ha comenzado.')
                        
                    except Exception as e:
                        logger.error(f"Error enviando webhook a n8n: {e}")
                        messages.warning(request, 'Bot configurado, pero hubo un problema notificando el sistema. El soporte será contactado.')
                    
                    # Redirigir al bot builder para continuar configuración
                    messages.success(request, 'Bot configurado exitosamente. ¡Ahora puedes personalizar más configuraciones!')
                    return redirect('bot_builder:config')
                    
            except Exception as e:
                logger.error(f"Error configurando bot: {e}")
                messages.error(request, f'Error configurando bot: {str(e)}')
    else:
        form = BotConfigForm()
    
    return render(request, 'onboarding/bot_config.html', {
        'form': form,
        'company': company,
        'step': 4,
        'total_steps': 4  # Reducido a 4 pasos ya que combinamos config+docs
    })

# Vista documents_upload eliminada - ahora integrada en bot_config
    
def complete(request):
    """Paso 3: Completado - Mostrar resumen del trial"""
    if not request.user.is_authenticated:
        messages.error(request, 'Sesión expirada. Inicia el proceso nuevamente.')
        return redirect('onboarding:company-registration')
        
    if not request.user.company:
        messages.error(request, 'Empresa no encontrada')
        return redirect('onboarding:company-registration')
    
    company = request.user.company
    
    try:
        bot_config = BotConfig.objects.get(company=company)
        trial = company.trial
    except (BotConfig.DoesNotExist, Trial.DoesNotExist):
        messages.error(request, 'Configuración incompleta')
        return redirect('onboarding:bot-config')
    
    # Marcar onboarding como completado
    if not getattr(bot_config, 'onboarding_completed', False):
        bot_config.onboarding_completed = True
        bot_config.save()
    
    # Limpiar datos de sesión
    request.session.pop('onboarding_company_id', None)
    request.session.pop('onboarding_user_id', None)
    
    documents_count = Document.objects.filter(bot_config=bot_config).count()
    
    return render(request, 'onboarding/complete.html', {
        'company': company,
        'bot_config': bot_config,
        'trial': trial,
        'documents_count': documents_count,
        'step': 3,
        'total_steps': 3
    })