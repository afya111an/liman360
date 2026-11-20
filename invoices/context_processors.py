from django.conf import settings

from .models import Currency, ExchangeRate, waiting_for


def shell(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    rates = [(c, ExchangeRate.objects.filter(currency=c).first()) for c in (Currency.USD, Currency.EUR)]
    return {
        'static_demo': getattr(settings, 'LIMAN_STATIC_DEMO', False),
        'shell_rates': [(c, r) for c, r in rates if r],
        'shell_pool_count': len(waiting_for(request.user)),
    }
