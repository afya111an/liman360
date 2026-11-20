from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import InvoiceForm
from .models import ApprovalLevel, Company, Invoice, Vessel, waiting_for


def _filtered(request, scope):
    qs = Invoice.objects.select_related('supplier', 'company', 'vessel')
    if scope == 'pool':
        return qs.filter(pk__in=waiting_for(request.user)), {}
    f = {k: request.GET.get(k, '').strip() for k in ('durum', 'sirket', 'gemi', 'q')}
    if f['durum'] in Invoice.Status.values:
        qs = qs.filter(status=f['durum'])
    if f['sirket'].isdigit():
        qs = qs.filter(company_id=f['sirket'])
    if f['gemi'].isdigit():
        qs = qs.filter(vessel_id=f['gemi'])
    if f['q']:
        qs = qs.filter(Q(number__icontains=f['q']) | Q(ref_no__icontains=f['q'])
                       | Q(supplier__name__icontains=f['q']) | Q(description__icontains=f['q']))
    return qs, f


@login_required
def invoice_list(request, scope, pk=None):
    qs, filters = _filtered(request, scope)
    totals = qs.order_by().values('currency').annotate(total=Sum('amount'), n=Count('pk')).order_by('currency')
    page = Paginator(qs, 50).get_page(request.GET.get('sayfa'))
    selected = None
    if pk is not None:
        selected = get_object_or_404(Invoice.objects.select_related(
            'supplier', 'company', 'vessel', 'category', 'created_by'), pk=pk)
    ctx = {
        'scope': scope,
        'page': page,
        'totals': list(totals),
        'filters': filters,
        'statuses': Invoice.Status.choices,
        'companies': Company.objects.all() if scope == 'all' else [],
        'vessels': Vessel.objects.all() if scope == 'all' else [],
        'query': request.GET.urlencode(),
        'selected': selected,
    }
    if selected:
        decisions = {a.level_id: a for a in selected.approvals.select_related('level', 'user')}
        recent = [a for a in decisions.values() if timezone.now() - a.at < timedelta(seconds=15)]
        ctx.update({
            'steps': [(lv, decisions.get(lv.pk)) for lv in ApprovalLevel.objects.select_related('group')],
            'next_level': selected.next_level(),
            'can_decide': selected.can_decide(request.user),
            'decided_here': request.get_full_path(),
            'fresh': recent[-1].pk if recent else None,  # the stamp just placed gets its landing motion
            'fresh_final': bool(recent) and selected.status != Invoice.Status.PENDING,
            'final_at': max((a.at for a in decisions.values()), default=None),
            # Field numbers continue after the optional notes box.
            'n_entered': 11 if selected.notes else 10,
            'n_stamps': 12 if selected.notes else 11,
            'n_decide': 13 if selected.notes else 12,
        })
    return render(request, 'invoices/list.html', ctx)


@login_required
@require_POST
def invoice_decide(request, pk):
    inv = get_object_or_404(Invoice, pk=pk)
    action = request.POST.get('karar')
    nxt = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        nxt = reverse('invoices:all_detail', args=[pk])
    if action not in ('onayla', 'reddet'):
        messages.error(request, 'Geçersiz işlem.')
        return redirect(nxt)
    try:
        inv.decide(request.user, approve=action == 'onayla', note=request.POST.get('gerekce', ''))
    except (PermissionDenied, ValidationError) as e:
        messages.error(request, e.messages[0] if isinstance(e, ValidationError) else str(e))
    else:
        if action == 'reddet':
            messages.success(request, f'{inv.number} reddedildi.')
        elif inv.status == Invoice.Status.APPROVED:
            messages.success(request, f'{inv.number} tüm onaylardan geçti.')
        else:
            messages.success(request, f'{inv.number} onaylandı; sıradaki onay adımına geçti.')
    return redirect(nxt)


@login_required
def invoice_create(request):
    form = InvoiceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        inv = form.save(commit=False)
        inv.created_by = request.user
        if not ApprovalLevel.objects.exists():
            inv.status = Invoice.Status.APPROVED
        inv.save()
        messages.success(request, f'{inv.number} kaydedildi ve onaya gönderildi.'
                         if inv.status == Invoice.Status.PENDING else f'{inv.number} kaydedildi.')
        return redirect('invoices:all_detail', pk=inv.pk)
    return render(request, 'invoices/create.html', {'form': form})
