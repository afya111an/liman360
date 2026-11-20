import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from invoices.models import Invoice

from .forms import OrderForm, PickForm
from .models import BankAccount, OrderInvalid, PaymentLine, PaymentOrder, create_order, payable_invoices, with_balances

S = PaymentOrder.Status
SCOPES = {'onay': [S.PENDING], 'odenecek': [S.APPROVED], 'tumu': None}
DETAIL = {'onay': 'payments:pending_detail', 'odenecek': 'payments:topay_detail', 'tumu': 'payments:all_detail'}
can_view = permission_required('payments.view_paymentorder', raise_exception=True)


@login_required
@can_view
def order_list(request, scope, pk=None):
    qs = PaymentOrder.objects.select_related('supplier', 'company', 'account').annotate(sum_total=Sum('lines__amount'))
    durum = request.GET.get('durum', '')
    if SCOPES[scope]:
        qs = qs.filter(status__in=SCOPES[scope])
    elif durum in S.values:
        qs = qs.filter(status=durum)
    totals = (PaymentLine.objects.filter(order__in=qs.values('pk')).values('order__currency')
              .annotate(total=Sum('amount'), n=Count('order', distinct=True)).order_by('order__currency'))
    page = Paginator(qs.order_by(*PaymentOrder._meta.ordering), 50).get_page(request.GET.get('sayfa'))
    ctx = {'scope': scope, 'page': page, 'totals': list(totals), 'durum': durum, 'statuses': S.choices,
           'query': request.GET.urlencode(), 'detail_url': DETAIL[scope], 'selected': None}
    if pk is not None:
        o = get_object_or_404(PaymentOrder.objects.select_related(
            'supplier', 'company', 'account', 'created_by', 'decided_by', 'paid_by', 'cancelled_by'), pk=pk)
        lines = list(o.lines.select_related('invoice'))
        bal = {i.pk: i for i in with_balances(Invoice.objects.filter(pk__in=[ln.invoice_id for ln in lines]))}
        for ln in lines:
            ln.open = ln.invoice.amount - bal[ln.invoice_id].committed
            ln.paid_total = bal[ln.invoice_id].paid
        ctx.update(selected=o, lines=lines, total=sum((ln.amount for ln in lines), Decimal('0')),
                   can_decide=o.can_decide(request.user), can_pay=o.can_pay(request.user),
                   can_cancel=o.can_cancel(request.user), here=request.get_full_path(), today=date.today(),
                   fresh=_fresh(o), n=_numbers(o))
    return render(request, 'payments/list.html', ctx)


def _fresh(o):
    """Which stamp was placed in the last 15 seconds, so it gets the landing motion."""
    def recent(t):
        return t is not None and not settings.LIMAN_STATIC_DEMO and timezone.now() - t < timedelta(seconds=15)
    for name, t in (('cancel', o.cancelled_at), ('paid', o.paid_recorded_at), ('decision', o.decided_at)):
        if recent(t):
            return name
    return None


def _numbers(o):
    """Field numbers after the optional note box."""
    made = 9 if o.note else 8
    return {'made': made, 'stamps': made + 1, 'act': made + 2}


@login_required
@require_POST
def order_action(request, pk):
    o = get_object_or_404(PaymentOrder, pk=pk)
    nxt = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        nxt = reverse('payments:all_detail', args=[pk])
    act, note = request.POST.get('islem'), request.POST.get('not', '')
    try:
        if act in ('onayla', 'reddet'):
            o.decide(request.user, approve=act == 'onayla', note=note)
        elif act == 'ode':
            try:
                paid_on = date.fromisoformat(request.POST.get('odeme_tarihi', ''))
            except ValueError:
                paid_on = None
            o.mark_paid(request.user, paid_on, request.POST.get('dekont', ''))
        elif act == 'iptal':
            o.cancel(request.user, note)
        else:
            raise ValidationError('Geçersiz işlem.')
    except (PermissionDenied, ValidationError) as e:
        messages.error(request, e.messages[0] if isinstance(e, ValidationError) else str(e))
    else:
        messages.success(request, f'{o.number}: {o.get_status_display().lower()}.')
    return redirect(nxt)


def _amounts(post, invoices):
    """Read tutar_<pk> inputs. Returns ({pk: Decimal}, {pk: error})."""
    amounts, errors = {}, {}
    for inv in invoices:
        raw = post.get(f'tutar_{inv.pk}', '').strip().replace(' ', '')
        if not raw:
            continue
        # Accept Turkish "1.250,50" and "1.250" as well as "1250.50" (same rules as the page's total).
        if ',' in raw or re.fullmatch(r'\d{1,3}(\.\d{3})+', raw):
            raw = raw.replace('.', '').replace(',', '.')
        try:
            amounts[inv.pk] = Decimal(raw).quantize(Decimal('0.01'))
        except InvalidOperation:
            errors[inv.pk] = 'Geçerli bir tutar yazın.'
    return amounts, errors


@login_required
@permission_required('payments.add_paymentorder', raise_exception=True)
def order_create(request):
    pick = PickForm(request.GET or None)
    ctx = {'pick': pick, 'scope': 'yeni'}
    if pick.is_valid():
        company, supplier, currency = (pick.cleaned_data[k] for k in ('sirket', 'cari', 'doviz'))
        invoices = payable_invoices(company, supplier, currency)
        for inv in invoices:
            inv.open = inv.amount - inv.committed
        accounts = BankAccount.objects.filter(company=company, currency=currency, active=True)
        line_errors = {}
        if request.method == 'POST':
            form = OrderForm(request.POST, accounts=accounts)
            amounts, line_errors = _amounts(request.POST, invoices)
            if form.is_valid() and not line_errors:
                try:
                    order = create_order(request.user, company=company, supplier=supplier, currency=currency,
                                         amounts=amounts, **form.cleaned_data)
                except OrderInvalid as e:
                    for field, msg in e.fields.items():
                        form.add_error(field if field in form.fields else None, msg)
                    line_errors = e.lines
                else:
                    messages.success(request, f'{order.number} oluşturuldu ve onaya gönderildi.')
                    return redirect('payments:pending_detail', pk=order.pk)
        else:
            first = accounts.first() if accounts.count() == 1 else None
            form = OrderForm(accounts=accounts, initial={'payee_iban': supplier.iban, 'account': first})
        for inv in invoices:
            inv.error = line_errors.get(inv.pk)
            inv.entered = request.POST.get(f'tutar_{inv.pk}', '') if request.method == 'POST' else ''
        ctx.update(form=form, invoices=invoices, accounts=accounts, company=company, supplier=supplier,
                   currency=currency)
    return render(request, 'payments/create.html', ctx)
