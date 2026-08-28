from django.urls import path
from . import views

app_name = 'onboarding'

urlpatterns = [
    # Nuevo flujo simplificado
    path('', views.company_registration, name='company-registration'),
    path('bot-config/', views.bot_config, name='bot-config'),
    path('complete/', views.complete, name='complete'),
]