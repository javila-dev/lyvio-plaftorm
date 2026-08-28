from django.urls import path
from . import views

app_name = 'auth'

urlpatterns = [
    path('chatwoot/callback/', views.chatwoot_login_callback, name='chatwoot_callback'),
    path('chatwoot/required/', views.chatwoot_login_required, name='chatwoot_required'),
    path('chatwoot/check/', views.chatwoot_session_check, name='session_check'),
    path('chatwoot/webhook/', views.chatwoot_auth_webhook, name='chatwoot_webhook'),
    path('logout/', views.logout_view, name='logout'),
]