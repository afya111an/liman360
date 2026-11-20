from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def money(value):
    """187200 -> '187.200,00' (Turkish grouping and decimal comma)."""
    if value is None:
        return '—'
    return floatformat(value, '2g')


@register.filter
def iban(value):
    """TR330006100519786457841326 -> 'TR33 0006 1005 1978 6457 8413 26'."""
    v = (value or '').replace(' ', '')
    return ' '.join(v[i:i + 4] for i in range(0, len(v), 4))
