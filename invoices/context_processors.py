from django.conf import settings

from .models import Currency, ExchangeRate, waiting_for


def _payment_counts(user):
    if not user.has_perm('payments.view_paymentorder'):
        return None
    from payments.models import PaymentOrder
    qs = PaymentOrder.objects
    return {'pending': qs.filter(status=PaymentOrder.Status.PENDING).exclude(created_by=user).count(),
            'topay': qs.filter(status=PaymentOrder.Status.APPROVED).count()}


def _underway():
    from operations.models import Voyage
    return Voyage.objects.filter(status__in=Voyage.UNDERWAY).count()


def shell(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    rates = [(c, ExchangeRate.objects.filter(currency=c).first()) for c in (Currency.USD, Currency.EUR)]
    return {
        'static_demo': getattr(settings, 'LIMAN_STATIC_DEMO', False),
        'shell_rates': [(c, r) for c, r in rates if r],
        'shell_pool_count': len(waiting_for(request.user)),
        'shell_pay_counts': _payment_counts(request.user),
        'shell_underway': _underway(),
    }
