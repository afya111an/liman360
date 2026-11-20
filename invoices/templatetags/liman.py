from django import template
from decimal import Decimal

from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def money(value):
    """187200 -> '187.200,00' (Turkish grouping and decimal comma)."""
    if value is None:
        return '—'
    return floatformat(value, '2g')


@register.filter
def mt(value):
    """Tonnage with only the decimals it has, up to three: 28500.000 -> '28.500', 650.500 -> '650,5'."""
    if value is None:
        return '—'
    d = Decimal(value).quantize(Decimal('0.001')).normalize()
    places = max(0, -d.as_tuple().exponent)
    return floatformat(d, f'{places}g')


@register.filter
def mt_input(value):
    """Value for a tonnage <input>: stored Decimals formatted like mt(), typed text passed through."""
    if value in (None, ''):
        return ''
    return mt(value) if isinstance(value, Decimal) else value


@register.filter
def iban(value):
    """TR330006100519786457841326 -> 'TR33 0006 1005 1978 6457 8413 26'."""
    v = (value or '').replace(' ', '')
    return ' '.join(v[i:i + 4] for i in range(0, len(v), 4))
