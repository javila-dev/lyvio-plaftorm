from django.shortcuts import render
from subscriptions.models import Plan

def home(request):
    """Landing page principal"""
    # Obtener todos los planes activos ordenados por precio
    plans = Plan.objects.filter(is_active=True).order_by('price_monthly')
    
    context = {
        'plans': plans
    }
    return render(request, 'landing/home.html', context)

def pricing(request):
    """Página de precios"""
    return render(request, 'landing/pricing.html')

def features(request):
    """Página de características"""
    return render(request, 'landing/features.html')

def contact(request):
    """Página de contacto"""
    return render(request, 'landing/contact.html')
