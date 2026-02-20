from django.utils import timezone
from accounts.models import Company, User, Trial
from subscriptions.models import Subscription
from bots.models import BotConfig


def serialize_company_status(company):
    """Serializar el estado completo de una empresa para API"""
    
    def get_admin_name():
        """Obtener nombre completo del administrador"""
        parts = []
        if company.admin_first_name:
            parts.append(company.admin_first_name)
        if company.admin_last_name:
            parts.append(company.admin_last_name)
        return ' '.join(parts) if parts else None

    def get_admin_first_name():
        """Obtener primer nombre del administrador"""
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
    
    def get_admin_last_name():
        """Obtener apellido del administrador"""
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

    def get_admin_email():
        """Obtener email del primer usuario administrador"""
        admin_user = company.users.filter(is_staff=True).first()
        if admin_user:
            return admin_user.email
        # Si no hay admin, devolver el primer usuario
        first_user = company.users.first()
        return first_user.email if first_user else None

    def get_admin_phone():
        """Obtener teléfono del administrador"""
        # Primero intentar del usuario admin
        admin_user = company.users.filter(is_staff=True).first()
        if admin_user and admin_user.phone:
            return admin_user.phone
        # Luego del primer usuario
        first_user = company.users.first()
        if first_user and first_user.phone:
            return first_user.phone
        # Finalmente del teléfono de la empresa
        return company.phone if company.phone else None

    def get_plan_type():
        """Determinar tipo de plan"""
        try:
            subscription = company.subscription
            if subscription and subscription.is_active:
                return 'subscription'
        except:
            pass
        
        try:
            trial = company.trial
            if trial:
                return 'trial'
        except:
            pass
        
        return 'no_plan'

    def get_plan_status():
        """Estado del plan"""
        plan_type = get_plan_type()
        
        if plan_type == 'subscription':
            return 'active'
        elif plan_type == 'trial':
            try:
                trial = company.trial
                if trial.is_active:
                    return 'trial_active'
                else:
                    return 'trial_expired'
            except:
                return 'trial_expired'
        else:
            return 'inactive'

    def get_plan_name():
        """Nombre del plan"""
        plan_type = get_plan_type()
        
        if plan_type == 'subscription':
            try:
                subscription = company.subscription
                return subscription.plan.name if hasattr(subscription, 'plan') else 'Plan Pagado'
            except:
                return 'Plan Pagado'
        elif plan_type == 'trial':
            try:
                trial = company.trial
                return f'Trial {trial.status.title()}'
            except:
                return 'Trial'
        else:
            return 'Sin Plan'

    def get_expiry_date():
        """Fecha de expiración"""
        plan_type = get_plan_type()
        
        if plan_type == 'subscription':
            try:
                subscription = company.subscription
                return subscription.end_date.strftime('%Y-%m-%d') if subscription.end_date else None
            except:
                return None
        elif plan_type == 'trial':
            try:
                trial = company.trial
                return trial.end_date.strftime('%Y-%m-%d') if trial.end_date else None
            except:
                return None
        else:
            return None

    def get_days_remaining():
        """Días restantes"""
        plan_type = get_plan_type()
        now = timezone.now()
        
        if plan_type == 'subscription':
            try:
                subscription = company.subscription
                if subscription.end_date:
                    return (subscription.end_date - now).days
            except:
                pass
        elif plan_type == 'trial':
            try:
                trial = company.trial
                if trial.end_date:
                    remaining = (trial.end_date - now).days
                    return max(0, remaining)
            except:
                pass
        
        return 0

    def get_is_active():
        """¿Está activo el plan?"""
        plan_status = get_plan_status()
        return plan_status in ['active', 'trial_active']

    def get_trial_resources():
        """Recursos del trial"""
        try:
            trial = company.trial
            if trial:
                return {
                    'messages': {
                        'used': trial.current_messages,
                        'limit': trial.max_messages,
                        'percentage': round((trial.current_messages / trial.max_messages * 100), 1) if trial.max_messages > 0 else 0
                    },
                    'conversations': {
                        'used': trial.current_conversations,
                        'limit': trial.max_conversations,
                        'percentage': round((trial.current_conversations / trial.max_conversations * 100), 1) if trial.max_conversations > 0 else 0
                    },
                    'documents': {
                        'used': trial.current_documents,
                        'limit': trial.max_documents,
                        'percentage': round((trial.current_documents / trial.max_documents * 100), 1) if trial.max_documents > 0 else 0
                    }
                }
        except:
            pass
        
        return None

    def get_chatwoot_info():
        """Información de Chatwoot"""
        chatwoot_data = {
            'account_id': company.chatwoot_account_id,
            'access_token': company.chatwoot_access_token,
            'is_connected': bool(company.chatwoot_account_id),
            'users_with_chatwoot': []
        }
        
        # Obtener usuarios con ID de Chatwoot
        users_with_chatwoot = company.users.filter(chatwoot_user_id__isnull=False)
        for user in users_with_chatwoot:
            chatwoot_data['users_with_chatwoot'].append({
                'email': user.email,
                'chatwoot_user_id': user.chatwoot_user_id
            })
        
        return chatwoot_data

    def get_usage_metrics():
        """Métricas de uso"""
        try:
            # Contar usuarios
            user_count = company.users.count()
            
            # Contar bots
            bot_count = BotConfig.objects.filter(company=company).count()
            
            # Contar documentos
            document_count = 0
            for bot in BotConfig.objects.filter(company=company):
                document_count += bot.documents.count()
            
            return {
                'users': user_count,
                'bots': bot_count,
                'documents': document_count,
                'has_active_users': user_count > 0,
                'has_bots_configured': bot_count > 0
            }
        except Exception as e:
            return {
                'users': 0,
                'bots': 0,
                'documents': 0,
                'has_active_users': False,
                'has_bots_configured': False,
                'error': str(e)
            }

    # Construir el diccionario de datos
    return {
        # Información básica
        'id': company.id,
        'name': company.name,
        'email': company.email,
        'phone': company.phone,
        'address': company.address,
        'website': company.website,
        
        # Información del admin
        'admin_name': get_admin_name(),
        'admin_first_name': get_admin_first_name(),
        'admin_last_name': get_admin_last_name(),
        'admin_email': get_admin_email(),
        'admin_phone': get_admin_phone(),
        
        # Estado del plan
        'plan_type': get_plan_type(),
        'plan_status': get_plan_status(),
        'plan_name': get_plan_name(),
        'expiry_date': get_expiry_date(),
        'days_remaining': get_days_remaining(),
        'is_active': get_is_active(),
        
        # Recursos
        'trial_resources': get_trial_resources(),
        
        # Chatwoot
        'chatwoot_info': get_chatwoot_info(),
        
        # Métricas
        'usage_metrics': get_usage_metrics(),
        
        # Fechas
        'registration_date': company.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'last_updated': company.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
    }


def serialize_companies_list(companies):
    """Serializar lista completa de empresas"""
    return [serialize_company_status(company) for company in companies]