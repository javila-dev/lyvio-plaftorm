from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplica dos números"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Resta dos números"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Suma dos números"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Divide dos números"""
    try:
        return float(value) / float(arg) if float(arg) != 0 else 0
    except (ValueError, TypeError):
        return 0

@register.filter
def currency(value):
    """Formatea un número como moneda colombiana"""
    try:
        # Convertir a float si es necesario
        if isinstance(value, (str, Decimal)):
            value = float(value)
        # Formatear con separadores de miles
        return f"${value:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return "$0"

@register.filter
def percentage(value, total):
    """Calcula el porcentaje de value respecto a total"""
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0