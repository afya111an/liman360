from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from invoices.models import Invoice, Vessel

from .forms import BunkerForm, NoonForm, VesselForm, VoyageForm
from .models import BunkerDelivery, NoonFuel, NoonReport, Voyage, fuel_ledger

V = Voyage.Status
NEXT_LABEL = {V.LOADING: 'Yüklemeye başla', V.AT_SEA: 'Limandan ayrıldı', V.DISCHARGING: 'Tahliyeye başla',
              V.COMPLETED: 'Seferi tamamla'}
VOYAGE_FILTERS = {'': ('Açık seferler', Q(status__in=Voyage.OPEN)),
                  'denizde': ('Yolda', Q(status__in=Voyage.UNDERWAY)),
                  'planlanan': ('Planlanan', Q(status=V.PLANNED)),
                  'tamamlanan': ('Tamamlanan', Q(status=V.COMPLETED)),
                  'iptal': ('İptal edilen', Q(status=V.CANCELLED)),
                  'tumu': ('Tümü', Q())}


def _ctx(request, section, **kw):
    """Shared context: which subnav tab is active and what its "Yeni" button creates."""
    new = {'seferler': ('operations:voyage_create', 'sefer', 'operations.add_voyage'),
           'gemiler': ('operations:vessel_create', 'gemi', 'invoices.add_vessel'),
           'bunker': ('operations:bunker_create', 'ikmal', 'operations.add_bunkerdelivery'),
           'raporlar': ('operations:noon_create', 'rapor', 'operations.add_noonreport')}[section]
    kw.update(section=section, query=request.GET.urlencode(),
              new_url=reverse(new[0]) if request.user.has_perm(new[2]) else None, new_label=new[1])
    return kw


def _safe_next(request, fallback):
    nxt = request.POST.get('next', '')
    ok = url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return nxt if ok else fallback


# ---------------- voyages ----------------

@login_required
def voyage_list(request, pk=None):
    durum = request.GET.get('durum', '')
    title, cond = VOYAGE_FILTERS.get(durum, VOYAGE_FILTERS[''])
    qs = Voyage.objects.select_related('vessel', 'load_port', 'discharge_port').filter(cond)
    gemi = request.GET.get('gemi', '')
    if gemi.isdigit():
        qs = qs.filter(vessel_id=gemi)
    ctx = _ctx(request, 'seferler', page=Paginator(qs, 50).get_page(request.GET.get('sayfa')), title=title,
               durum=durum, gemi=gemi, filters=[(k, v[0]) for k, v in VOYAGE_FILTERS.items()],
               vessels=Vessel.objects.all(), selected=None,
               counts=dict(Voyage.objects.values_list('status').annotate(n=Count('pk'))))
    if pk is not None:
        v = get_object_or_404(Voyage.objects.select_related('vessel', 'load_port', 'discharge_port', 'charterer',
                                                            'created_by'), pk=pk)
        events = {e.status: e for e in v.events.select_related('user')}
        phases = []
        for s in Voyage.FLOW:
            idx, cur = Voyage.FLOW.index(s), (Voyage.FLOW.index(v.status) if v.status in Voyage.FLOW else -1)
            phases.append({'label': V(s).label, 'event': events.get(s),
                           'state': 'done' if idx < cur or v.status == V.COMPLETED else 'current' if idx == cur else 'todo'})
        invoices = list(v.invoices.exclude(status=Invoice.Status.REJECTED).select_related('supplier')
                        .order_by('invoice_date'))
        totals = {}
        for i in invoices:
            totals[i.currency] = totals.get(i.currency, 0) + i.amount
        # Same-currency costs only; with no such costs the net equals the freight.
        net = None if v.freight_total is None else v.freight_total - totals.get(v.freight_currency, 0)
        ctx.update(selected=v, phases=phases, cancel_event=events.get(V.CANCELLED), invoices=invoices,
                   # the freight currency's total first, the rest alphabetically
                   cost_totals=sorted(totals.items(), key=lambda kv: (kv[0] != v.freight_currency, kv[0])), net=net,
                   bunkers=v.bunkers.select_related('port', 'supplier').order_by('date'),
                   noons=[r for r in fuel_ledger(v.vessel) if r.voyage_id == v.pk][:5],
                   can_change=request.user.has_perm('operations.change_voyage') and v.editable,
                   next_label=NEXT_LABEL.get(v.next_status), today=timezone.localdate(),
                   here=request.get_full_path())
    return render(request, 'operations/voyages.html', ctx)


@login_required
def voyage_form(request, pk=None):
    v = get_object_or_404(Voyage, pk=pk) if pk else None
    if not request.user.has_perm('operations.change_voyage' if v else 'operations.add_voyage'):
        raise PermissionDenied
    if v and not v.editable:
        messages.error(request, 'Tamamlanan veya iptal edilen sefer değiştirilemez.')
        return redirect('operations:voyage_detail', pk=v.pk)
    form = VoyageForm(request.POST or None, instance=v)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not v:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f'{obj.number} kaydedildi.')
        return redirect('operations:voyage_detail', pk=obj.pk)
    return render(request, 'shared/form.html', _ctx(
        request, 'seferler', form=form, form_title=f'{v.number} düzenle' if v else 'Yeni sefer',
        submit_label='Kaydet', cancel_url=reverse('operations:voyage_detail', args=[v.pk]) if v
        else reverse('operations:voyages')))


@login_required
@require_POST
def voyage_action(request, pk):
    v = get_object_or_404(Voyage, pk=pk)
    nxt = _safe_next(request, reverse('operations:voyage_detail', args=[pk]))
    try:
        if request.POST.get('islem') == 'ilerle':
            try:
                on = date.fromisoformat(request.POST.get('tarih', ''))
            except ValueError:
                on = None
            v.advance(request.user, on)
            messages.success(request, f'{v.number}: {v.get_status_display().lower()}.')
        elif request.POST.get('islem') == 'iptal':
            v.cancel(request.user, request.POST.get('not', ''))
            messages.success(request, f'{v.number} iptal edildi.')
        else:
            raise ValidationError('Geçersiz işlem.')
    except (PermissionDenied, ValidationError) as e:
        messages.error(request, e.messages[0] if isinstance(e, ValidationError) else str(e))
    return redirect(nxt)


# ---------------- vessels ----------------

@login_required
def vessel_list(request, pk=None):
    qs = Vessel.objects.annotate(n_voyages=Count('voyages')).order_by('-active', 'name')
    ctx = _ctx(request, 'gemiler', page=Paginator(qs, 50).get_page(request.GET.get('sayfa')), selected=None)
    underway = {v.vessel_id: v for v in Voyage.objects.filter(status__in=Voyage.UNDERWAY)
                .select_related('load_port', 'discharge_port')}
    for s in ctx['page'].object_list:
        s.current = underway.get(s.pk)
    if pk is not None:
        s = get_object_or_404(Vessel, pk=pk)
        s.current = underway.get(s.pk)
        reports = fuel_ledger(s, limit=7)
        ctx.update(selected=s, last_report=reports[0] if reports else None, reports=reports,
                   voyages=s.voyages.select_related('load_port', 'discharge_port')[:10],
                   bunkers=s.bunkers.select_related('port')[:5],
                   can_change=request.user.has_perm('invoices.change_vessel'))
    return render(request, 'operations/vessels.html', ctx)


@login_required
def vessel_form(request, pk=None):
    s = get_object_or_404(Vessel, pk=pk) if pk else None
    if not request.user.has_perm('invoices.change_vessel' if s else 'invoices.add_vessel'):
        raise PermissionDenied
    form = VesselForm(request.POST or None, instance=s)
    if request.method == 'POST' and form.is_valid():
        s = form.save()
        messages.success(request, f'{s.name} kaydedildi.')
        return redirect('operations:vessel_detail', pk=s.pk)
    return render(request, 'shared/form.html', _ctx(
        request, 'gemiler', form=form, form_title=f'{s.name} düzenle' if s else 'Yeni gemi', submit_label='Kaydet',
        cancel_url=reverse('operations:vessel_detail', args=[s.pk]) if s else reverse('operations:vessels')))


# ---------------- bunker ----------------

@login_required
def bunker_list(request, pk=None):
    qs = BunkerDelivery.objects.select_related('vessel', 'port', 'supplier', 'voyage')
    gemi = request.GET.get('gemi', '')
    if gemi.isdigit():
        qs = qs.filter(vessel_id=gemi)
    totals = qs.order_by().values('grade').annotate(mt=Sum('quantity_mt')).order_by('grade')
    ctx = _ctx(request, 'bunker', page=Paginator(qs, 50).get_page(request.GET.get('sayfa')), totals=totals,
               gemi=gemi, vessels=Vessel.objects.all(), selected=None)
    if pk is not None:
        ctx['selected'] = get_object_or_404(qs.model.objects.select_related(
            'vessel', 'port', 'supplier', 'voyage', 'created_by'), pk=pk)
        ctx['can_edit'] = request.user.has_perm('operations.change_bunkerdelivery') and not settings.LIMAN_STATIC_DEMO
    return render(request, 'operations/bunkers.html', ctx)


@login_required
def bunker_form(request, pk=None):
    b = get_object_or_404(BunkerDelivery, pk=pk) if pk else None
    if not request.user.has_perm('operations.change_bunkerdelivery' if b else 'operations.add_bunkerdelivery'):
        raise PermissionDenied
    form = BunkerForm(request.POST or None, instance=b, initial=None if b else {
        'vessel': request.GET.get('gemi'), 'voyage': request.GET.get('sefer')})
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not b:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f'Bunker ikmali kaydedildi: {obj.grade}, BDN {obj.bdn_no}.')
        return redirect('operations:bunker_detail', pk=obj.pk)
    return render(request, 'shared/form.html', _ctx(
        request, 'bunker', form=form, form_title=f'BDN {b.bdn_no} düzenle' if b else 'Yeni bunker ikmali',
        submit_label='Kaydet', cancel_url=reverse('operations:bunker_detail', args=[b.pk]) if b
        else reverse('operations:bunkers')))


# ---------------- noon reports ----------------

@login_required
def noon_list(request, pk=None):
    vessels = list(Vessel.objects.filter(noon_reports__isnull=False).distinct())
    gemi = request.GET.get('gemi', '')
    selected = get_object_or_404(NoonReport.objects.select_related('vessel', 'voyage', 'created_by'), pk=pk) if pk else None
    vessel = selected.vessel if selected else next((v for v in vessels if str(v.pk) == gemi), vessels[0] if vessels else None)
    reports = fuel_ledger(vessel) if vessel else []
    if selected:
        selected = next(r for r in reports if r.pk == selected.pk)
    page = Paginator(reports, 60).get_page(request.GET.get('sayfa'))
    ctx = _ctx(request, 'raporlar', page=page, vessel=vessel, vessels=vessels, selected=selected,
               flagged=sum(1 for r in reports if r.flagged),
               can_edit=request.user.has_perm('operations.change_noonreport') and not settings.LIMAN_STATIC_DEMO)
    ctx['query'] = f'gemi={vessel.pk}' if vessel else ''
    return render(request, 'operations/noon.html', ctx)


def _fuel_context(exclude_pk=None):
    """Per active vessel: recent reports' ROB per grade and recent bunkers, so the entry page can show
    previous ROB + bunkered for whatever ship and date are chosen (computed in the browser)."""
    since = timezone.localdate() - timedelta(days=60)
    data = {}
    for s in Vessel.objects.filter(active=True):
        reports = [{'date': r.date.isoformat(), 'rob': {f.grade: str(f.rob_mt) for f in r.fuels.all()}}
                   for r in s.noon_reports.filter(date__gte=since).exclude(pk=exclude_pk).prefetch_related('fuels')]
        bunkers = [{'date': b.date.isoformat(), 'grade': b.grade, 'mt': str(b.quantity_mt)}
                   for b in s.bunkers.filter(date__gte=since)]
        data[s.pk] = {'reports': reports, 'bunkers': bunkers}
    return data


@login_required
def noon_form(request, pk=None):
    report = get_object_or_404(NoonReport, pk=pk) if pk else None
    if not request.user.has_perm('operations.change_noonreport' if report else 'operations.add_noonreport'):
        raise PermissionDenied
    initial = {'vessel': request.GET.get('gemi')}
    if report:
        initial = {f'{k}_{f.grade}': v for f in report.fuels.all() for k, v in (('cons', f.consumed_mt), ('rob', f.rob_mt))}
    form = NoonForm(request.POST or None, instance=report, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            r = form.save(commit=False)
            if not report:
                r.created_by = request.user
            r.voyage = (Voyage.objects.filter(vessel=r.vessel, actual_departure__lte=r.date)
                        .filter(Q(actual_arrival__gte=r.date) | Q(actual_arrival__isnull=True))
                        .exclude(status=V.CANCELLED).order_by('-actual_departure').first())
            r.save()
            r.fuels.all().delete()  # an edit replaces the fuel rows as entered
            NoonFuel.objects.bulk_create([NoonFuel(report=r, grade=g, consumed_mt=c, rob_mt=rob)
                                          for g, (c, rob) in form.fuel_rows.items()])
        flagged = next(x for x in fuel_ledger(r.vessel) if x.pk == r.pk).flagged
        (messages.error if flagged else messages.success)(
            request, f'{r.vessel} · {r.date:%d.%m.%Y} raporu kaydedildi.'
            + (' ROB hesabı tutmuyor; değerleri kontrol edin.' if flagged else ''))
        return redirect('operations:noon_detail', pk=r.pk)
    return render(request, 'operations/noon_form.html', _ctx(
        request, 'raporlar', form=form, report=report, fuel_data=_fuel_context(report.pk if report else None)))
