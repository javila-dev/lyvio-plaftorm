"""
Decoradores personalizados para autenticación con Chatwoot
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test

def chatwoot_login_required(view_func):
    """
    Decorador que requiere autenticación vía Chatwoot SSO
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Redirigir al sistema SSO en lugar del login de Django
            next_url = request.get_full_path()
            return redirect(f'/auth/chatwoot/required/?next={next_url}')
        return view_func(request, *args, **kwargs)
    return wrapper

def company_required(view_func):
    """
    Decorador que requiere que el usuario tenga una empresa asociada
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'company') or not request.user.company:
            from django.contrib import messages
            messages.error(request, 'No tienes una empresa asociada. Completa el registro primero.')
            return redirect('onboarding:company-registration')
        return view_func(request, *args, **kwargs)
    return wrapper