from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.http import JsonResponse
import uuid
import json
import logging

from accounts.models import Company, User, Trial
# Decoradores removidos - usando @login_required estándar
from bots.models import BotConfig, BotType, Document
from .forms import BotBuilderForm

# Importar vistas de configuración
from .views_configure import bot_configure, delete_document

logger = logging.getLogger(__name__)

@login_required
def bot_config(request):
    """Configuración principal del bot - accesible independientemente del onboarding"""
    # Verificar que el usuario tenga empresa
    if not hasattr(request.user, 'company') or not request.user.company:
        messages.error(request, 'Necesitas completar tu registro empresarial para acceder al bot builder.')
        return redirect('onboarding:company-registration')
    
    company = request.user.company
    
    # Determinar si viene del onboarding
    from_onboarding = request.GET.get('next') == 'onboarding'
    
    # Buscar bot existente o crear uno nuevo
    try:
        bot = BotConfig.objects.get(company=company)
        is_editing = True
    except BotConfig.DoesNotExist:
        bot = None
        is_editing = False
    
    if request.method == 'POST':
        form = BotBuilderForm(request.POST, request.FILES, instance=bot, company=company)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Crear o actualizar bot
                    bot = form.save(commit=False)
                    bot.company = company
                    
                    # Si es nuevo, usar system prompt del tipo seleccionado
                    if not is_editing and bot.bot_type:
                        bot.system_prompt = bot.bot_type.system_prompt
                    
                    bot.save()
                    
                    # Guardar información de Calendly si está habilitada
                    enable_calendly = form.cleaned_data.get('enable_calendly', False)
                    if enable_calendly:
                        calendly_token = form.cleaned_data.get('calendly_token', '').strip()
                        calendly_org_uri = form.cleaned_data.get('calendly_organization_uri', '').strip()
                        
                        if calendly_token and calendly_org_uri:
                            company.calendly_token = calendly_token
                            company.calendly_organization_uri = calendly_org_uri
                            company.save(update_fields=['calendly_token', 'calendly_organization_uri'])
                            messages.success(request, 'Integración de Calendly configurada exitosamente')
                        else:
                            messages.warning(request, 'Por favor completa todos los campos de Calendly para habilitar la integración')
                    else:
                        # Si se deshabilita, limpiar los datos
                        if company.calendly_token or company.calendly_organization_uri:
                            company.calendly_token = ''
                            company.calendly_organization_uri = ''
                            company.save(update_fields=['calendly_token', 'calendly_organization_uri'])
                            messages.info(request, 'Integración de Calendly deshabilitada')
                    
                    # Procesar archivos si se subieron
                    files = request.FILES.getlist('files')
                    if files:
                        # Obtener trial para verificar límites
                        trial = Trial.objects.filter(company=company).first()
                        
                        if trial:
                            current_docs = Document.objects.filter(bot_config=bot).count()
                            if current_docs + len(files) > trial.max_documents:
                                messages.error(request, f'Límite de documentos excedido. Máximo {trial.max_documents} documentos.')
                                return render(request, 'bot_builder/config.html', {
                                    'form': form,
                                    'bot': bot,
                                    'company': company,
                                    'trial': trial,
                                    'existing_documents': Document.objects.filter(bot_config=bot),
                                    'from_onboarding': from_onboarding,
                                    'is_editing': is_editing
                                })
                        
                        # Guardar documentos con estructura: company_id/filename
                        for file in files:
                            Document.objects.create(
                                bot_config=bot,
                                filename=file.name,
                                minio_path=f"{company.id}/{file.name}",
                                file_size_bytes=file.size if hasattr(file, 'size') else 0
                            )
                    
                    success_msg = 'Bot actualizado exitosamente' if is_editing else 'Bot creado exitosamente'
                    messages.success(request, success_msg)
                    
                    if from_onboarding:
                        return redirect('dashboard:dashboard')
                    else:
                        return redirect('bot_builder:config')
                        
            except Exception as e:
                logger.error(f"Error guardando bot config: {e}")
                messages.error(request, 'Error al guardar la configuración')
    else:
        form = BotBuilderForm(instance=bot, company=company)
    
    # Obtener documentos existentes
    existing_documents = []
    if bot:
        existing_documents = Document.objects.filter(bot_config=bot)
    
    # Obtener información del trial
    trial = None
    try:
        trial = Trial.objects.get(company=company)
    except Trial.DoesNotExist:
        pass
    
    context = {
        'form': form,
        'bot': bot,
        'company': company,
        'trial': trial,
        'existing_documents': existing_documents,
        'from_onboarding': from_onboarding,
        'is_editing': is_editing
    }
    
    return render(request, 'bot_builder/config.html', context)

@login_required
def flow_builder(request):
    """Constructor visual de flujos conversacionales (futuro: Rete.js)"""
    
    company = request.user.company
    if not company:
        messages.error(request, 'Usuario sin empresa asociada')
        return redirect('onboarding:company-registration')
    
    bot = get_object_or_404(BotConfig, company=company)
    
    return render(request, 'bot_builder/flow_builder.html', {
        'company': company,
        'bot': bot
    })

@login_required
def preview_bot(request):
    """Vista previa del bot configurado"""
    
    if not request.user.company:
        return JsonResponse({'error': 'No company associated'}, status=400)
    
    company = request.user.company
    
    try:
        bot = BotConfig.objects.get(company=company)
        
        preview_data = {
            'bot_name': bot.name,
            'personality': bot.bot_type.name if bot.bot_type else 'General',
            'system_prompt': bot.system_prompt,
            'documents_count': Document.objects.filter(bot_config=bot).count(),
            'sample_responses': [
                "¡Hola! Soy el asistente de " + company.name + ". ¿En qué puedo ayudarte?",
                "Claro, puedo ayudarte con información sobre nuestros productos y servicios.",
                "Si necesitas hablar con un humano, puedo transferirte con nuestro equipo."
            ]
        }
        
        return JsonResponse(preview_data)
        
    except BotConfig.DoesNotExist:
        return JsonResponse({'error': 'Bot not configured'}, status=404)

@login_required
def save_config(request):
    """Guardar configuración via AJAX"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not request.user.company:
        return JsonResponse({'error': 'No company associated'}, status=400)
    
    # Implementar lógica de guardado AJAX aquí
    # Por ahora, respuesta de éxito
    return JsonResponse({'success': True, 'message': 'Configuración guardada'})


@login_required
@require_http_methods(["POST"])
def save_flow(request):
    """Guardar flujo de conversación del bot"""
    try:
        data = json.loads(request.body)
        bot_id = data.get('bot_id')
        flow_data = data.get('flow_data')
        
        if not bot_id or not flow_data:
            return JsonResponse({'error': 'Datos incompletos'}, status=400)
        
        # Obtener el bot
        company = request.user.company
        if not company:
            return JsonResponse({'error': 'Usuario sin empresa asociada'}, status=400)
            
        bot_config = get_object_or_404(BotConfig, id=bot_id, company=company)
        
        # Guardar el flujo en system_prompt como JSON
        bot_config.system_prompt = json.dumps(flow_data, indent=2)
        bot_config.save()
        
        logger.info(f"Flujo guardado para bot {bot_id} de empresa {company.name}")
        return JsonResponse({
            'success': True, 
            'message': 'Flujo guardado exitosamente'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error al guardar flujo: {str(e)}")
        return JsonResponse({'error': 'Error interno del servidor'}, status=500)
