from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import HttpResponse

def health_check(request):
    """Endpoint liviano para el HEALTHCHECK del Dockerfile/Traefik."""
    return HttpResponse('ok')

def home_redirect(request):
    """Redirigir a dashboard para usuarios autenticados"""
    if request.user.is_authenticated and hasattr(request.user, 'company'):
        return redirect('dashboard:dashboard')
    # Redirigir a Lyvio para usuarios no autenticados
    return redirect('https://app.lyvio.io')

urlpatterns = [
    path('health/', health_check),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('activation/', include('activation.urls')),
    path('onboarding/', include('onboarding.urls')),
    path('bot-builder/', include('bot_builder.urls')),
    path('admin-dashboard/', include('dashboard.urls')),  # Admin/staff portal
    path('dashboard/', include('subscriptions.urls')),  # Portal de billing/dashboard
    path('', include('landing.urls')),  # Landing page
    path('', include('sso.urls')),  # SSO endpoints
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
