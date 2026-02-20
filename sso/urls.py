from django.urls import path
from . import views

app_name = 'sso'

urlpatterns = [
    # API endpoint para generar tokens SSO (usado por n8n)
    path('api/sso/generate-token/', views.generate_sso_token, name='generate_token'),
    
    # Endpoint para login con token SSO (usado por usuarios)
    path('sso/login', views.sso_login, name='login'),
]
