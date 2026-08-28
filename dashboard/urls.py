from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    # Dashboard web views
    path('', views.dashboard_home, name='home'),
    path('settings/', views.settings, name='settings'),
    path('admin/', views.admin_dashboard, name='admin'),
    
    # API endpoints para N8N
    path('api/companies/status/', views.api_companies_status, name='api_companies_status'),
    path('api/companies/summary/', views.api_companies_summary, name='api_companies_summary'),
    path('api/companies/<int:company_id>/', views.api_company_detail, name='api_company_detail'),
    path('api/trials/active/', views.api_trials_active, name='api_trials_active'),
    path('api/subscriptions/active/', views.api_active_subscriptions, name='api_active_subscriptions'),
    path('api/subscriptions/by-chatwoot-account/', views.api_subscription_by_chatwoot, name='api_subscription_by_chatwoot'),
    path('api/subscriptions/<int:subscription_id>/charge-payload/', views.api_subscription_charge_payload, name='api_subscription_charge_payload'),
    path('api/subscriptions/<int:subscription_id>/verify-transaction/', views.api_verify_transaction, name='api_verify_transaction'),
    path('api/subscriptions/<int:subscription_id>/suspend/', views.api_suspend_subscription, name='api_suspend_subscription'),
    path('api/debug/auth/', views.api_debug_auth, name='api_debug_auth'),
]
