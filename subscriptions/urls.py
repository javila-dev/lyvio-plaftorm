from django.urls import path
from . import views
from dashboard import views as dashboard_views

app_name = 'dashboard'

urlpatterns = [
    # Portal de billing
    path('', views.billing_dashboard, name='dashboard'),
    path('login/', views.billing_login, name='login'),
    path('logout/', views.billing_logout, name='logout'),
    
    # Gestión de plan
    path('plan/', views.billing_plan_details, name='plan_details'),
    path('settings/', dashboard_views.settings, name='settings'),
    path('plan/activate/<int:plan_id>/', views.billing_activate_plan, name='activate_plan'),
    path('plan/billing-info/', views.billing_info, name='billing_info'),
    path('plan/upgrade/<int:plan_id>/', views.billing_upgrade_plan, name='upgrade_plan'),
    path('cancel/', views.billing_cancel_subscription, name='cancel_subscription'),
    
    # Reactivación de suscripciones
    path('reactivate/', views.reactivate_subscription, name='reactivate_subscription'),
    path('renew/', views.renew_expired_subscription, name='renew_expired_subscription'),
    
    # Historial de pagos
    path('payments/', views.billing_payment_history, name='payment_history'),
    path('invoice/<int:invoice_id>/', views.billing_invoice_detail, name='invoice_detail'),
    
    # Respuesta de pago
    path('payment/success/', views.payment_success, name='payment_success'),
    
    # Webhooks
    path('wompi/webhook/', views.wompi_webhook, name='wompi-webhook'),
    
    # Gestión de método de pago
    path('payment-method/update/', views.update_payment_method, name='update_payment_method'),
    path('payment/retry/', views.retry_payment, name='retry_payment'),
    
    # Cobros automáticos para N8N
    path('recurring-payments/', views.process_recurring_payments, name='recurring-payments'),
    path('payment-source/', views.manage_payment_source, name='manage-payment-source'),
    
    # API endpoints para N8N (desde dashboard app)
    path('api/companies/status/', dashboard_views.api_companies_status, name='api_companies_status'),
    path('api/companies/summary/', dashboard_views.api_companies_summary, name='api_companies_summary'),
    path('api/companies/<int:company_id>/', dashboard_views.api_company_detail, name='api_company_detail'),
    path('api/trials/active/', dashboard_views.api_trials_active, name='api_trials_active'),
    path('api/subscriptions/active/', dashboard_views.api_active_subscriptions, name='api_active_subscriptions'),
    path('api/subscriptions/by-chatwoot-account/', dashboard_views.api_subscription_by_chatwoot, name='api_subscription_by_chatwoot'),
    path('api/subscriptions/<int:subscription_id>/charge-payload/', dashboard_views.api_subscription_charge_payload, name='api_subscription_charge_payload'),
    path('api/subscriptions/<int:subscription_id>/verify-transaction/', dashboard_views.api_verify_transaction, name='api_verify_transaction'),
    path('api/subscriptions/<int:subscription_id>/suspend/', dashboard_views.api_suspend_subscription, name='api_suspend_subscription'),
    path('api/subscriptions/cancelled-to-suspend/', dashboard_views.api_cancelled_subscriptions_to_suspend, name='api_cancelled_subscriptions_to_suspend'),
    path('api/debug/auth/', dashboard_views.api_debug_auth, name='api_debug_auth'),
]
