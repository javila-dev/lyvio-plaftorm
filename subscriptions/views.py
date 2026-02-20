from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.conf import settings
from django.forms.models import model_to_dict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
import requests

from .models import Subscription, Plan, Invoice, DiscountCampaign
from .wompi_service import WompiService
from accounts.models import Company, User, Trial
from accounts.forms import BillingForm
from accounts.models import BillingInfo


@login_required(login_url='dashboard:login')
def billing_info(request):
    """Crear/Editar información de facturación para la empresa del usuario."""
    company, redirect_response = get_user_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    try:
        billing = company.billing_info
    except BillingInfo.DoesNotExist:
        billing = None

    if request.method == 'POST':
        form = BillingForm(request.POST, instance=billing)
        if form.is_valid():
            billing_obj = form.save(commit=False)
            billing_obj.company = company
            billing_obj.save()
            messages.success(request, 'Datos de facturación guardados correctamente')
            return redirect('dashboard:dashboard')
    else:
        form = BillingForm(instance=billing)

    context = {
        'company': company,
        'form': form,
    }
    return render(request, 'subscriptions/billing_info_form.html', context)

logger = logging.getLogger(__name__)


# ==================== FUNCIONES AUXILIARES ====================

def get_user_company_or_redirect(request):
    """
    Obtiene la empresa del usuario o redirige al login con mensaje de error
    """
    if not hasattr(request.user, 'company') or not request.user.company:
        messages.error(request, 'Tu cuenta no está asociada a ninguna empresa. Contacta con soporte.')
        return None, redirect('dashboard:login')
    return request.user.company, None


def notify_account_reactivation(company):
    """
    Reactiva la cuenta en Chatwoot cuando una cuenta suspendida es reactivada tras un pago exitoso
    
    Args:
        company: Objeto Company con la información de la cuenta reactivada
    """
    if not company.chatwoot_account_id:
        logger.warning(f"⚠️ Company {company.name} no tiene chatwoot_account_id configurado")
        return False
    
    chatwoot_api_url = settings.CHATWOOT_API_URL
    platform_token = settings.LYVIO_PLATFORM_TOKEN
    account_id = company.chatwoot_account_id
    
    url = f"{chatwoot_api_url}/platform/api/v1/accounts/{account_id}"
    
    try:
        payload = {
            "status": "active"
        }
        
        headers = {
            "api_access_token": platform_token,
            "Content-Type": "application/json"
        }
        
        logger.info(f"🔔 Reactivando cuenta en Chatwoot:")
        logger.info(f"   URL: {url}")
        logger.info(f"   Company: {company.name} (ID: {company.id})")
        logger.info(f"   Chatwoot Account ID: {account_id}")
        
        response = requests.patch(
            url,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Cuenta reactivada en Chatwoot exitosamente")
            logger.info(f"   Response: {response.text}")
            return True
        else:
            logger.warning(f"⚠️ Error al reactivar cuenta en Chatwoot: {response.status_code}")
            logger.warning(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout al reactivar cuenta en Chatwoot (>10s)")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error al reactivar cuenta en Chatwoot: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado al reactivar cuenta: {str(e)}")
        return False


def notify_plan_update(company, plan, billing_cycle):
    """
    Envía información del cambio de plan a n8n para sincronizar límites en Chatwoot.
    """
    webhook_url = "https://n8n.2asoft.tech/webhook/update-plan"

    plan_data = model_to_dict(plan)
    plan_data['id'] = plan.id

    serializable_plan = {}
    for key, value in plan_data.items():
        if isinstance(value, Decimal):
            serializable_plan[key] = float(value)
        else:
            serializable_plan[key] = value

    payload = {
        "company_id": company.id,
        "chatwoot_account_id": getattr(company, "chatwoot_account_id", ""),
        "chatwoot_access_token": getattr(company, "chatwoot_access_token", ""),
        "lyvio_platform_token": getattr(settings, "LYVIO_PLATFORM_TOKEN", ""),
        "plan": serializable_plan,
        "billing_cycle": billing_cycle,
    }

    try:
        logger.info(f"📡 Enviando actualización de plan a n8n: {webhook_url}")
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code < 400:
            logger.info("✅ Webhook de actualización de plan enviado correctamente")
            return True

        logger.error(
            f"❌ Error al enviar webhook de actualización de plan "
            f"(status={response.status_code}): {response.text}"
        )
        return False
    except requests.RequestException as exc:
        logger.error(f"❌ Excepción al enviar webhook de actualización de plan: {exc}")
        return False


# ==================== VISTAS DE AUTENTICACIÓN ====================

def billing_login(request):
    """
    Login específico para portal de billing
    
    Redirige a app.lyvio.io para el login real
    Este endpoint no debería mostrar un formulario de login propio
    """
    # Si ya está autenticado, llevarlo al dashboard
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    
    # Si no está autenticado, redirigir a la aplicación principal de Lyvio
    lyvio_url = getattr(settings, 'LYVIO_APP_URL', 'https://app.lyvio.io')
    messages.info(request, 'Por favor inicia sesión en Lyvio para acceder al dashboard.')
    return redirect(lyvio_url)


def billing_logout(request):
    """Logout del portal de billing - redirige a Lyvio"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente')
    
    # Redirigir a la página principal de Lyvio
    lyvio_url = getattr(settings, 'CHATWOOT_API_URL', 'https://app.lyvio.io')
    return redirect(lyvio_url)


# ==================== VISTAS DEL PORTAL DE BILLING ====================

@login_required(login_url='dashboard:login')
def billing_dashboard(request):
    """Dashboard principal del portal de billing"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
            
        subscription = getattr(company, 'subscription', None)
        trial = getattr(company, 'trial', None)
        
        context = {
            'company': company,
            'subscription': subscription,
            'trial': trial,
            'user': request.user,
        }
        
        if subscription:
            # Información del plan actual
            context.update({
                'plan': subscription.plan,
                'days_until_expiry': (subscription.current_period_end - timezone.now()).days,
                'is_trial': subscription.status == 'trial',
                'is_active': subscription.status == 'active',
                'next_billing_date': subscription.current_period_end,
            })
            
            # Última factura
            last_invoice = subscription.invoices.filter(status='paid').first()
            context['last_invoice'] = last_invoice
            
            # Próxima factura (estimada)
            if subscription.status == 'active':
                next_amount = subscription.plan.price_monthly if subscription.billing_cycle == 'monthly' else subscription.plan.price_yearly
                context['next_invoice_amount'] = next_amount
        else:
            # Si no hay suscripción, mostrar información del trial y planes disponibles
            available_plans = Plan.objects.filter(is_active=True).order_by('price_monthly')
            context.update({
                'available_plans': available_plans,
                'show_activation_flow': True,
            })
            
            if trial:
                context.update({
                    'trial_days_remaining': trial.days_remaining,
                    'trial_expired': not trial.is_active,
                    'trial_usage': {
                        'messages': (trial.current_messages / trial.max_messages) * 100 if trial.max_messages > 0 else 0,
                        'conversations': (trial.current_conversations / trial.max_conversations) * 100 if trial.max_conversations > 0 else 0,
                        'documents': (trial.current_documents / trial.max_documents) * 100 if trial.max_documents > 0 else 0,
                    }
                })
        
        return render(request, 'subscriptions/dashboard.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa asociada a tu cuenta')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def billing_plan_details(request):
    """Detalles del plan actual y opciones de upgrade/downgrade"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        subscription = getattr(company, 'subscription', None)
        available_plans = Plan.objects.filter(is_active=True).order_by('price_monthly')
        
        context = {
            'company': company,
            'subscription': subscription,
            'available_plans': available_plans,
            'current_plan': subscription.plan if subscription else None,
        }
        
        return render(request, 'subscriptions/plan_details.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def billing_payment_history(request):
    """Historial de pagos y facturas"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        subscription = getattr(company, 'subscription', None)
        
        if not subscription:
            messages.warning(request, 'No tienes una suscripción activa')
            return redirect('dashboard:dashboard')
        
        # Obtener facturas con paginación
        invoices_list = subscription.invoices.all().order_by('-created_at')
        paginator = Paginator(invoices_list, 10)  # 10 facturas por página
        
        page_number = request.GET.get('page')
        invoices = paginator.get_page(page_number)
        
        # Estadísticas
        total_paid = subscription.invoices.filter(status='paid').count()
        total_amount_paid = sum(
            invoice.amount for invoice in subscription.invoices.filter(status='paid')
        )
        
        context = {
            'company': company,
            'subscription': subscription,
            'invoices': invoices,
            'total_paid': total_paid,
            'total_amount_paid': total_amount_paid,
        }
        
        return render(request, 'subscriptions/payment_history.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def billing_invoice_detail(request, invoice_id):
    """Detalle de una factura específica"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        subscription = getattr(company, 'subscription', None)
        
        if not subscription:
            messages.error(request, 'No tienes una suscripción activa')
            return redirect('dashboard:dashboard')
        
        invoice = get_object_or_404(Invoice, id=invoice_id, subscription=subscription)
        
        # Calcular valores de impuestos
        tax_amount = float(invoice.amount) * 0.19  # 19% IVA
        total_amount = float(invoice.amount) * 1.19  # Subtotal + IVA
        
        context = {
            'company': company,
            'subscription': subscription,
            'invoice': invoice,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
        }
        
        return render(request, 'subscriptions/invoice_detail.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


def _show_card_form(request, company, plan, trial, billing_cycle):
    """Muestra el formulario para ingresar datos de tarjeta"""
    # Determinar el precio según el ciclo de facturación
    if billing_cycle == 'yearly' and plan.price_yearly:
        amount = plan.price_yearly
    else:
        amount = plan.price_monthly
        billing_cycle = 'monthly'
    
    # Verificar descuentos aplicables
    applicable_discount = None
    for discount in DiscountCampaign.objects.filter(is_active=True):
        if discount.can_apply_to_user(company, trial):
            # Verificar precio mínimo si aplica
            if discount.minimum_plan_price and amount < discount.minimum_plan_price:
                continue
            applicable_discount = discount
            break
    
    original_amount = amount
    discount_amount = Decimal('0')
    discount_info = None
    
    if applicable_discount:
        discount_amount = applicable_discount.calculate_discount(amount)
        amount = amount - discount_amount
        discount_info = {
            'campaign': applicable_discount,
            'discount_amount': discount_amount,
        }
    
    # Generar años para el formulario (próximos 15 años)
    current_year = timezone.now().year
    years = [str(year)[2:] for year in range(current_year, current_year + 16)]
    
    # Obtener tokens de aceptación y permalinks de Wompi
    wompi_service = WompiService()
    acceptance_data = wompi_service.create_acceptance_token()
    
    context = {
        'company': company,
        'plan': plan,
        'trial': trial,
        'billing_cycle': billing_cycle,
        'original_amount': original_amount,
        'final_amount': amount,
        'discount_info': discount_info,
        'years': years,
        'terms_permalink': acceptance_data.get('terms_permalink'),
        'personal_data_permalink': acceptance_data.get('personal_data_permalink'),
    }
    
    return render(request, 'subscriptions/card_form_professional.html', context)


def _process_card_payment(request, company, plan, trial):
    """Procesa el pago con los datos de tarjeta ingresados"""
    try:
        # Obtener datos del formulario
        card_data = {
            'number': request.POST.get('card_number', '').replace(' ', ''),
            'exp_month': request.POST.get('exp_month'),
            'exp_year': request.POST.get('exp_year'), 
            'cvc': request.POST.get('cvc'),
            'card_holder': request.POST.get('card_holder')
        }
        
        billing_cycle = request.POST.get('billing_cycle', 'monthly')
        
        # Determinar el precio según el ciclo de facturación
        if billing_cycle == 'yearly' and plan.price_yearly:
            amount = plan.price_yearly
        else:
            amount = plan.price_monthly
            billing_cycle = 'monthly'
        
        # Verificar descuentos aplicables
        applicable_discount = None
        for discount in DiscountCampaign.objects.filter(is_active=True):
            if discount.can_apply_to_user(company, trial):
                if discount.minimum_plan_price and amount < discount.minimum_plan_price:
                    continue
                applicable_discount = discount
                break
        
        original_amount = amount
        if applicable_discount:
            discount_amount = applicable_discount.calculate_discount(amount)
            amount = amount - discount_amount
        
        # Procesar pago con Wompi
        wompi_service = WompiService()
        
        # 1. Obtener tokens de aceptación (acceptance_token y accept_personal_auth)
        logger.info(f"🔑 Obteniendo tokens de aceptación para {request.user.email}")
        acceptance_tokens = wompi_service.create_acceptance_token()
        logger.info(f"✅ Tokens obtenidos: acceptance_token y accept_personal_auth")
        
        # 2. Tokenizar tarjeta
        logger.info(f"🔒 Tokenizando tarjeta terminada en {card_data['number'][-4:]}")
        card_token = wompi_service.tokenize_card(card_data)
        logger.info(f"✅ Token obtenido: {card_token}")
        
        # 3. Crear fuente de pago (payment_source) - PASO CRÍTICO para pagos recurrentes
        logger.info(f"💾 Creando fuente de pago para {request.user.email}")
        payment_source_data = wompi_service.create_payment_source(
            token=card_token,
            customer_email=request.user.email,
            acceptance_tokens=acceptance_tokens
        )
        payment_source_id = payment_source_data['id']
        logger.info(f"✅ Fuente de pago creada: {payment_source_id}")
        
        # Extraer información de la tarjeta del payment_source
        public_data = payment_source_data.get('public_data', {})
        card_info = {
            'brand': public_data.get('brand', ''),
            'last_four': public_data.get('last_four', ''),
            'exp_month': public_data.get('exp_month', ''),
            'exp_year': public_data.get('exp_year', '')
        }
        logger.info(f"💳 Info de tarjeta guardada: {card_info['brand']} terminada en {card_info['last_four']}")
        
        # 4. Crear transacción usando el payment_source_id
        import time
        timestamp = int(time.time())
        reference = f"LYVIO-FIRST-{plan.id}-{request.user.id}-{timestamp}"
        
        logger.info(f"💳 Procesando primer cobro con payment_source_id: ${amount}")
        logger.info(f"📝 Referencia generada: {reference}")
        logger.info(f"👤 Customer email: {request.user.email}")
        logger.info(f"🏢 Empresa: {company.name} (ID: {company.id})")
        
        transaction_result = wompi_service.create_recurring_transaction(
            payment_source_id=payment_source_id,
            amount=amount,
            customer_email=request.user.email,
            reference=reference
        )
        
        # 5. Verificar el estado inicial del cobro
        transaction_status = transaction_result.get('status')
        transaction_id = transaction_result.get('id')
        
        logger.info(f"🔍 Resultado inicial del cobro: {transaction_status} (ID: {transaction_id})")
        logger.info(f"💾 Payment source guardado: {payment_source_id}")
        
        # 6. ESPERAR confirmación de Wompi consultando el estado
        max_attempts = 15  # 15 intentos = 30 segundos
        wait_seconds = 2   # Esperar 2 segundos entre consultas
        
        logger.info(f"⏳ Esperando confirmación de Wompi (máximo {max_attempts * wait_seconds} segundos)...")
        
        for attempt in range(max_attempts):
            # Consultar estado actual de la transacción
            current_transaction = wompi_service.get_transaction_status(transaction_id)
            transaction_status = current_transaction.get('status')
            
            logger.info(f"   Intento {attempt + 1}/{max_attempts}: Status = {transaction_status}")
            
            # Estados finales
            if transaction_status == 'APPROVED':
                logger.info(f"✅ Pago APROBADO después de {attempt + 1} intentos")
                break
            elif transaction_status in ['DECLINED', 'ERROR', 'VOIDED']:
                error_msg = f"Pago rechazado por el banco: {transaction_status}"
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # Si aún está PENDING, esperar antes del siguiente intento
            if attempt < max_attempts - 1:  # No esperar en el último intento
                time.sleep(wait_seconds)
        
        # Verificar estado final después del polling
        # Calcular fechas según billing_cycle
        if billing_cycle == 'yearly':
            period_days = 365
        else:
            period_days = 30
        
        # Determinar estado de la suscripción según el resultado del polling
        if transaction_status == 'APPROVED':
            subscription_status = 'active'
            success_message = f'¡Suscripción activada exitosamente! Se ha cobrado ${amount:,.0f} COP y tu suscripción al plan {plan.name} está activa.'
            logger.info(f"✅ Pago APROBADO después de polling - Creando suscripción ACTIVA")
        
        elif transaction_status == 'PENDING':
            # ⚠️ IMPORTANTE: Si después de 30 segundos sigue PENDING, crear suscripción 
            # en estado 'pending' y dejar que el webhook la active cuando Wompi responda
            subscription_status = 'pending'
            success_message = (
                f'Tu pago está siendo procesado por el banco. '
                f'La suscripción quedará activa automáticamente cuando se confirme el pago. '
                f'Esto puede tomar algunos minutos. Te notificaremos por email.'
            )
            logger.warning(
                f"⏳ Pago AÚN PENDING después de {max_attempts * wait_seconds}s - "
                f"Creando suscripción en estado PENDING. El webhook la activará."
            )
        
        elif transaction_status in ['DECLINED', 'ERROR', 'VOIDED']:
            # Pago rechazado - no crear suscripción
            error_msg = f"Pago rechazado por el banco: {transaction_status}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        else:
            # Estado desconocido - no crear suscripción por seguridad
            error_msg = f"Estado inesperado de la transacción: {transaction_status}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # Crear la suscripción ANTES de cualquier otra cosa
        logger.info(f"💾 Guardando suscripción en base de datos...")
        
        subscription = Subscription.objects.create(
            company=company,
            plan=plan,
            status=subscription_status,
            billing_cycle=billing_cycle,
            wompi_customer_email=request.user.email,
            wompi_subscription_id=transaction_id,  # ID de la primera transacción
            payment_source_id=payment_source_id,  # Fuente de pago para cobros futuros
            card_brand=card_info['brand'],
            card_last_four=card_info['last_four'],
            card_exp_month=card_info['exp_month'],
            card_exp_year=card_info['exp_year'],
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=period_days)
        )
        
        # Forzar commit a la base de datos antes de continuar
        from django.db import transaction as db_transaction
        db_transaction.commit()
        
        logger.info(f"✅ Suscripción #{subscription.id} guardada en DB exitosamente")
        
        # Marcar trial como convertido si existe
        if trial:
            trial.status = 'converted'
            trial.save()
        
        # Incrementar uso de campaña de descuento si se aplicó
        if applicable_discount:
            applicable_discount.current_uses += 1
            applicable_discount.save()
        
        logger.info(f"✅ Suscripción creada exitosamente:")
        logger.info(f"   ID: {subscription.id}")
        logger.info(f"   Status: {subscription_status}")
        logger.info(f"   Empresa: {company.name}")
        logger.info(f"   Email: {request.user.email}")
        logger.info(f"   wompi_subscription_id: {transaction_id}")
        logger.info(f"   payment_source_id: {payment_source_id}")
        logger.info(f"   Plan: {plan.name}")
        logger.info(f"   🎯 El webhook debe buscar por customer_email={request.user.email}")
        
        messages.success(request, success_message)
        return redirect('dashboard:dashboard')
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error procesando pago con tarjeta: {error_msg}")
        
        # Mensajes más amigables para el usuario
        if 'tokeniza' in error_msg.lower():
            user_message = 'Error validando los datos de la tarjeta. Verifica que estén correctos.'
        elif 'fuente de pago' in error_msg.lower():
            user_message = 'Error procesando la tarjeta. Intenta con otra tarjeta.'
        elif 'rechazado' in error_msg.lower() or 'DECLINED' in error_msg:
            user_message = 'Pago rechazado. Verifica que tu tarjeta tenga fondos suficientes e intenta nuevamente.'
        elif 'PENDING' in error_msg:
            user_message = 'El pago está siendo procesado. Por favor espera unos minutos e intenta nuevamente.'
        else:
            user_message = f'Error al procesar el pago: {error_msg}'
        
        messages.error(request, user_message)
        return redirect('dashboard:activate_plan', plan_id=plan.id)


@login_required(login_url='dashboard:login')
def billing_activate_plan(request, plan_id):
    """Activar un plan para una empresa sin suscripción activa"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        
        subscription = getattr(company, 'subscription', None)
        if subscription:
            messages.info(request, 'Ya tienes una suscripción activa')
            return redirect('dashboard:dashboard')
            
        plan = get_object_or_404(Plan, id=plan_id, is_active=True)
        trial = getattr(company, 'trial', None)
        
        if request.method == 'POST':
            # Verificar si es envío de datos de tarjeta o selección de plan
            # Antes de permitir el proceso de pago, verificar que la empresa tenga BillingInfo
            if not hasattr(company, 'billing_info'):
                messages.error(request, 'Debes completar los datos de facturación antes de activar una suscripción.')
                return redirect('dashboard:billing_info')

            if 'card_number' in request.POST:
                # Procesar datos de tarjeta y crear suscripción
                return _process_card_payment(request, company, plan, trial)
            else:
                # Mostrar formulario de tarjeta
                billing_cycle = request.POST.get('billing_cycle', 'monthly')
                return _show_card_form(request, company, plan, trial, billing_cycle)
        
        # Para GET request, mostrar la selección de plan (mantiene la funcionalidad actual)
        # Calcular precios y descuentos
        monthly_price = plan.price_monthly
        yearly_price = plan.price_yearly if plan.price_yearly else monthly_price * 12
        
        # Verificar descuentos aplicables
        applicable_discount = None
        for discount in DiscountCampaign.objects.filter(is_active=True):
            if discount.can_apply_to_user(company, trial):
                # Verificar precio mínimo para monthly
                if discount.minimum_plan_price and monthly_price < discount.minimum_plan_price:
                    continue
                applicable_discount = discount
                break
        
        discount_info = None
        if applicable_discount:
            monthly_discount = applicable_discount.calculate_discount(monthly_price)
            yearly_discount = applicable_discount.calculate_discount(yearly_price)
            
            discount_info = {
                'campaign': applicable_discount,
                'monthly_discount': monthly_discount,
                'yearly_discount': yearly_discount,
                'monthly_final': monthly_price - monthly_discount,
                'yearly_final': yearly_price - yearly_discount,
            }
        
        context = {
            'company': company,
            'plan': plan,
            'trial': trial,
            'trial_expired': trial and not trial.is_active if trial else False,
            'monthly_price': monthly_price,
            'yearly_price': yearly_price,
            'discount_info': discount_info,
        }
        
        return render(request, 'subscriptions/activate_plan.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def billing_upgrade_plan(request, plan_id):
    """Actualizar a un plan superior"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        subscription = getattr(company, 'subscription', None)
        new_plan = get_object_or_404(Plan, id=plan_id, is_active=True)
        
        if not subscription:
            messages.error(request, 'No tienes una suscripción activa')
            return redirect('dashboard:dashboard')
        
        # Verificar que tenga payment source
        if not subscription.payment_source_id:
            messages.error(request, 'No tienes un método de pago registrado. Por favor actualiza tu método de pago primero.')
            return redirect('dashboard:dashboard')
        
        if request.method == 'POST':
            billing_cycle = request.POST.get('billing_cycle', 'monthly')
            
            try:
                amount = Decimal('0.00')

                if billing_cycle == 'yearly':
                    amount = Decimal(str(new_plan.price_yearly))
                else:
                    from calendar import monthrange
                    now = timezone.now()
                    days_in_month = monthrange(now.year, now.month)[1]
                    days_remaining = days_in_month - now.day + 1

                    current_plan = subscription.plan
                    price_difference = (
                        Decimal(str(new_plan.price_monthly)) -
                        Decimal(str(current_plan.price_monthly))
                    )

                    if subscription.status != 'active' or price_difference <= 0:
                        logger.info(
                            f"Suscripción no activa o sin diferencia de precio "
                            f"(status: {subscription.status}, price_diff: {price_difference}). "
                            f"Cobrando precio completo del nuevo plan."
                        )
                        amount = Decimal(str(new_plan.price_monthly))
                    else:
                        prorated = (price_difference / Decimal(days_in_month)) * Decimal(days_remaining)
                        amount = prorated

                amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if amount <= 0:
                    messages.error(request, 'El monto calculado para el upgrade no es válido.')
                    return redirect('dashboard:plan_details')

                amount_in_cents = int((amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

                import uuid
                reference = f"upgrade-{company.id}-{uuid.uuid4().hex[:8]}"

                wompi_service = WompiService()
                transaction = wompi_service.create_transaction(
                    amount_in_cents=amount_in_cents,
                    currency="COP",
                    customer_email=request.user.email,
                    payment_source_id=subscription.payment_source_id,
                    reference=reference
                )

                if not transaction:
                    messages.error(request, 'No se recibió respuesta del procesador de pago. Intenta nuevamente.')
                    return redirect('dashboard:plan_details')

                transaction_data = {}
                if isinstance(transaction, dict):
                    if isinstance(transaction.get('data'), dict):
                        transaction_data = transaction['data']
                    else:
                        transaction_data = transaction

                transaction_status = transaction_data.get('status') or transaction.get('status') if isinstance(transaction, dict) else None
                transaction_id = transaction_data.get('id') or transaction.get('id') if isinstance(transaction, dict) else None
                transaction_status_message = transaction_data.get('status_message') if isinstance(transaction_data, dict) else None
                if not transaction_status_message and isinstance(transaction, dict):
                    transaction_status_message = transaction.get('error', {}).get('message', '')

                if transaction_status in ['APPROVED', 'PENDING']:
                    webhook_success = notify_plan_update(company, new_plan, billing_cycle)
                    if not webhook_success:
                        messages.error(
                            request,
                            'El pago fue procesado pero no se pudo sincronizar el plan con la plataforma. '
                            'Contacta a soporte para completar el cambio.'
                        )
                        return redirect('dashboard:plan_details')

                    subscription.plan = new_plan
                    subscription.billing_cycle = billing_cycle
                    subscription.save()
                    
                    invoice_identifier = transaction_id or reference
                    existing_invoice = Invoice.objects.filter(
                        wompi_transaction_id=invoice_identifier
                    ).first()

                    if existing_invoice:
                        logger.info(
                            f"Factura ya registrada para transaction {invoice_identifier}; "
                            f"no se generará una nueva (probablemente creada por webhook)."
                        )
                    else:
                        Invoice.objects.create(
                            subscription=subscription,
                            amount=amount,
                            status='paid' if transaction_status == 'APPROVED' else 'pending',
                            paid_at=timezone.now() if transaction_status == 'APPROVED' else None,
                            wompi_transaction_id=invoice_identifier,
                            wompi_reference=reference
                        )
                    
                    messages.success(request, f'¡Plan actualizado exitosamente a {new_plan.name}!')
                    return redirect('dashboard:dashboard')
                else:
                    logger.error(
                        f"Wompi rechazó el upgrade (company={company.id}, plan={new_plan.id}). "
                        f"Status: {transaction_status}, Mensaje: {transaction_status_message}, Respuesta: {transaction}"
                    )
                    error_msg = 'El pago no pudo ser procesado. Por favor intenta nuevamente.'
                    if transaction_status_message:
                        error_msg = f'El pago fue rechazado: {transaction_status_message}'
                    messages.error(request, error_msg)
                    
            except Exception as e:
                logger.error(f"Error procesando upgrade: {e}")
                messages.error(request, 'Error al procesar el upgrade. Por favor intenta nuevamente.')
        
        # Calcular diferencias de precio
        current_monthly = subscription.plan.price_monthly
        new_monthly = new_plan.price_monthly
        price_difference = new_monthly - current_monthly
        
        context = {
            'company': company,
            'subscription': subscription,
            'new_plan': new_plan,
            'current_plan': subscription.plan,
            'price_difference': price_difference,
        }
        
        return render(request, 'subscriptions/upgrade_plan.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def billing_cancel_subscription(request):
    """Cancelar suscripción"""
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        subscription = getattr(company, 'subscription', None)
        
        if not subscription or subscription.status == 'cancelled':
            messages.warning(request, 'No tienes una suscripción activa para cancelar')
            return redirect('dashboard:dashboard')
        
        if request.method == 'POST':
            reason = request.POST.get('cancellation_reason', '')
            
            # Cancelar en el sistema
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
            subscription.save()
            
            # TODO: Cancelar en Wompi si es necesario
            
            messages.success(request, 'Tu suscripción ha sido cancelada. Tendrás acceso hasta el final del período de facturación actual.')
            return redirect('dashboard:dashboard')
        
        context = {
            'company': company,
            'subscription': subscription,
        }
        
        return render(request, 'subscriptions/cancel_subscription.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def reactivate_subscription(request):
    """
    ESCENARIO 1: Reactivar suscripción durante grace period (sin pago)
    
    Usuario cancela su suscripción pero antes de que expire el período:
    - Status actual: 'cancelled'
    - current_period_end: todavía no ha pasado
    - Acción: Cambiar status='active', limpiar cancelled_at
    - NO requiere pago (ya está pagado el período actual)
    - Notifica a N8N inmediatamente para restaurar features en Chatwoot
    """
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
            
        subscription = getattr(company, 'subscription', None)
        
        if not subscription:
            messages.error(request, 'No se encontró ninguna suscripción')
            return redirect('dashboard:dashboard')
        
        if subscription.status != 'cancelled':
            messages.warning(request, 'Tu suscripción no está cancelada')
            return redirect('dashboard:dashboard')
        
        # Verificar que estamos en grace period (período no expirado)
        if subscription.current_period_end and subscription.current_period_end.date() < timezone.now().date():
            messages.error(request, 'Tu suscripción ya expiró. Por favor renueva tu plan.')
            return redirect('subscriptions:renew_expired_subscription')
        
        if request.method == 'POST':
            # PASO 1: Notificar a N8N PRIMERO para restaurar features en Chatwoot
            # Si N8N falla, NO reactivamos en nuestra BD
            from dashboard.views import notify_n8n_subscription_reactivated
            
            logger.info(f"Iniciando reactivación de subscription {subscription.id} - Notificando a N8N primero")
            n8n_response = notify_n8n_subscription_reactivated(subscription)
            
            if not n8n_response:
                # N8N falló - NO reactivar en BD
                logger.error(f"N8N falló para reactivación de subscription {subscription.id} - Abortando reactivación")
                messages.error(
                    request, 
                    'No se pudo reactivar tu suscripción. El servicio de Chatwoot no respondió correctamente. '
                    'Por favor intenta nuevamente en unos minutos o contacta a soporte.'
                )
                return redirect('dashboard:dashboard')
            
            # PASO 2: N8N respondió OK - Ahora SÍ reactivar en nuestra BD
            subscription.status = 'active'
            subscription.cancelled_at = None
            subscription.save()
            
            logger.info(f"Subscription {subscription.id} reactivada exitosamente en BD tras confirmación de N8N para company {company.name}")
            
            messages.success(request, '¡Tu suscripción ha sido reactivada exitosamente! Tu cuenta de Chatwoot ya tiene acceso completo.')
            return redirect('dashboard:dashboard')
        
        # GET: Mostrar confirmación
        context = {
            'company': company,
            'subscription': subscription,
            'days_remaining': (subscription.current_period_end.date() - timezone.now().date()).days if subscription.current_period_end else 0,
        }
        
        return render(request, 'subscriptions/reactivate_subscription.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def renew_expired_subscription(request):
    """
    ESCENARIO 2: Renovar suscripción después de expiración (con pago)
    
    Suscripción expirada o suspendida:
    - Status actual: 'suspended' o 'cancelled' con current_period_end pasado
    - Acción: Validar payment_source, cobrar en Wompi, si APPROVED:
      * status='active'
      * Extender current_period_end según billing_cycle
      * Crear Invoice
    - Notifica a N8N inmediatamente para restaurar features en Chatwoot
    """
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
            
        subscription = getattr(company, 'subscription', None)
        
        if not subscription:
            messages.error(request, 'No se encontró ninguna suscripción')
            return redirect('dashboard:dashboard')
        
        if subscription.status == 'active':
            messages.warning(request, 'Tu suscripción ya está activa')
            return redirect('dashboard:dashboard')
        
        # Verificar que necesita renovación (expirada o suspendida)
        if subscription.status not in ['cancelled', 'suspended', 'past_due']:
            messages.warning(request, f'Estado de suscripción inválido: {subscription.status}')
            return redirect('dashboard:dashboard')
        
        # Calcular monto según billing_cycle
        if subscription.billing_cycle == 'yearly' and subscription.plan.price_yearly:
            amount = subscription.plan.price_yearly
        else:
            amount = subscription.plan.price_monthly
        
        if request.method == 'POST':
            # Validar información de facturación (usar hasattr para evitar RelatedObjectDoesNotExist)
            if not hasattr(company, 'billing_info') or not company.billing_info:
                messages.error(request, 'Debes completar tu información de facturación antes de renovar tu suscripción.')
                return redirect('dashboard:billing_info')
            
            # Validar que tiene payment_source_id (tarjeta guardada)
            if not subscription.payment_source_id:
                messages.error(request, 'No tienes un método de pago guardado. Por favor agrega una tarjeta de crédito para continuar.')
                return redirect('dashboard:dashboard')  # Redirige al dashboard donde puede actualizar su tarjeta
            
            # Intentar cobrar con Wompi usando payment_source_id guardado
            wompi_service = WompiService()
            
            try:
                import hashlib
                import time
                
                # Generar referencia única
                timestamp = int(time.time())
                reference = f"LYVIO-RENEW-{subscription.id}-{timestamp}"
                
                # Calcular firma de integridad
                currency = "COP"
                amount_in_cents = int(float(amount) * 100)
                integrity_string = f"{reference}{amount_in_cents}{currency}{settings.WOMPI_INTEGRITY_SECRET}"
                signature = hashlib.sha256(integrity_string.encode()).hexdigest()
                
                # Payload para Wompi
                transaction_data = {
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
                
                logger.info(f"Intentando cobrar renovación de subscription {subscription.id} - Amount: {amount}")
                
                # Hacer request a Wompi
                response = wompi_service.create_transaction_with_token(transaction_data)
                transaction_status = response.get('data', {}).get('status', 'UNKNOWN') if response else 'ERROR'
                transaction_id = response.get('data', {}).get('id') if response else None
                
                logger.info(f"Respuesta de Wompi para renovación: Status={transaction_status}, Transaction ID={transaction_id}")
                
                if transaction_status == 'APPROVED':
                    # Pago aprobado inmediatamente - PASO 1: Notificar a N8N PRIMERO antes de actualizar BD
                    
                    # Calcular nuevo período
                    today = timezone.now()
                    if subscription.billing_cycle == 'yearly':
                        new_period_end = today + timedelta(days=365)
                    else:
                        new_period_end = today + timedelta(days=30)
                    
                    # Notificar a N8N ANTES de actualizar la BD
                    from dashboard.views import notify_n8n_subscription_reactivated
                    logger.info(f"Pago aprobado para subscription {subscription.id} - Notificando a N8N primero")
                    n8n_response = notify_n8n_subscription_reactivated(subscription)
                    
                    if not n8n_response:
                        # N8N falló - NO reactivar pero el pago ya se cobró
                        # Esto es crítico: necesitamos revertir o manejar manualmente
                        logger.error(
                            f"CRÍTICO: Pago aprobado pero N8N falló para subscription {subscription.id}. "
                            f"Transaction: {transaction_id}. Requiere intervención manual."
                        )
                        messages.error(
                            request,
                            'Tu pago fue procesado exitosamente, pero hubo un error al reactivar tu cuenta de Chatwoot. '
                            'Nuestro equipo ha sido notificado y resolverá esto en los próximos minutos. '
                            'Por favor contacta a soporte si no ves cambios pronto.'
                        )
                        # Aún así guardamos el invoice para tracking
                        Invoice.objects.create(
                            subscription=subscription,
                            amount=amount,
                            currency='COP',
                            status='paid',
                            billing_reason='subscription_renewal',
                            wompi_transaction_id=transaction_id,
                            paid_at=timezone.now()
                        )
                        return redirect('dashboard:dashboard')
                    
                    # PASO 2: N8N respondió OK - Ahora SÍ actualizar BD
                    subscription.status = 'active'
                    subscription.cancelled_at = None
                    subscription.current_period_start = today
                    subscription.current_period_end = new_period_end
                    subscription.save()
                    
                    # Crear Invoice
                    Invoice.objects.create(
                        subscription=subscription,
                        amount=amount,
                        currency='COP',
                        status='paid',
                        billing_reason='subscription_renewal',
                        wompi_transaction_id=transaction_id,
                        paid_at=timezone.now()
                    )
                    
                    logger.info(f"Subscription {subscription.id} renovada exitosamente en BD tras confirmación de N8N para company {company.name}")
                    
                    messages.success(request, f'¡Tu suscripción ha sido renovada exitosamente! Cobro: ${amount:,.0f} COP. Tu cuenta de Chatwoot ya tiene acceso completo.')
                    return redirect('dashboard:dashboard')
                
                elif transaction_status == 'PENDING':
                    # ⚠️ Pago PENDIENTE - Guardar invoice en estado pending y esperar webhook
                    logger.warning(
                        f"⏳ Pago PENDING para renovación de subscription {subscription.id}. "
                        f"Transaction ID: {transaction_id}. Esperando webhook para confirmar."
                    )
                    
                    # Crear invoice en estado pending (el webhook lo actualizará)
                    Invoice.objects.create(
                        subscription=subscription,
                        amount=amount,
                        currency='COP',
                        status='pending',
                        billing_reason='subscription_renewal',
                        wompi_transaction_id=transaction_id,
                        paid_at=None  # Se establecerá cuando se confirme
                    )
                    
                    messages.info(
                        request,
                        'Tu pago está siendo procesado por el banco. '
                        'La renovación se completará automáticamente cuando se confirme el pago. '
                        'Te notificaremos por email cuando tu suscripción esté activa nuevamente.'
                    )
                    return redirect('dashboard:dashboard')
                
                else:
                    # Pago rechazado o error
                    logger.error(f"Pago fallido para renovación de subscription {subscription.id}: {transaction_status}")
                    
                    # Mensajes más específicos según el estado
                    if transaction_status == 'DECLINED':
                        error_message = 'Tu pago fue rechazado por el banco. Por favor verifica tu tarjeta o intenta con otro método de pago.'
                    elif transaction_status == 'ERROR':
                        error_message = 'Ocurrió un error al procesar tu pago. Por favor intenta nuevamente.'
                    else:
                        error_message = f'No se pudo procesar el pago. Estado: {transaction_status}. Por favor verifica tu tarjeta.'
                    
                    messages.error(request, error_message)
                    return redirect('subscriptions:renew_expired_subscription')
                    
            except Exception as e:
                logger.error(f"Error al procesar pago para renovación: {e}")
                messages.error(request, 'Ocurrió un error al procesar el pago. Por favor intenta nuevamente.')
                return redirect('subscriptions:renew_expired_subscription')
        
        # GET: Mostrar página de renovación con detalles del pago
        
        # Validar requisitos para mostrar alertas en el template (usar hasattr para evitar RelatedObjectDoesNotExist)
        missing_billing_info = not hasattr(company, 'billing_info') or not company.billing_info
        missing_payment_method = not subscription.payment_source_id
        
        context = {
            'company': company,
            'subscription': subscription,
            'amount': amount,
            'billing_cycle': subscription.billing_cycle,
            'card_brand': subscription.card_brand,
            'card_last_four': subscription.card_last_four,
            'missing_billing_info': missing_billing_info,
            'missing_payment_method': missing_payment_method,
        }
        
        return render(request, 'subscriptions/renew_subscription.html', context)
        
    except Company.DoesNotExist:
        messages.error(request, 'No se encontró información de la empresa')
        return redirect('dashboard:login')


# ==================== API ENDPOINTS ====================

@csrf_exempt
def wompi_webhook(request):
    """
    Webhook para eventos de Wompi
    
    Implementa:
    - Validación de firma (X-Event-Checksum)
    - Idempotencia (evita procesamiento duplicado)
    - Auditoría completa de eventos
    """
    if request.method == 'POST':
        try:
            request_body = request.body
            separator = "=" * 80
            
            logger.info(f"\n{separator}")
            logger.info("🔔 WEBHOOK RECIBIDO DE WOMPI")
            logger.info(f"{separator}")
            logger.info(f"Body length: {len(request_body)} bytes")
            logger.info(f"Content-Type: {request.META.get('CONTENT_TYPE')}")
            logger.info(f"User-Agent: {request.META.get('HTTP_USER_AGENT')}")
            
            event_data = json.loads(request_body)
            
            # Log del webhook completo con formato bonito
            logger.info(f"\n📦 WEBHOOK PAYLOAD COMPLETO:")
            logger.info(json.dumps(event_data, indent=2, ensure_ascii=False))
            logger.info(f"{separator}\n")
            
            # ========================================
            # 1. VALIDACIÓN DE FIRMA (SEGURIDAD)
            # ========================================
            wompi_service = WompiService()
            signature = request.META.get('HTTP_X_EVENT_CHECKSUM')
            
            logger.info(f"🔐 X-Event-Checksum recibido: {signature}")
            
            if not signature:
                logger.error("❌ WEBHOOK RECHAZADO: No se recibió X-Event-Checksum")
                return HttpResponse('Missing signature', status=401)
            
            if not wompi_service.verify_signature(request_body, signature):
                logger.error("❌ WEBHOOK RECHAZADO: Firma inválida")
                logger.error(f"   Body: {request_body.decode('utf-8')}")
                logger.error(f"   Firma recibida: {signature}")
                
                # Registrar intento de webhook con firma inválida
                from subscriptions.models import WebhookEvent
                webhook_event = WebhookEvent.objects.create(
                    event_id=event_data.get('id', f"invalid-{timezone.now().timestamp()}"),
                    event_type=event_data.get('event', 'unknown'),
                    transaction_id=event_data.get('data', {}).get('transaction', {}).get('id', 'unknown'),
                    payload=event_data,
                    signature=signature,
                    status='invalid_signature',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                webhook_event.mark_as_invalid_signature()
                
                return HttpResponse('Invalid signature', status=403)
            
            logger.info("✅ Firma válida - Webhook autenticado correctamente")
            
            # ========================================
            # 2. IDEMPOTENCIA (EVITAR DUPLICADOS)
            # ========================================
            from subscriptions.models import WebhookEvent
            
            event_id = event_data.get('id')
            event_type = event_data.get('event')
            transaction_data = event_data.get('data', {}).get('transaction', {})
            transaction_id = transaction_data.get('id')
            
            if not event_id:
                logger.error("❌ WEBHOOK RECHAZADO: No se recibió event_id")
                return HttpResponse('Missing event_id', status=400)
            
            # Verificar si ya procesamos este webhook
            existing_webhook = WebhookEvent.objects.filter(event_id=event_id).first()
            
            if existing_webhook:
                if existing_webhook.status in ['processed', 'duplicate']:
                    logger.warning(f"⚠️ WEBHOOK DUPLICADO: event_id={event_id} ya fue procesado")
                    logger.warning(f"   Estado anterior: {existing_webhook.status}")
                    logger.warning(f"   Procesado el: {existing_webhook.processed_at}")
                    
                    existing_webhook.mark_as_duplicate()
                    
                    # Responder 200 OK para que Wompi no reintente
                    return HttpResponse('OK - Already processed', status=200)
                
                elif existing_webhook.status == 'processing':
                    logger.warning(f"⚠️ WEBHOOK EN PROCESAMIENTO: event_id={event_id}")
                    # Otro worker lo está procesando, responder OK
                    return HttpResponse('OK - Processing', status=200)
                
                elif existing_webhook.status == 'failed':
                    logger.info(f"🔄 REINTENTANDO webhook fallido: event_id={event_id}")
                    webhook_event = existing_webhook
                    webhook_event.mark_as_processing()
            else:
                # Crear nuevo registro de webhook
                webhook_event = WebhookEvent.objects.create(
                    event_id=event_id,
                    event_type=event_type,
                    transaction_id=transaction_id,
                    payload=event_data,
                    signature=signature,
                    status='processing',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                logger.info(f"📝 Webhook registrado con ID: {webhook_event.id}")
            
            # ========================================
            # 3. PROCESAMIENTO DEL WEBHOOK
            # ========================================
            logger.info(f"\n📋 EVENT TYPE: {event_type}")
            logger.info(f"\n💳 TRANSACTION DATA:")
            logger.info(json.dumps(transaction_data, indent=2, ensure_ascii=False))
            
            if event_type == 'transaction.updated':
                status = transaction_data.get('status')
                reference = transaction_data.get('reference')
                transaction_id = transaction_data.get('id')
                payment_method = transaction_data.get('payment_method', {})
                
                logger.info(f"\n🔍 TRANSACTION SUMMARY:")
                logger.info(f"   Status: {status}")
                logger.info(f"   Reference: {reference}")
                logger.info(f"   ID: {transaction_id}")
                logger.info(f"   Payment Method Type: {payment_method.get('type')}")
                logger.info(f"   Amount: {transaction_data.get('amount_in_cents', 0) / 100} COP")
                
                if status == 'APPROVED':
                    # ========================================
                    # WEBHOOK COMO RESPALDO
                    # ========================================
                    # Este webhook es un RESPALDO para casos donde el usuario cierra la página
                    # antes de que termine el proceso síncrono. El flujo principal ahora 
                    # espera la confirmación en _process_card_payment() haciendo polling.
                    # Este webhook solo activa suscripciones que quedaron en PENDING.
                    # ========================================
                    logger.info(f"✅ Transacción aprobada (webhook): {reference}")
                    
                    # Buscar la suscripción asociada a esta transacción
                    # La referencia tiene formato: 
                    # - LYVIO-FIRST-{plan_id}-{user_id}-{timestamp} (primer pago)
                    # - LYVIO-REC-{subscription_id}-{timestamp} (cobro recurrente)
                    # - LYVIO-RETRY-{subscription_id}-{timestamp} (reintento manual)
                    try:
                        subscription = None
                        
                        # 1. Intentar buscar por wompi_subscription_id (primer pago)
                        subscription = Subscription.objects.filter(wompi_subscription_id=transaction_id).first()
                        
                        # 2. Si no encuentra, buscar por referencia (cobros recurrentes o reintentos)
                        if not subscription and reference:
                            if 'LYVIO-REC-' in reference or 'LYVIO-RETRY-' in reference:
                                # Extraer subscription_id de la referencia
                                # Formato: LYVIO-REC-123-timestamp o LYVIO-RETRY-123-timestamp
                                parts = reference.split('-')
                                if len(parts) >= 3:
                                    try:
                                        subscription_id = int(parts[2])
                                        subscription = Subscription.objects.filter(id=subscription_id).first()
                                        if subscription:
                                            logger.info(f"✅ Suscripción encontrada por referencia: {reference}")
                                    except (ValueError, IndexError):
                                        logger.warning(f"⚠️ No se pudo extraer subscription_id de referencia: {reference}")
                        
                        if subscription:
                            logger.info(f"✅ Suscripción encontrada: {subscription.id} para empresa {subscription.company.name}")
                            logger.info(f"   Plan: {subscription.plan.name}, Status: {subscription.status}")
                            logger.info(f"   Payment source: {subscription.payment_source_id}")
                            
                            # Si la suscripción estaba PENDING, activarla ahora
                            if subscription.status == 'pending':
                                subscription.status = 'active'
                                subscription.save()
                                logger.info(f"🎉 Suscripción ACTIVADA - Cambió de PENDING a ACTIVE")
                            elif subscription.status == 'active':
                                logger.info(f"   ℹ️ Suscripción ya estaba ACTIVE (webhook duplicado?)")
                            
                            # Verificar si ya existe factura para esta transacción
                            existing_invoice = Invoice.objects.filter(
                                wompi_transaction_id=transaction_id
                            ).first()
                            
                            if existing_invoice:
                                logger.info(f"   ℹ️ Factura ya existe para transaction_id={transaction_id} (webhook duplicado)")
                            else:
                                # Crear factura del pago
                                transaction_amount_cents = transaction_data.get('amount_in_cents', 0)
                                transaction_amount = Decimal(transaction_amount_cents / 100) if transaction_amount_cents else None
                                
                                Invoice.objects.create(
                                    subscription=subscription,
                                    amount=transaction_amount,
                                    status='paid',
                                    paid_at=timezone.now(),
                                    wompi_transaction_id=transaction_id,
                                    wompi_reference=reference
                                )
                                logger.info(f"✅ Factura creada: ${transaction_amount} COP")
                                
                                # Extender periodo de suscripción si es cobro recurrente
                                # Identificar tipo de pago:
                                # - LYVIO-FIRST-: Primer pago (no extender, ya tiene periodo)
                                # - LYVIO-REC-: Cobro recurrente automático (extender periodo)
                                # - LYVIO-RETRY-: Reintento manual (extender periodo si suspendida)
                                is_recurring = reference and 'LYVIO-REC-' in reference
                                is_retry = reference and 'LYVIO-RETRY-' in reference
                                
                                if is_retry:
                                    # Reintento manual - reactivar suscripción suspendida
                                    was_suspended = subscription.status == 'suspended'
                                    
                                    if was_suspended:
                                        subscription.status = 'active'
                                        subscription.save()
                                        logger.info(f"🎉 Suscripción REACTIVADA desde estado SUSPENDIDO")
                                        
                                        # Notificar a n8n sobre la reactivación
                                        notify_account_reactivation(subscription.company)
                                    
                                    # Extender periodo como si fuera recurrente
                                    old_period_end = subscription.current_period_end
                                    
                                    if subscription.billing_cycle == 'yearly':
                                        new_period_start = subscription.current_period_end
                                        new_period_end = new_period_start + timedelta(days=365)
                                    else:
                                        new_period_start = subscription.current_period_end
                                        new_period_end = new_period_start + timedelta(days=30)
                                    
                                    subscription.current_period_start = new_period_start
                                    subscription.current_period_end = new_period_end
                                    subscription.save()
                                    
                                    logger.info(f"🔄 Periodo extendido por REINTENTO exitoso:")
                                    logger.info(f"   Periodo anterior: {old_period_end}")
                                    logger.info(f"   Nuevo periodo: {new_period_start} → {new_period_end}")
                                    
                                elif is_recurring:
                                    # Extender el periodo según billing_cycle
                                    old_period_end = subscription.current_period_end
                                    
                                    if subscription.billing_cycle == 'yearly':
                                        # Extender 1 año
                                        new_period_start = subscription.current_period_end
                                        new_period_end = new_period_start + timedelta(days=365)
                                    else:
                                        # Extender 1 mes (monthly)
                                        new_period_start = subscription.current_period_end
                                        new_period_end = new_period_start + timedelta(days=30)
                                    
                                    subscription.current_period_start = new_period_start
                                    subscription.current_period_end = new_period_end
                                    subscription.save()
                                    
                                    logger.info(f"🔄 Periodo de suscripción EXTENDIDO:")
                                    logger.info(f"   Periodo anterior: {old_period_end}")
                                    logger.info(f"   Nuevo periodo: {new_period_start} → {new_period_end}")
                                    logger.info(f"   Billing cycle: {subscription.billing_cycle}")
                                else:
                                    logger.info(f"   ℹ️ Primer pago - periodo no extendido (ya establecido al crear suscripción)")
                            
                            # Verificar que el pago corresponda al monto esperado
                            transaction_amount_cents = transaction_data.get('amount_in_cents', 0)
                            transaction_amount = Decimal(transaction_amount_cents / 100) if transaction_amount_cents else None
                            logger.info(f"   Monto transacción webhook: ${transaction_amount} COP")
                            
                        else:
                            # La suscripción puede no existir si:
                            # 1. Es un cobro recurrente (no el primero)
                            # 2. Es una transacción de prueba
                            # 3. Hubo un error al crear la suscripción
                            # 4. Transacción PENDING → APPROVED (wompi_subscription_id puede cambiar)
                            
                            logger.info(f"ℹ️ No se encontró suscripción con wompi_subscription_id={transaction_id}")
                            logger.info(f"   Intentando estrategias alternativas de búsqueda...")
                            
                            # Estrategia 2: Buscar por payment_source_id si está disponible
                            payment_source_id = transaction_data.get('payment_source_id')
                            if payment_source_id:
                                logger.info(f"   🔍 Buscando por payment_source_id={payment_source_id}")
                                subscriptions_with_source = Subscription.objects.filter(payment_source_id=payment_source_id)
                                if subscriptions_with_source.exists():
                                    subscription = subscriptions_with_source.first()
                                    logger.info(f"   ✅ Suscripción encontrada por payment_source_id: {subscription.id}")
                                    
                                    # Si estaba pending, activarla
                                    if subscription.status == 'pending':
                                        subscription.status = 'active'
                                        subscription.save()
                                        logger.info(f"   🎉 Suscripción ACTIVADA - Cambió de PENDING a ACTIVE")
                                    
                                    # Verificar si ya existe factura (evitar duplicados)
                                    existing_invoice = Invoice.objects.filter(
                                        wompi_transaction_id=transaction_id
                                    ).first()
                                    
                                    if not existing_invoice:
                                        # Crear factura para este cobro
                                        transaction_amount_cents = transaction_data.get('amount_in_cents', 0)
                                        transaction_amount = Decimal(transaction_amount_cents / 100) if transaction_amount_cents else None
                                        
                                        Invoice.objects.create(
                                            subscription=subscription,
                                            amount=transaction_amount,
                                            status='paid',
                                            paid_at=timezone.now(),
                                            wompi_transaction_id=transaction_id,
                                            wompi_reference=reference
                                        )
                                        logger.info(f"   ✅ Factura creada: ${transaction_amount} COP")
                                        
                                        # Extender periodo de suscripción si es cobro recurrente
                                        is_recurring = reference and 'LYVIO-REC-' in reference
                                        
                                        if is_recurring:
                                            old_period_end = subscription.current_period_end
                                            
                                            if subscription.billing_cycle == 'yearly':
                                                new_period_start = subscription.current_period_end
                                                new_period_end = new_period_start + timedelta(days=365)
                                            else:
                                                new_period_start = subscription.current_period_end
                                                new_period_end = new_period_start + timedelta(days=30)
                                            
                                            subscription.current_period_start = new_period_start
                                            subscription.current_period_end = new_period_end
                                            subscription.save()
                                            
                                            logger.info(f"   🔄 Periodo EXTENDIDO: {old_period_end} → {new_period_end}")
                                    else:
                                        logger.info(f"   ℹ️ Factura ya existe (webhook duplicado)")
                                else:
                                    logger.warning(f"   ⚠️ No se encontró suscripción con payment_source_id={payment_source_id}")
                            else:
                                logger.warning(f"   ⚠️ payment_source_id es None en la transacción")
                            
                            # Estrategia 3A: Buscar por customer_email + timestamp reciente
                            if not subscription:
                                customer_email = transaction_data.get('customer_email')
                                if customer_email:
                                    logger.info(f"   🔍 Buscando por customer_email: {customer_email}")
                                    
                                    # Buscar suscripciones recientes (últimos 5 minutos) con ese email
                                    # NO filtramos por status porque puede ya estar 'active' si el webhook llegó 2 veces
                                    recent_subs = Subscription.objects.filter(
                                        wompi_customer_email=customer_email,
                                        created_at__gte=timezone.now() - timedelta(minutes=5)
                                    ).order_by('-created_at')
                                    
                                    logger.info(f"   📊 Encontradas {recent_subs.count()} suscripciones recientes con ese email")
                                    
                                    # Log detallado de TODAS las suscripciones encontradas
                                    for idx, sub in enumerate(recent_subs[:5], 1):  # Mostrar hasta 5
                                        logger.info(f"      {idx}. Suscripción ID={sub.id}, Status={sub.status}, Empresa={sub.company.name}")
                                        logger.info(f"         Email={sub.wompi_customer_email}, Created={sub.created_at}")
                                        logger.info(f"         wompi_subscription_id={sub.wompi_subscription_id}")
                                    
                                    if recent_subs.exists():
                                        subscription = recent_subs.first()
                                        logger.info(f"   ✅ Suscripción encontrada por email: {subscription.id}")
                                        logger.info(f"      Empresa: {subscription.company.name}, Status: {subscription.status}")
                                        logger.info(f"      Creada: {subscription.created_at}")
                                        
                                        # Actualizar wompi_subscription_id con el correcto
                                        subscription.wompi_subscription_id = transaction_id
                                        
                                        # Si estaba pending, activarla
                                        if subscription.status == 'pending':
                                            subscription.status = 'active'
                                            logger.info(f"   🎉 Suscripción ACTIVADA - Cambió de PENDING a ACTIVE")
                                        elif subscription.status == 'active':
                                            logger.info(f"   ℹ️ Suscripción ya estaba ACTIVE (webhook duplicado?)")
                                        
                                        subscription.save()
                                        
                                        # Verificar si ya existe una factura para esta transacción (evitar duplicados)
                                        existing_invoice = Invoice.objects.filter(
                                            wompi_transaction_id=transaction_id
                                        ).first()
                                        
                                        if existing_invoice:
                                            logger.info(f"   ℹ️ Factura ya existe para transaction_id={transaction_id} (webhook duplicado)")
                                        else:
                                            # Crear factura solo si no existe
                                            transaction_amount_cents = transaction_data.get('amount_in_cents', 0)
                                            transaction_amount = Decimal(transaction_amount_cents / 100) if transaction_amount_cents else None
                                            
                                            Invoice.objects.create(
                                                subscription=subscription,
                                                amount=transaction_amount,
                                                status='paid',
                                                paid_at=timezone.now(),
                                                wompi_transaction_id=transaction_id,
                                                wompi_reference=reference
                                            )
                                            logger.info(f"   ✅ Factura creada: ${transaction_amount} COP")
                                            
                                            # Extender periodo si es cobro recurrente
                                            is_recurring = reference and 'LYVIO-REC-' in reference
                                            
                                            if is_recurring:
                                                old_period_end = subscription.current_period_end
                                                
                                                if subscription.billing_cycle == 'yearly':
                                                    new_period_start = subscription.current_period_end
                                                    new_period_end = new_period_start + timedelta(days=365)
                                                else:
                                                    new_period_start = subscription.current_period_end
                                                    new_period_end = new_period_start + timedelta(days=30)
                                                
                                                subscription.current_period_start = new_period_start
                                                subscription.current_period_end = new_period_end
                                                subscription.save()
                                                
                                                logger.info(f"   🔄 Periodo EXTENDIDO: {old_period_end} → {new_period_end}")
                                    else:
                                        logger.warning(f"   ⚠️ No se encontraron suscripciones recientes para email: {customer_email}")
                            
                            # Estrategia 3B: Buscar por referencia (extrae user_id de la referencia)
                            # Formato: LYVIO-FIRST-{plan_id}-{user_id}-{timestamp}
                            if not subscription and reference:
                                try:
                                    logger.info(f"   🔍 Buscando por referencia: {reference}")
                                    parts = reference.split('-')
                                    if len(parts) >= 4 and parts[0] == 'LYVIO' and parts[1] == 'FIRST':
                                        plan_id = int(parts[2])
                                        user_id = int(parts[3])
                                        
                                        logger.info(f"   📋 Extraído de referencia - plan_id={plan_id}, user_id={user_id}")
                                        
                                        # Buscar suscripciones recientes (últimas 24 horas) del usuario y plan
                                        from accounts.models import User
                                        user = User.objects.filter(id=user_id).first()
                                        
                                        if user and hasattr(user, 'company') and user.company:
                                            recent_subs = Subscription.objects.filter(
                                                company=user.company,
                                                plan_id=plan_id,
                                                created_at__gte=timezone.now() - timedelta(hours=24)
                                            ).order_by('-created_at')
                                            
                                            if recent_subs.exists():
                                                subscription = recent_subs.first()
                                                logger.info(f"   ✅ Suscripción encontrada por referencia: {subscription.id}")
                                                logger.info(f"      Empresa: {subscription.company.name}, Status: {subscription.status}")
                                                
                                                # Actualizar wompi_subscription_id con el correcto
                                                subscription.wompi_subscription_id = transaction_id
                                                
                                                # Si estaba pending, activarla
                                                if subscription.status == 'pending':
                                                    subscription.status = 'active'
                                                    logger.info(f"   🎉 Suscripción ACTIVADA - Cambió de PENDING a ACTIVE")
                                                
                                                subscription.save()
                                                
                                                # Verificar si ya existe factura (evitar duplicados)
                                                existing_invoice = Invoice.objects.filter(
                                                    wompi_transaction_id=transaction_id
                                                ).first()
                                                
                                                if not existing_invoice:
                                                    # Crear factura
                                                    transaction_amount_cents = transaction_data.get('amount_in_cents', 0)
                                                    transaction_amount = Decimal(transaction_amount_cents / 100) if transaction_amount_cents else None
                                                    
                                                    Invoice.objects.create(
                                                        subscription=subscription,
                                                        amount=transaction_amount,
                                                        status='paid',
                                                        paid_at=timezone.now(),
                                                        wompi_transaction_id=transaction_id,
                                                        wompi_reference=reference
                                                    )
                                                    logger.info(f"   ✅ Factura creada: ${transaction_amount} COP")
                                                    
                                                    # Extender periodo si es cobro recurrente
                                                    is_recurring = reference and 'LYVIO-REC-' in reference
                                                    
                                                    if is_recurring:
                                                        old_period_end = subscription.current_period_end
                                                        
                                                        if subscription.billing_cycle == 'yearly':
                                                            new_period_start = subscription.current_period_end
                                                            new_period_end = new_period_start + timedelta(days=365)
                                                        else:
                                                            new_period_start = subscription.current_period_end
                                                            new_period_end = new_period_start + timedelta(days=30)
                                                        
                                                        subscription.current_period_start = new_period_start
                                                        subscription.current_period_end = new_period_end
                                                        subscription.save()
                                                        
                                                        logger.info(f"   🔄 Periodo EXTENDIDO: {old_period_end} → {new_period_end}")
                                                else:
                                                    logger.info(f"   ℹ️ Factura ya existe (webhook duplicado)")
                                            else:
                                                logger.warning(f"   ⚠️ No se encontraron suscripciones recientes para user_id={user_id}, plan_id={plan_id}")
                                        else:
                                            logger.warning(f"   ⚠️ No se encontró usuario o empresa para user_id={user_id}")
                                    else:
                                        logger.warning(f"   ⚠️ Formato de referencia no reconocido: {reference}")
                                except (ValueError, IndexError) as parse_error:
                                    logger.error(f"   ❌ Error parseando referencia {reference}: {parse_error}")
                            
                            if not subscription:
                                logger.error(f"   ❌ NO SE PUDO ENCONTRAR SUSCRIPCIÓN con ninguna estrategia")
                                logger.error(f"      - wompi_subscription_id: {transaction_id}")
                                logger.error(f"      - payment_source_id: {payment_source_id}")
                                logger.error(f"      - reference: {reference}")
                    
                    except Exception as e:
                        logger.error(f"❌ Error procesando webhook de transacción aprobada: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                    
                elif status == 'DECLINED':
                    logger.info(f"Transacción rechazada: {reference}")
                    
                elif status == 'VOIDED':
                    logger.info(f"Transacción anulada: {reference}")
            
            # ========================================
            # 4. MARCAR WEBHOOK COMO PROCESADO
            # ========================================
            # Buscar la suscripción e invoice procesados para asociarlos
            processed_subscription = None
            processed_invoice = None
            
            if event_type == 'transaction.updated' and status == 'APPROVED':
                # Intentar encontrar la suscripción que se actualizó
                processed_subscription = Subscription.objects.filter(
                    wompi_subscription_id=transaction_id
                ).first()
                
                if not processed_subscription and reference:
                    # Buscar por referencia
                    if 'LYVIO-REC-' in reference or 'LYVIO-RENEW-' in reference:
                        parts = reference.split('-')
                        if len(parts) >= 3:
                            try:
                                subscription_id = int(parts[2])
                                processed_subscription = Subscription.objects.filter(id=subscription_id).first()
                            except (ValueError, IndexError):
                                pass
                
                # Buscar invoice creado/actualizado
                processed_invoice = Invoice.objects.filter(
                    wompi_transaction_id=transaction_id
                ).first()
            
            # Marcar webhook como procesado exitosamente
            webhook_event.mark_as_processed(
                subscription=processed_subscription,
                invoice=processed_invoice
            )
            
            logger.info(f"✅ WEBHOOK PROCESADO EXITOSAMENTE")
            logger.info(f"   Event ID: {event_id}")
            logger.info(f"   Subscription: {processed_subscription.id if processed_subscription else 'N/A'}")
            logger.info(f"   Invoice: {processed_invoice.id if processed_invoice else 'N/A'}")
            
            # ========================================
            # 5. RESPONDER A WOMPI
            # ========================================
            # Wompi espera un checksum en la respuesta
            # El checksum se calcula como: sha256(event_checksum + events_secret)
            signature = request.META.get('HTTP_X_EVENT_CHECKSUM', '')
            response_checksum = wompi_service._compute_response_checksum(signature)
            
            logger.info(f"📤 Enviando response checksum: {response_checksum}")
            
            response = JsonResponse({
                'signature': {
                    'checksum': response_checksum
                }
            })
            response.status_code = 200
            return response
            
        except Exception as e:
            logger.error(f"❌ ERROR CRÍTICO en webhook Wompi: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Marcar webhook como fallido
            try:
                webhook_event.mark_as_failed(str(e))
            except:
                logger.error("No se pudo marcar webhook como fallido")
            
            # Intentar responder con checksum incluso en error
            try:
                signature = request.META.get('HTTP_X_EVENT_CHECKSUM', '')
                wompi_service = WompiService()
                response_checksum = wompi_service._compute_response_checksum(signature)
                return JsonResponse({
                    'signature': {
                        'checksum': response_checksum
                    }
                }, status=500)
            except:
                return HttpResponse('Error', status=500)
    
    return HttpResponse('Method not allowed', status=405)


@csrf_exempt
def payment_success(request):
    """Vista para manejar el éxito del pago desde Wompi"""
    
    # Si es un POST, podría ser un webhook llegando a la URL equivocada
    if request.method == 'POST':
        # Redirigir al webhook handler correcto
        return wompi_webhook(request)
    
    # Si es GET, es una redirección normal del usuario
    transaction_id = request.GET.get('id')
    status = request.GET.get('status')
    reference = request.GET.get('reference')
    
    context = {
        'transaction_id': transaction_id,
        'status': status,
        'reference': reference,
    }
    
    # Si el pago fue exitoso, mostrar mensaje de éxito
    if status == 'APPROVED':
        messages.success(request, '¡Pago procesado exitosamente! Tu suscripción se activará en unos momentos.')
        return redirect('dashboard:dashboard')
    elif status == 'DECLINED':
        messages.error(request, 'El pago fue rechazado. Por favor intenta con otro método de pago.')
        return redirect('dashboard:dashboard')
    else:
        messages.info(request, f'Estado del pago: {status}')
        return redirect('dashboard:dashboard')


# ==================== COBROS AUTOMÁTICOS PARA N8N ====================

@csrf_exempt
def process_recurring_payments(request):
    """
    Endpoint para que N8N ejecute cobros automáticos
    POST /billing/recurring-payments/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        # Obtener parámetros
        data = json.loads(request.body)
        subscription_ids = data.get('subscription_ids', [])  # Lista específica de IDs
        dry_run = data.get('dry_run', False)  # True para solo simular
        
        # Si no se especifican IDs, procesar todas las suscripciones activas que deben cobrarse
        if not subscription_ids:
            # Buscar suscripciones que necesitan cobro
            today = timezone.now().date()
            subscriptions_to_charge = Subscription.objects.filter(
                status='active',
                payment_source_id__isnull=False,  # Solo las que tienen fuente de pago
                current_period_end__date__lte=today  # Período actual ha terminado
            )
        else:
            # Procesar solo las suscripciones especificadas
            subscriptions_to_charge = Subscription.objects.filter(
                id__in=subscription_ids,
                status='active',
                payment_source_id__isnull=False
            )
        
        results = []
        wompi_service = WompiService()
        
        logger.info(f"🔄 Procesando {subscriptions_to_charge.count()} suscripciones para cobro automático")
        
        for subscription in subscriptions_to_charge:
            result = {
                'subscription_id': subscription.id,
                'company': subscription.company.name,
                'plan': subscription.plan.name,
                'amount': None,
                'status': 'pending',
                'error': None,
                'transaction_id': None
            }
            
            try:
                # Calcular monto según el ciclo de facturación
                if subscription.billing_cycle == 'yearly':
                    amount = subscription.plan.price_yearly or subscription.plan.price_monthly * 12
                    period_days = 365
                else:
                    amount = subscription.plan.price_monthly
                    period_days = 30
                
                result['amount'] = float(amount)
                
                if dry_run:
                    result['status'] = 'simulated'
                    result['message'] = 'Simulación - no se ejecutó el cobro real'
                    logger.info(f"🎯 SIMULACIÓN - Suscripción {subscription.id}: ${amount}")
                else:
                    # Generar referencia única para el cobro
                    import time
                    timestamp = int(time.time())
                    reference = f"RECURRING-{subscription.id}-{timestamp}"
                    
                    # Ejecutar cobro automático
                    transaction_data = wompi_service.create_recurring_transaction(
                        payment_source_id=subscription.payment_source_id,
                        amount=amount,
                        customer_email=subscription.wompi_customer_email,
                        reference=reference
                    )
                    
                    result['transaction_id'] = transaction_data['id']
                    
                    if transaction_data['status'] in ['APPROVED', 'PENDING']:
                        # Actualizar período de la suscripción
                        subscription.current_period_start = timezone.now()
                        subscription.current_period_end = timezone.now() + timedelta(days=period_days)
                        subscription.save()
                        
                        result['status'] = 'success'
                        result['message'] = f"Cobro procesado: {transaction_data['status']}"
                        
                        logger.info(f"✅ Cobro exitoso - Suscripción {subscription.id}: ${amount}, TX: {transaction_data['id']}")
                    else:
                        result['status'] = 'failed'
                        result['message'] = f"Cobro rechazado: {transaction_data['status']}"
                        
                        # Marcar suscripción como vencida
                        subscription.status = 'past_due'
                        subscription.save()
                        
                        logger.warning(f"❌ Cobro fallido - Suscripción {subscription.id}: {transaction_data['status']}")
                        
            except Exception as e:
                result['status'] = 'error'
                result['error'] = str(e)
                logger.error(f"💥 Error cobrando suscripción {subscription.id}: {str(e)}")
            
            results.append(result)
        
        # Resumen
        summary = {
            'total_processed': len(results),
            'successful': len([r for r in results if r['status'] == 'success']),
            'failed': len([r for r in results if r['status'] in ['failed', 'error']]),
            'simulated': len([r for r in results if r['status'] == 'simulated']),
        }
        
        logger.info(f"📊 Resumen de cobros: {summary}")
        
        return JsonResponse({
            'success': True,
            'summary': summary,
            'results': results,
            'dry_run': dry_run
        })
        
    except Exception as e:
        logger.error(f"💥 Error general en cobros automáticos: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
def manage_payment_source(request):
    """
    Endpoint para gestionar fuentes de pago (renovar tarjetas vencidas, etc.)
    POST /billing/payment-source/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        subscription_id = data.get('subscription_id')
        action = data.get('action')  # 'void', 'update', 'check'
        
        subscription = get_object_or_404(Subscription, id=subscription_id)
        wompi_service = WompiService()
        
        if action == 'void':
            # Cancelar fuente de pago actual
            if subscription.payment_source_id:
                # TODO: Implementar void de payment source en WompiService
                subscription.payment_source_id = None
                subscription.status = 'past_due'
                subscription.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Fuente de pago cancelada',
                    'subscription_id': subscription.id,
                    'status': subscription.status
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'No hay fuente de pago activa'
                })
        
        elif action == 'check':
            # Verificar estado de la fuente de pago
            if subscription.payment_source_id:
                # TODO: Implementar check de payment source en WompiService
                return JsonResponse({
                    'success': True,
                    'subscription_id': subscription.id,
                    'payment_source_id': subscription.payment_source_id,
                    'status': subscription.status,
                    'current_period_end': subscription.current_period_end.isoformat()
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'No hay fuente de pago activa'
                })
        
        else:
            return JsonResponse({
                'success': False,
                'error': f'Acción no válida: {action}'
            })
            
    except Exception as e:
        logger.error(f"Error gestionando fuente de pago: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='dashboard:login')
def update_payment_method(request):
    """
    Vista para actualizar el método de pago (tarjeta) de una suscripción
    
    Acepta suscripciones con status: active, suspended
    
    Parámetros POST opcionales:
    - retry_charge: 'true' para reintentar cobro con la nueva tarjeta (si está suspendida)
    - Si está suspendida y retry_charge=true, intenta cobrar y reactivar
    - Si está activa, solo actualiza el método de pago sin cobrar
    """
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        
        # Permitir active o suspended
        subscription = Subscription.objects.filter(
            company=company, 
            status__in=['active', 'suspended']
        ).first()
        
        if not subscription:
            messages.error(request, 'No tienes una suscripción para actualizar')
            return redirect('dashboard:dashboard')
        
        if request.method == 'POST':
            try:
                # Obtener datos del formulario
                card_number = request.POST.get('card_number', '').replace(' ', '')
                card_holder = request.POST.get('card_holder', '')
                exp_month = request.POST.get('exp_month', '')
                exp_year = request.POST.get('exp_year', '')
                cvc = request.POST.get('cvc', '')
                
                logger.info(f"🔄 Actualizando método de pago para suscripción {subscription.id}")
                logger.info(f"   Empresa: {company.name}")
                logger.info(f"   Tarjeta: ****{card_number[-4:]}")
                
                # Validaciones básicas
                if not all([card_number, card_holder, exp_month, exp_year, cvc]):
                    messages.error(request, 'Todos los campos son obligatorios')
                    return redirect('dashboard:update_payment_method')
                
                # Inicializar servicio Wompi
                wompi_service = WompiService()
                
                # PASO 1: Tokenizar la nueva tarjeta (NO hace cobro)
                logger.info("   📝 Tokenizando nueva tarjeta...")
                card_data = {
                    'number': card_number,
                    'cvc': cvc,
                    'exp_month': exp_month,
                    'exp_year': exp_year,
                    'card_holder': card_holder
                }
                token_id = wompi_service.tokenize_card(card_data)
                
                if not token_id:
                    logger.error(f"   ❌ Error tokenizando tarjeta")
                    messages.error(request, 'Error al validar la tarjeta. Verifica los datos.')
                    return redirect('dashboard:dashboard')
                
                logger.info(f"   ✅ Tarjeta tokenizada: {token_id}")
                
                # PASO 2: Crear payment_source (vincula tarjeta con cliente, NO hace cobro)
                logger.info("   💳 Creando payment source...")
                acceptance_tokens = wompi_service.create_acceptance_token()
                payment_source_result = wompi_service.create_payment_source(
                    token=token_id,
                    customer_email=subscription.wompi_customer_email,
                    acceptance_tokens=acceptance_tokens
                )
                
                if not payment_source_result or 'id' not in payment_source_result:
                    logger.error(f"   ❌ Error creando payment source: {payment_source_result}")
                    messages.error(request, 'Error al vincular la tarjeta. Intenta de nuevo.')
                    return redirect('dashboard:update_payment_method')
                
                new_payment_source_id = payment_source_result['id']
                logger.info(f"   ✅ Payment source creado: {new_payment_source_id}")
                
                # PASO 3: Actualizar suscripción con nueva tarjeta
                old_payment_source = subscription.payment_source_id
                
                # Extraer información de la tarjeta del public_data
                public_data = payment_source_result.get('public_data', {})
                
                subscription.payment_source_id = new_payment_source_id
                subscription.card_brand = public_data.get('brand', '').upper()
                subscription.card_last_four = public_data.get('last_four', '')
                subscription.card_exp_month = public_data.get('exp_month', exp_month)
                subscription.card_exp_year = public_data.get('exp_year', exp_year)
                subscription.save()
                
                logger.info(f"   🎉 Tarjeta actualizada exitosamente")
                logger.info(f"      Payment source anterior: {old_payment_source}")
                logger.info(f"      Payment source nuevo: {new_payment_source_id}")
                logger.info(f"      Nueva tarjeta: {subscription.card_brand} ****{subscription.card_last_four}")
                
                # PASO 4: Si está suspendida, SIEMPRE intentar cobro automáticamente
                was_suspended = subscription.status == 'suspended'
                
                if was_suspended:
                    logger.info("   💰 Reintentando cobro para reactivar suscripción suspendida...")
                    
                    # Calcular monto a cobrar
                    if subscription.billing_cycle == 'yearly' and subscription.plan.price_yearly:
                        amount = float(subscription.plan.price_yearly)
                    else:
                        amount = float(subscription.plan.price_monthly)
                    
                    amount_in_cents = int(amount * 100)
                    
                    # Crear referencia única
                    import time
                    reference = f"LYVIO-REACTIVATION-{subscription.id}-{int(time.time())}"
                    
                    try:
                        # Crear transacción
                        logger.info(f"   💳 Creando transacción de ${amount:,.0f} COP...")
                        transaction_result = wompi_service.create_transaction(
                            amount_in_cents=amount_in_cents,
                            currency='COP',
                            customer_email=subscription.wompi_customer_email,
                            payment_source_id=new_payment_source_id,
                            reference=reference
                        )
                        
                        if not transaction_result:
                            logger.error("   ❌ No se recibió respuesta de Wompi")
                            messages.warning(request, 'Tarjeta actualizada, pero hubo un error al procesar el pago.')
                            return redirect('dashboard:dashboard')
                        
                        transaction_status = transaction_result.get('data', {}).get('status', 'UNKNOWN')
                        transaction_id = transaction_result.get('data', {}).get('id', '')
                        
                        logger.info(f"   📊 Estado de transacción: {transaction_status} (ID: {transaction_id})")
                        
                        if transaction_status == 'APPROVED':
                            # Reactivar y extender periodo
                            was_suspended = subscription.status == 'suspended'
                            subscription.status = 'active'
                            
                            # Extender el periodo según billing_cycle
                            old_period_end = subscription.current_period_end
                            
                            if subscription.billing_cycle == 'yearly':
                                # Extender 1 año desde el final del periodo actual
                                new_period_start = subscription.current_period_end
                                new_period_end = new_period_start + timedelta(days=365)
                            else:
                                # Extender 1 mes (monthly)
                                new_period_start = subscription.current_period_end
                                new_period_end = new_period_start + timedelta(days=30)
                            
                            subscription.current_period_start = new_period_start
                            subscription.current_period_end = new_period_end
                            subscription.save()
                            
                            logger.info(f"   ✅ Pago APROBADO - Suscripción REACTIVADA")
                            logger.info(f"   🔄 Periodo extendido:")
                            logger.info(f"      Periodo anterior finalizaba: {old_period_end}")
                            logger.info(f"      Nuevo periodo: {new_period_start} → {new_period_end}")
                            
                            # Notificar a n8n si la cuenta estaba suspendida
                            if was_suspended:
                                notify_account_reactivation(subscription.company)
                            
                            messages.success(request, f'✅ Tarjeta actualizada y suscripción reactivada exitosamente! Monto cobrado: ${amount:,.0f} COP')
                            
                        elif transaction_status == 'PENDING':
                            logger.info(f"   ⏳ Pago PENDIENTE - Iniciando polling...")
                            
                            # Hacer polling durante 15 segundos
                            max_attempts = 3
                            for attempt in range(1, max_attempts + 1):
                                logger.info(f"   ⏱️  Intento {attempt}/{max_attempts} - Esperando 5 segundos...")
                                time.sleep(5)
                                
                                updated_transaction = wompi_service.get_transaction(transaction_id)
                                
                                if updated_transaction:
                                    updated_status = updated_transaction.get('data', {}).get('status', 'UNKNOWN')
                                    logger.info(f"   📊 Estado actualizado: {updated_status}")
                                    
                                    if updated_status == 'APPROVED':
                                        # Reactivar y extender periodo
                                        was_suspended = subscription.status == 'suspended'
                                        subscription.status = 'active'
                                        
                                        # Extender el periodo según billing_cycle
                                        old_period_end = subscription.current_period_end
                                        
                                        if subscription.billing_cycle == 'yearly':
                                            new_period_start = subscription.current_period_end
                                            new_period_end = new_period_start + timedelta(days=365)
                                        else:
                                            new_period_start = subscription.current_period_end
                                            new_period_end = new_period_start + timedelta(days=30)
                                        
                                        subscription.current_period_start = new_period_start
                                        subscription.current_period_end = new_period_end
                                        subscription.save()
                                        
                                        logger.info(f"   ✅ Pago APROBADO (después de {attempt * 5}s) - Suscripción REACTIVADA")
                                        logger.info(f"   🔄 Periodo extendido:")
                                        logger.info(f"      Periodo anterior finalizaba: {old_period_end}")
                                        logger.info(f"      Nuevo periodo: {new_period_start} → {new_period_end}")
                                        
                                        # Notificar a n8n si la cuenta estaba suspendida
                                        if was_suspended:
                                            notify_account_reactivation(subscription.company)
                                        
                                        messages.success(request, f'✅ Tarjeta actualizada y suscripción reactivada! Monto cobrado: ${amount:,.0f} COP')
                                        transaction_status = 'APPROVED'
                                        break
                                    
                                    elif updated_status in ['DECLINED', 'ERROR']:
                                        logger.info(f"   ❌ Pago rechazado: {updated_status}")
                                        messages.warning(request, 'Tarjeta actualizada, pero el pago fue rechazado. Por favor contacta a tu banco.')
                                        transaction_status = updated_status
                                        break
                            
                            # Si sigue PENDING después del polling
                            if transaction_status == 'PENDING':
                                logger.info(f"   ⏳ Transacción sigue PENDING después de 15 segundos")
                                messages.warning(request, 'Tarjeta actualizada. El pago está siendo procesado, te notificaremos cuando se apruebe.')
                        
                        elif transaction_status in ['DECLINED', 'ERROR']:
                            logger.info(f"   ❌ Pago rechazado: {transaction_status}")
                            messages.warning(request, 'Tarjeta actualizada, pero el pago fue rechazado. Por favor verifica tu método de pago.')
                        
                        else:
                            logger.warning(f"   ⚠️ Estado desconocido: {transaction_status}")
                            messages.warning(request, f'Tarjeta actualizada. Estado del pago: {transaction_status}')
                    
                    except Exception as charge_error:
                        logger.error(f"   ❌ Error al crear transacción: {charge_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        messages.warning(request, 'Tarjeta actualizada, pero hubo un error al procesar el pago.')
                
                else:
                    messages.success(request, f'✅ Tarjeta actualizada exitosamente: {subscription.card_brand} ****{subscription.card_last_four}')
                
                return redirect('dashboard:dashboard')
                
            except Exception as e:
                logger.error(f"   ❌ Error actualizando tarjeta: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                messages.error(request, f'Error al actualizar la tarjeta: {str(e)}')
                return redirect('dashboard:dashboard')
        
        # GET request - redirigir al dashboard (el formulario está en offcanvas)
        return redirect('dashboard:dashboard')
        
    except Exception as e:
        logger.error(f"Error en update_payment_method: {str(e)}")
        messages.error(request, 'Error procesando la solicitud')
        return redirect('dashboard:dashboard')


@login_required
def retry_payment(request):
    """
    Vista para reintentar el cobro con el payment_source actual
    Usado cuando la suscripción está suspendida y el usuario quiere reactivarla
    sin cambiar la tarjeta
    """
    if request.method != 'POST':
        return redirect('dashboard:dashboard')
    
    try:
        company, redirect_response = get_user_company_or_redirect(request)
        if redirect_response:
            return redirect_response
        
        # Obtener suscripción suspendida
        subscription = Subscription.objects.filter(
            company=company, 
            status='suspended'
        ).first()
        
        if not subscription:
            logger.warning(f"⚠️ No hay suscripción suspendida para {company.name}")
            messages.error(request, 'No tienes una suscripción suspendida para reactivar')
            return redirect('dashboard:dashboard')
        
        if not subscription.payment_source_id:
            logger.error(f"❌ Suscripción {subscription.id} no tiene payment_source_id")
            messages.error(request, 'No hay método de pago configurado')
            return redirect('dashboard:dashboard')
        
        logger.info(f"🔄 Reintentando cobro para suscripción suspendida {subscription.id}")
        logger.info(f"   Empresa: {company.name}")
        logger.info(f"   Payment source: {subscription.payment_source_id}")
        
        # Calcular monto a cobrar
        if subscription.billing_cycle == 'yearly' and subscription.plan.price_yearly:
            amount = float(subscription.plan.price_yearly)
        else:
            amount = float(subscription.plan.price_monthly)
        
        amount_in_cents = int(amount * 100)
        
        # Crear referencia única
        import time
        reference = f"LYVIO-RETRY-{subscription.id}-{int(time.time())}"
        
        # Inicializar servicio Wompi
        wompi_service = WompiService()
        
        try:
            # Crear transacción con el payment_source actual
            logger.info(f"   💳 Creando transacción de ${amount:,.0f} COP...")
            transaction_result = wompi_service.create_transaction(
                amount_in_cents=amount_in_cents,
                currency='COP',
                customer_email=subscription.wompi_customer_email,
                payment_source_id=subscription.payment_source_id,
                reference=reference
            )
            
            if not transaction_result:
                logger.error("   ❌ No se recibió respuesta de Wompi")
                messages.error(request, 'Error al procesar el pago. Intenta nuevamente.')
                return redirect('dashboard:dashboard')
            
            transaction_status = transaction_result.get('data', {}).get('status', 'UNKNOWN')
            transaction_id = transaction_result.get('data', {}).get('id', '')
            status_message = transaction_result.get('data', {}).get('status_message', '')
            
            logger.info(f"   📊 Estado de transacción: {transaction_status} (ID: {transaction_id})")
            if status_message:
                logger.info(f"   📝 Mensaje de Wompi: {status_message}")
            logger.info(f"   🔍 Respuesta completa de Wompi:")
            logger.info(f"   {transaction_result}")
            
            if transaction_status == 'APPROVED':
                # Reactivar y extender periodo
                subscription.status = 'active'
                
                # Extender el periodo según billing_cycle
                old_period_end = subscription.current_period_end
                
                if subscription.billing_cycle == 'yearly':
                    new_period_start = subscription.current_period_end
                    new_period_end = new_period_start + timedelta(days=365)
                else:
                    new_period_start = subscription.current_period_end
                    new_period_end = new_period_start + timedelta(days=30)
                
                subscription.current_period_start = new_period_start
                subscription.current_period_end = new_period_end
                subscription.save()
                
                logger.info(f"   ✅ Pago APROBADO - Suscripción REACTIVADA")
                logger.info(f"   🔄 Periodo extendido:")
                logger.info(f"      Periodo anterior finalizaba: {old_period_end}")
                logger.info(f"      Nuevo periodo: {new_period_start} → {new_period_end}")
                
                # Notificar a n8n sobre la reactivación
                notify_account_reactivation(company)
                
                messages.success(request, f'✅ Pago exitoso! Tu suscripción ha sido reactivada. Monto: ${amount:,.0f} COP')
                
            elif transaction_status == 'PENDING':
                logger.info(f"   ⏳ Pago PENDIENTE de aprobación bancaria")
                logger.info(f"   🔄 Iniciando polling para esperar aprobación de Wompi...")
                
                # Hacer polling durante 15 segundos (3 intentos de 5 segundos)
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    logger.info(f"   ⏱️  Intento {attempt}/{max_attempts} - Esperando 5 segundos...")
                    time.sleep(5)
                    
                    # Consultar estado actualizado de la transacción
                    updated_transaction = wompi_service.get_transaction(transaction_id)
                    
                    if updated_transaction:
                        updated_status = updated_transaction.get('data', {}).get('status', 'UNKNOWN')
                        logger.info(f"   📊 Estado actualizado: {updated_status}")
                        
                        if updated_status == 'APPROVED':
                            # ¡Aprobado! Reactivar y extender periodo
                            subscription.status = 'active'
                            
                            # Extender el periodo según billing_cycle
                            old_period_end = subscription.current_period_end
                            
                            if subscription.billing_cycle == 'yearly':
                                new_period_start = subscription.current_period_end
                                new_period_end = new_period_start + timedelta(days=365)
                            else:
                                new_period_start = subscription.current_period_end
                                new_period_end = new_period_start + timedelta(days=30)
                            
                            subscription.current_period_start = new_period_start
                            subscription.current_period_end = new_period_end
                            subscription.save()
                            
                            logger.info(f"   ✅ Pago APROBADO (después de {attempt * 5}s) - Suscripción REACTIVADA")
                            logger.info(f"   🔄 Periodo extendido:")
                            logger.info(f"      Periodo anterior finalizaba: {old_period_end}")
                            logger.info(f"      Nuevo periodo: {new_period_start} → {new_period_end}")
                            
                            # Notificar a n8n sobre la reactivación
                            notify_account_reactivation(company)
                            
                            messages.success(request, f'✅ Pago exitoso! Tu suscripción ha sido reactivada. Monto: ${amount:,.0f} COP')
                            transaction_status = 'APPROVED'  # Actualizar para no mostrar mensaje de pending
                            break
                        
                        elif updated_status in ['DECLINED', 'ERROR']:
                            # Rechazado - es un resultado normal, no un error del sistema
                            logger.info(f"   ❌ Pago rechazado durante polling: {updated_status}")
                            messages.warning(request, 'El pago fue rechazado. Por favor actualiza tu método de pago o contacta a tu banco.')
                            transaction_status = updated_status
                            break
                    else:
                        logger.warning(f"   ⚠️ No se pudo consultar estado de transacción en intento {attempt}")
                
                # Si después del polling sigue PENDING
                if transaction_status == 'PENDING':
                    logger.info(f"   ⏳ Transacción sigue PENDING después de 15 segundos")
                    logger.info(f"   ℹ️  El webhook de Wompi activará la suscripción cuando se apruebe")
                    messages.warning(request, '⏳ Tu pago está siendo procesado. Recibirás una notificación cuando sea aprobado y tu cuenta se reactivará automáticamente.')
                
            elif transaction_status in ['DECLINED', 'ERROR']:
                logger.info(f"   ❌ Pago rechazado: {transaction_status}")
                messages.warning(request, 'El pago fue rechazado. Por favor actualiza tu método de pago o contacta a tu banco.')
                
            else:
                logger.warning(f"   ⚠️ Estado desconocido: {transaction_status}")
                messages.warning(request, f'El pago está en proceso. Estado: {transaction_status}')
            
            return redirect('dashboard:dashboard')
            
        except Exception as charge_error:
            logger.error(f"   ❌ Error al crear transacción: {charge_error}")
            import traceback
            logger.error(traceback.format_exc())
            messages.error(request, f'Error al procesar el pago: {str(charge_error)}')
            return redirect('dashboard:dashboard')
        
    except Exception as e:
        logger.error(f"Error en retry_payment: {e}")
        import traceback
        logger.error(traceback.format_exc())
        messages.error(request, 'Error al procesar la solicitud')
        return redirect('dashboard:dashboard')
