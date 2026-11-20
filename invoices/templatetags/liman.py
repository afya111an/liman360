from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def money(value):
    """187200 -> '187.200,00' (Turkish grouping and decimal comma)."""
    if value is None:
        return '—'
    return floatformat(value, '2g')
