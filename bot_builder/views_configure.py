from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.core.files.storage import default_storage
from django.conf import settings
import logging
import os
import requests

from bots.models import BotConfig, BotType, Document
from bots.services import MinioService, N8NService
from bots.document_analyzer import DocumentAnalyzer
from accounts.models import Company
import asyncio

logger = logging.getLogger(__name__)

@login_required
def bot_configure(request):
    """Vista principal para configurar el Bot IA desde el portal de billing"""
    
    # Verificar que el usuario tenga empresa
    if not hasattr(request.user, 'company') or not request.user.company:
        messages.error(request, 'Necesitas una empresa asociada para configurar el bot.')
        return redirect('dashboard:dashboard')
    
    company = request.user.company
    
    # Obtener o crear bot config
    bot_config, created = BotConfig.objects.get_or_create(
        company=company,
        defaults={
            'inbox_id': company.id * 1000,  # ID temporal
            'tone': 'Profesional y amigable',
            'language': 'es-CO'
        }
    )
    
    # Obtener tipos de bot disponibles
    bot_types = BotType.objects.filter(is_active=True)
    
    # Obtener documentos actuales
    documents = Document.objects.filter(bot_config=bot_config)
    documents_count = documents.count()
    
    # Obtener límite de documentos según el plan de suscripción
    max_documents = Document.get_max_documents_for_company(company)
    
    # Sectores industriales comunes
    industry_sectors = [
        'Tecnología',
        'Salud y Bienestar',
        'Educación',
        'Retail y E-commerce',
        'Servicios Financieros',
        'Turismo y Hospitalidad',
        'Inmobiliaria',
        'Manufactura',
        'Servicios Profesionales',
        'Entretenimiento',
        'Otro'
    ]
    
    # Tonos disponibles
    tone_options = [
        'Profesional y formal',
        'Profesional y amigable',
        'Casual y cercano',
        'Entusiasta y motivador',
        'Empático y comprensivo',
        'Directo y conciso'
    ]
    
    if request.method == 'POST':
        logger.info(f"POST recibido para configurar bot de {company.name}")
        logger.info(f"Datos POST: {request.POST}")
        logger.info(f"Archivos: {request.FILES}")
        
        try:
            with transaction.atomic():
                # Actualizar configuración del bot
                bot_config.name = request.POST.get('name', '')
                bot_config.bot_type_id = request.POST.get('bot_type')
                bot_config.tone = request.POST.get('tone')
                bot_config.company_context = request.POST.get('company_context')
                bot_config.industry_sector = request.POST.get('industry_sector')
                bot_config.calendly_usage_description = request.POST.get('calendly_usage_description', '')
                
                # Si se seleccionó un tipo de bot, usar su system prompt
                if bot_config.bot_type:
                    bot_config.system_prompt = bot_config.bot_type.system_prompt
                
                bot_config.save()
                
                # Guardar configuración de Cal.com en la empresa
                enable_calendar = request.POST.get('enable_calendar')
                logger.info(f"🔍 DEBUG Cal.com - enable_calendar checkbox: '{enable_calendar}'")
                logger.info(f"🔍 DEBUG Cal.com - Todos los campos POST: {list(request.POST.keys())}")
                
                if enable_calendar == 'on':
                    calendar_api_key = request.POST.get('calendar_api_key', '').strip()
                    calendar_event_id = request.POST.get('calendar_event_id', '').strip()
                    calendar_booking_url = request.POST.get('calendar_booking_url', '').strip()
                    
                    logger.info(f"🔍 DEBUG Cal.com - API Key recibido: '{calendar_api_key[:20] if calendar_api_key else 'VACIO'}...' (len: {len(calendar_api_key)})")
                    logger.info(f"🔍 DEBUG Cal.com - Event ID recibido: '{calendar_event_id}' (len: {len(calendar_event_id)})")
                    logger.info(f"🔍 DEBUG Cal.com - Booking URL recibida: '{calendar_booking_url}' (len: {len(calendar_booking_url)})")
                    logger.info(f"🔍 DEBUG Cal.com - Validación: API Key: {bool(calendar_api_key)}, Event ID: {bool(calendar_event_id)}, URL: {bool(calendar_booking_url)}")
                    
                    if calendar_api_key and calendar_event_id and calendar_booking_url:
                        # Validar API key con Cal.com (opcional, guarda incluso si falla)
                        api_key_valid = False
                        try:
                            headers = {
                                'Authorization': f'Bearer {calendar_api_key}',
                                'cal-api-version': '2024-06-14',
                                'Content-Type': 'application/json'
                            }
                            response = requests.get('https://api.cal.com/v2/schedules/default', headers=headers, timeout=10)
                            
                            if response.status_code == 200:
                                api_key_valid = True
                                logger.info(f"✅ Cal.com API - API Key válida")
                            else:
                                logger.warning(f"⚠️ Cal.com API - Error {response.status_code}: {response.text}")
                                logger.warning(f"⚠️ Guardando de todas formas...")
                        except requests.exceptions.RequestException as e:
                            logger.warning(f"⚠️ Error al conectar con Cal.com API: {str(e)}")
                            logger.warning(f"⚠️ Guardando de todas formas...")
                        
                        # Parsear la URL para extraer username y event slug
                        # Soporta: https://cal.com/usuario/evento, cal.com/usuario/evento, https://app.cal.com/usuario/evento
                        url_clean = calendar_booking_url.replace('https://', '').replace('http://', '').strip('/')
                        url_parts = url_clean.split('/')
                        
                        if len(url_parts) >= 2:
                            # Extraer username y slug (últimos 2 elementos)
                            calendar_username = url_parts[-2]
                            calendar_event_slug = url_parts[-1]
                            
                            # Asegurar que la URL tenga https://
                            if not calendar_booking_url.startswith('http'):
                                calendar_booking_url = f'https://{calendar_booking_url}'
                            
                            # Guardar configuración
                            company.calendar_provider = 'calcom'
                            company.calendar_api_key = calendar_api_key
                            company.calendar_event_id = calendar_event_id
                            company.calendar_username = calendar_username
                            company.calendar_event_slug = calendar_event_slug
                            company.calendar_booking_url = calendar_booking_url
                            company.save(update_fields=[
                                'calendar_provider',
                                'calendar_api_key',
                                'calendar_event_id',
                                'calendar_username',
                                'calendar_event_slug',
                                'calendar_booking_url'
                            ])
                            
                            logger.info(f"✅ Integración de Cal.com configurada para {company.name}")
                            logger.info(f"✅ API Key guardado: {calendar_api_key[:20]}...")
                            logger.info(f"✅ Event ID: {calendar_event_id}")
                            logger.info(f"✅ Username: {calendar_username}")
                            logger.info(f"✅ Event Slug: {calendar_event_slug}")
                            logger.info(f"✅ Booking URL: {calendar_booking_url}")
                            
                            if api_key_valid:
                                messages.success(request, f'Integración con Cal.com configurada y validada correctamente.')
                            else:
                                messages.warning(request, f'Integración guardada pero no se pudo validar la API Key. Verifica que sea correcta.')
                        else:
                            logger.error(f"❌ URL inválida. Formato esperado: https://cal.com/usuario/evento")
                            messages.error(request, 'URL inválida. Formato esperado: https://cal.com/usuario/nombre-evento')
                    else:
                        if calendar_api_key or calendar_event_id or calendar_booking_url:
                            logger.warning(f"⚠️ Cal.com incompleto - API Key: {bool(calendar_api_key)}, Event ID: {bool(calendar_event_id)}, URL: {bool(calendar_booking_url)}")
                            messages.warning(request, 'Por favor completa todos los campos de Cal.com para habilitar la integración')
                else:
                    logger.info(f"🔍 DEBUG Cal.com - Checkbox NO marcado")
                    # Si se deshabilita, limpiar los datos
                    if company.calendar_api_key or company.calendar_booking_url:
                        company.calendar_provider = ''
                        company.calendar_api_key = ''
                        company.calendar_event_id = ''
                        company.calendar_username = ''
                        company.calendar_event_slug = ''
                        company.calendar_booking_url = ''
                        company.save(update_fields=[
                            'calendar_provider',
                            'calendar_api_key',
                            'calendar_event_id',
                            'calendar_username',
                            'calendar_event_slug',
                            'calendar_booking_url'
                        ])
                        logger.info(f"🔄 Integración de Cal.com deshabilitada para {company.name}")
                
                # Procesar archivos subidos
                files = request.FILES.getlist('documents')
                
                if files:
                    # ➕ MODO AGREGAR: Solo agregar archivos nuevos, nunca eliminar automáticamente
                    logger.info("➕ Procesando archivos nuevos...")
                    
                    # Obtener documentos actuales en DB
                    current_documents = bot_config.documents.all()
                    current_filenames = {doc.filename for doc in current_documents}
                    logger.info(f"   📂 Documentos actuales en DB: {current_filenames}")
                    
                    # Obtener archivos del form
                    new_filenames = {file.name for file in files}
                    logger.info(f"   📤 Archivos recibidos: {new_filenames}")
                    
                    # Identificar archivos nuevos (no están en DB)
                    files_to_process = [file for file in files 
                                       if file.name not in current_filenames]
                    
                    if files_to_process:
                        logger.info(f"   ➕ Archivos nuevos a procesar: {len(files_to_process)}")
                    else:
                        logger.info("   ℹ️ No hay archivos nuevos para procesar (todos ya existen)")
                        messages.info(request, 'Los archivos seleccionados ya existen en tu biblioteca.')
                        return redirect('bot_builder:configure')
                    
                    # Validar cantidad total de archivos
                    documents_count = current_documents.count()
                    if documents_count + len(files_to_process) > max_documents:
                        messages.error(request, f'Solo puedes tener {max_documents} documentos en total. Actualmente tienes {documents_count}. Elimina algunos antes de agregar más.')
                        return redirect('bot_builder:configure')
                    
                    # Procesar solo archivos NUEVOS
                    minio_service = MinioService()
                    analyzer = DocumentAnalyzer()
                    
                    total_tokens = 0
                    total_cost = 0
                    files_uploaded = 0
                    
                    for file in files_to_process:
                        # Validar tipo de archivo PRIMERO
                        file_ext = os.path.splitext(file.name)[1].lower()
                        if file_ext not in Document.ALLOWED_FILE_TYPES:
                            logger.warning(f"❌ {file.name}: Formato no permitido. Solo se aceptan {', '.join(Document.ALLOWED_FILE_TYPES)}")
                            messages.error(request, f'❌ {file.name}: Solo se aceptan archivos {", ".join(Document.ALLOWED_FILE_TYPES)}')
                            continue
                        
                        # Validar tamaño (80 KB máximo)
                        if file.size > Document.MAX_FILE_SIZE_BYTES:
                            size_kb = round(file.size / 1024, 2)
                            logger.warning(f"❌ {file.name}: Excede el tamaño máximo de {Document.MAX_FILE_SIZE_KB}KB (archivo: {size_kb}KB)")
                            messages.error(request, f'❌ {file.name}: Excede el tamaño máximo de {Document.MAX_FILE_SIZE_KB}KB (tu archivo: {size_kb}KB)')
                            continue
                        
                        # ANÁLISIS PROFUNDO DEL DOCUMENTO
                        logger.info(f"📄 Analizando documento: {file.name}")
                        analysis = analyzer.analyze_document(file, file.name)
                        
                        if not analysis['is_valid']:
                            logger.error(f"❌ {file.name}: {analysis['error']}")
                            continue
                        
                        stats = analysis['stats']
                        estimated_tokens = analyzer.estimate_tokens(stats['text_length'])
                        estimated_cost = analyzer.estimate_cost(stats['text_length'])
                        
                        total_tokens += estimated_tokens
                        total_cost += estimated_cost
                        
                        # Log detallado
                        logger.info(f"""
                        ✅ Documento analizado exitosamente:
                           - Archivo: {file.name}
                           - Páginas: {stats['pages']}
                           - Caracteres: {stats['text_length']:,}
                           - Palabras: {stats['word_count']:,}
                           - Tokens estimados: {estimated_tokens:,}
                           - Costo estimado: ${estimated_cost:.4f}
                           - Tiene imágenes: {'Sí' if stats.get('has_images') else 'No'}
                        """)
                        
                        # Subir a MinIO con estructura: company_id/filename
                        try:
                            object_name = f"{company.id}/{file.name}"
                            upload_result = minio_service.upload_file(file, object_name)
                            
                            # Crear registro del documento con metadatos
                            document = Document.objects.create(
                                bot_config=bot_config,
                                filename=file.name,
                                file_type=file_ext,
                                minio_path=upload_result['object_name'],
                                file_size_bytes=file.size,
                                processing_status='processing',  # Cambiar a processing mientras se vectoriza
                                metadata={
                                    'pages': stats['pages'],
                                    'text_length': stats['text_length'],
                                    'word_count': stats['word_count'],
                                    'estimated_tokens': estimated_tokens,
                                    'estimated_cost': estimated_cost,
                                    'has_images': stats.get('has_images', False),
                                }
                            )
                            
                            files_uploaded += 1
                            logger.info(f"✅ Documento {file.name} subido exitosamente para empresa {company.name}")
                            
                            # Enviar documento al webhook de n8n para vectorización
                            try:
                                # Reabrir el archivo para enviarlo
                                file.seek(0)
                                
                                # Obtener Chatwoot account ID de la empresa
                                chatwoot_account_id = company.chatwoot_account_id if hasattr(company, 'chatwoot_account_id') else None
                                
                                n8n_service = N8NService()
                                
                                document_data = {
                                    'file': file,
                                    'filename': file.name,
                                    'document_id': document.id,  # ← ID para identificar vectores en pgvector
                                    'company_id': company.id,
                                    'company_name': company.name,
                                    'bot_name': bot_config.name,
                                    'chatwoot_account_id': chatwoot_account_id,
                                    'chatwoot_access_token': getattr(company, 'chatwoot_access_token', ''),
                                    'minio_path': upload_result['object_name'],
                                    'metadata': {
                                        'pages': stats['pages'],
                                        'text_length': stats['text_length'],
                                        'word_count': stats['word_count'],
                                        'estimated_tokens': estimated_tokens,
                                        'estimated_cost': estimated_cost,
                                    }
                                }
                                
                                # Enviar de forma asíncrona
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                webhook_result = loop.run_until_complete(
                                    n8n_service.send_document_for_vectorization(document_data)
                                )
                                loop.close()
                                
                                logger.info(f"✅ Documento {file.name} enviado al webhook de vectorización")
                                
                                # Actualizar estado a completado si el webhook fue exitoso
                                document.processing_status = 'completed'
                                document.save()
                                
                            except Exception as webhook_error:
                                logger.error(f"⚠️ Error enviando documento {file.name} al webhook: {str(webhook_error)}")
                                # Actualizar documento con error pero no fallar la subida
                                document.processing_status = 'failed'
                                document.error_message = f"Error en vectorización: {str(webhook_error)}"
                                document.save()
                            
                        except Exception as e:
                            logger.error(f"❌ Error subiendo archivo {file.name}: {str(e)}")
                            continue
                    
                    # Log de resumen (solo en consola)
                    if files_uploaded > 0:
                        logger.info(f"📊 Resumen de carga:")
                        logger.info(f"   - Archivos subidos: {files_uploaded}")
                        logger.info(f"   - Total tokens estimados: {total_tokens:,}")
                        logger.info(f"   - Costo estimado total: ${total_cost:.4f}")
                
                messages.success(request, '¡Configuración del bot actualizada exitosamente!')
                return redirect('bot_builder:configure')
                
        except Exception as e:
            logger.error(f"Error al configurar bot: {str(e)}")
            messages.error(request, 'Ocurrió un error al guardar la configuración. Intenta nuevamente.')
            return redirect('bot_builder:configure')
    
    # Obtener información del plan
    plan_name = "Sin plan"
    is_trial = False
    
    # Primero verificar si tiene suscripción activa
    if hasattr(company, 'subscription') and company.subscription and hasattr(company.subscription, 'plan') and company.subscription.plan:
        plan_name = company.subscription.plan.name
        logger.info(f"🔍 Empresa {company.name} tiene suscripción: {plan_name}")
    else:
        # Si no tiene suscripción, verificar si está en trial
        logger.info(f"🔍 Empresa {company.name} sin suscripción, verificando trial...")
        
        # Verificar si existe trial y está activo
        if hasattr(company, 'trial') and company.trial:
            from django.utils import timezone
            from datetime import date
            
            trial_obj = company.trial
            # Verificar que el trial esté activo (end_date en el futuro)
            # Convertir end_date a date si es datetime
            trial_end_date = trial_obj.end_date.date() if hasattr(trial_obj.end_date, 'date') else trial_obj.end_date
            today = date.today()
            
            if trial_end_date and trial_end_date >= today:
                is_trial = True
                plan_name = "Trial Activo"
                logger.info(f"✅ Empresa {company.name} está en TRIAL activo hasta {trial_end_date}")
            else:
                logger.info(f"❌ Empresa {company.name} tiene trial pero expiró el {trial_end_date}")
        else:
            logger.info(f"❌ Empresa {company.name} no tiene trial")
    
    logger.info(f"📊 Empresa {company.name} - is_trial: {is_trial}, plan_name: {plan_name}")
    
    context = {
        'bot_config': bot_config,
        'bot_types': bot_types,
        'documents': documents,
        'documents_count': documents_count,
        'max_documents': max_documents,
        'industry_sectors': industry_sectors,
        'tone_options': tone_options,
        'max_file_size_kb': Document.MAX_FILE_SIZE_KB,
        'allowed_file_types': ', '.join(Document.ALLOWED_FILE_TYPES),
        'plan_name': plan_name,
        'is_trial': is_trial,
        'company': company,  # Agregar company al contexto para Calendly
    }
    
    return render(request, 'bot_builder/configure.html', context)


@login_required
def delete_document(request, document_id):
    """Eliminar un documento del bot (DB + MinIO + Vector Store)"""
    if request.method == 'POST':
        try:
            document = get_object_or_404(Document, id=document_id, bot_config__company=request.user.company)
            company = request.user.company
            filename = document.filename
            
            logger.info(f"🗑️ Iniciando eliminación de documento: {filename} (ID: {document_id})")
            
            # 1. Eliminar vectores de pgvector via n8n
            try:
                n8n_service = N8NService()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                delete_result = loop.run_until_complete(
                    n8n_service.delete_document_from_vectorstore({
                        'document_id': document.id,
                        'company_id': company.id,
                        'filename': filename,
                        'bot_name': document.bot_config.name if document.bot_config else '',
                        'chatwoot_account_id': company.chatwoot_account_id,
                        'chatwoot_access_token': getattr(company, 'chatwoot_access_token', ''),
                    })
                )
                loop.close()
                logger.info(f"   ✅ Vectores eliminados de pgvector: {filename}")
            except Exception as vector_error:
                logger.warning(f"   ⚠️ Error eliminando vectores (puede no existir aún): {vector_error}")
            
            # 2. Eliminar archivo de MinIO
            try:
                minio_service = MinioService()
                minio_service.delete_file(document.minio_path)
                logger.info(f"   ✅ Archivo eliminado de MinIO: {document.minio_path}")
            except Exception as minio_error:
                logger.warning(f"   ⚠️ Error eliminando de MinIO: {minio_error}")
            
            # 3. Eliminar registro de DB
            document.delete()
            logger.info(f"   ✅ Registro eliminado de DB: {filename}")
            
            logger.info(f"✅ Documento {filename} eliminado completamente")
            messages.success(request, f'Documento {filename} eliminado exitosamente.')
            return JsonResponse({'success': True})
            
        except Exception as e:
            logger.error(f"❌ Error eliminando documento: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)
