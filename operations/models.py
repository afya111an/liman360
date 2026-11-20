from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from invoices.models import Currency, Invoice, Supplier, Vessel

MT = dict(max_digits=10, decimal_places=3)


class Port(models.Model):
    name = models.CharField('liman', max_length=100)
    country = models.CharField('ülke', max_length=60)
    unlocode = models.CharField('UN/LOCODE', max_length=5, blank=True, help_text='ör. TRMER')

    class Meta:
        verbose_name = 'liman'
        verbose_name_plural = 'limanlar'
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['name', 'country'], name='uniq_port')]

    def __str__(self):
        return self.name


class FuelGrade(models.TextChoices):
    VLSFO = 'VLSFO', 'VLSFO'
    HSFO = 'HSFO', 'HSFO'
    LSMGO = 'LSMGO', 'LSMGO'
    MGO = 'MGO', 'MGO'


GRADE_ORDER = {g: i for i, g in enumerate(FuelGrade.values)}  # one grade order on every screen


class Voyage(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'PLANNED', 'Planlandı'
        LOADING = 'LOADING', 'Yüklemede'
        AT_SEA = 'AT_SEA', 'Denizde'
        DISCHARGING = 'DISCHARGING', 'Tahliyede'
        COMPLETED = 'COMPLETED', 'Tamamlandı'
        CANCELLED = 'CANCELLED', 'İptal edildi'

    FLOW = [Status.PLANNED, Status.LOADING, Status.AT_SEA, Status.DISCHARGING, Status.COMPLETED]
    UNDERWAY = [Status.LOADING, Status.AT_SEA, Status.DISCHARGING]
    OPEN = [Status.PLANNED, *UNDERWAY]

    number = models.CharField('sefer no', max_length=30, unique=True)
    vessel = models.ForeignKey(Vessel, on_delete=models.PROTECT, related_name='voyages', verbose_name='gemi')
    load_port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name='+', verbose_name='yükleme limanı')
    discharge_port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name='+',
                                       verbose_name='tahliye limanı')
    planned_departure = models.DateField('planlanan kalkış')
    planned_arrival = models.DateField('planlanan varış')
    actual_departure = models.DateField('gerçekleşen kalkış', null=True, blank=True)
    actual_arrival = models.DateField('gerçekleşen varış', null=True, blank=True)
    cargo = models.CharField('yük', max_length=100, blank=True)
    cargo_mt = models.DecimalField('yük miktarı (MT)', null=True, blank=True,
                                   validators=[MinValueValidator(Decimal('0'))], **MT)
    charterer = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name='+',
                                  verbose_name='kiracı (charterer)')
    freight_rate = models.DecimalField('navlun (MT başına)', max_digits=12, decimal_places=2, null=True, blank=True,
                                       validators=[MinValueValidator(Decimal('0'))])
    freight_currency = models.CharField('navlun para birimi', max_length=3, choices=Currency.choices,
                                        default=Currency.USD)
    status = models.CharField('durum', max_length=12, choices=Status.choices, default=Status.PLANNED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'sefer'
        verbose_name_plural = 'seferler'
        ordering = ['-planned_departure', '-pk']

    def __str__(self):
        return self.number

    def clean(self):
        errors = {}
        if self.planned_departure and self.planned_arrival and self.planned_arrival < self.planned_departure:
            errors['planned_arrival'] = 'Planlanan varış, kalkıştan önce olamaz.'
        if self.actual_departure and self.actual_arrival and self.actual_arrival < self.actual_departure:
            errors['actual_arrival'] = 'Gerçekleşen varış, kalkıştan önce olamaz.'
        if errors:
            raise ValidationError(errors)

    @property
    def freight_total(self):
        if self.freight_rate is None or self.cargo_mt is None:
            return None
        return (self.freight_rate * self.cargo_mt).quantize(Decimal('0.01'))

    @property
    def next_status(self):
        if self.status not in self.FLOW[:-1]:
            return None
        return self.FLOW[self.FLOW.index(self.status) + 1]

    @property
    def editable(self):
        return self.status in self.OPEN

    def advance(self, user, on_date):
        """Move to the next phase. Leaving port sets the actual departure, completing sets the actual arrival."""
        if not user.has_perm('operations.change_voyage'):
            raise PermissionDenied('Sefer güncelleme yetkiniz yok.')
        if on_date is None or on_date > timezone.localdate():
            raise ValidationError('Tarih bugünden ileri olamaz.')
        with transaction.atomic():
            v = Voyage.objects.select_for_update().get(pk=self.pk)
            nxt = v.next_status
            if nxt is None:
                raise ValidationError('Bu sefer ilerletilemez.')
            if nxt == self.Status.LOADING:
                # Lock the ship's voyages so two voyages cannot start on one ship at once.
                busy = (Voyage.objects.select_for_update().filter(vessel_id=v.vessel_id, status__in=self.UNDERWAY)
                        .exclude(pk=v.pk).first())
                if busy:
                    raise ValidationError(f'{v.vessel} şu an {busy} seferinde; o sefer bitmeden yenisi başlayamaz.')
            last = v.events.order_by('-on_date', '-pk').first()
            if last and on_date < last.on_date:
                raise ValidationError(f'Tarih, önceki aşamanın tarihinden ({last.on_date:%d.%m.%Y}) önce olamaz.')
            if nxt == self.Status.AT_SEA:
                v.actual_departure = on_date
            if nxt == self.Status.COMPLETED:
                v.actual_arrival = on_date
            v.status = nxt
            v.save()
            VoyageEvent.objects.create(voyage=v, status=nxt, on_date=on_date, user=user)
        self.status, self.actual_departure, self.actual_arrival = v.status, v.actual_departure, v.actual_arrival

    def cancel(self, user, note):
        note = (note or '').strip()
        if not user.has_perm('operations.change_voyage'):
            raise PermissionDenied('Sefer güncelleme yetkiniz yok.')
        if not note:
            raise ValidationError('İptal için bir gerekçe yazın.')
        with transaction.atomic():
            v = Voyage.objects.select_for_update().get(pk=self.pk)
            if v.status not in (self.Status.PLANNED, self.Status.LOADING):
                raise ValidationError('Yalnızca planlanan veya yüklemedeki sefer iptal edilebilir.')
            v.status = self.Status.CANCELLED
            v.save()
            VoyageEvent.objects.create(voyage=v, status=v.status, on_date=timezone.localdate(), user=user, note=note)
        self.status = v.status

    def costs(self):
        """Linked expense invoices (not rejected), totals per currency and status."""
        return (self.invoices.exclude(status=Invoice.Status.REJECTED).values('currency', 'status')
                .annotate(total=Sum('amount')).order_by('currency', 'status'))


class VoyageEvent(models.Model):
    """Audit trail: each phase change with who recorded it and when it happened."""
    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=12, choices=Voyage.Status.choices)
    on_date = models.DateField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    note = models.CharField(max_length=300, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['on_date', 'pk']


class BunkerDelivery(models.Model):
    vessel = models.ForeignKey(Vessel, on_delete=models.PROTECT, related_name='bunkers', verbose_name='gemi')
    voyage = models.ForeignKey(Voyage, on_delete=models.PROTECT, null=True, blank=True, related_name='bunkers',
                               verbose_name='sefer')
    date = models.DateField('teslim tarihi')
    port = models.ForeignKey(Port, on_delete=models.PROTECT, related_name='+', verbose_name='liman')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='+', verbose_name='tedarikçi')
    grade = models.CharField('yakıt cinsi', max_length=5, choices=FuelGrade.choices)
    quantity_mt = models.DecimalField('miktar (MT)', validators=[MinValueValidator(Decimal('0.001'))], **MT)
    price_per_mt = models.DecimalField('MT fiyatı', max_digits=10, decimal_places=2,
                                       validators=[MinValueValidator(Decimal('0'))])
    currency = models.CharField('para birimi', max_length=3, choices=Currency.choices, default=Currency.USD)
    bdn_no = models.CharField('BDN no', max_length=40, help_text='Bunker teslim belgesi numarası')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'bunker ikmali'
        verbose_name_plural = 'bunker ikmalleri'
        ordering = ['-date', '-pk']
        constraints = [models.UniqueConstraint(fields=['supplier', 'bdn_no'], name='uniq_bdn_per_supplier',
                                               violation_error_message='Bu tedarikçi için bu BDN zaten kayıtlı.')]

    def __str__(self):
        return f'{self.vessel} · {self.grade} · {self.date:%d.%m.%Y}'

    def clean(self):
        if self.date and self.date > timezone.localdate():
            raise ValidationError({'date': 'Teslim tarihi bugünden ileri olamaz.'})
        if self.voyage_id and self.vessel_id and self.voyage.vessel_id != self.vessel_id:
            raise ValidationError({'voyage': 'Sefer bu gemiye ait değil.'})

    @property
    def total(self):
        return (self.quantity_mt * self.price_per_mt).quantize(Decimal('0.01'))


class NoonReport(models.Model):
    vessel = models.ForeignKey(Vessel, on_delete=models.PROTECT, related_name='noon_reports', verbose_name='gemi')
    voyage = models.ForeignKey(Voyage, on_delete=models.PROTECT, null=True, blank=True,
                               related_name='noon_reports', verbose_name='sefer')
    date = models.DateField('rapor tarihi')
    remarks = models.CharField('açıklama', max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'günlük (noon) rapor'
        verbose_name_plural = 'günlük (noon) raporlar'
        ordering = ['-date']
        constraints = [models.UniqueConstraint(fields=['vessel', 'date'], name='uniq_noon_per_day',
                                               violation_error_message='Bu gemi için bu tarihte rapor zaten var.')]

    def __str__(self):
        return f'{self.vessel} · {self.date:%d.%m.%Y}'


class NoonFuel(models.Model):
    report = models.ForeignKey(NoonReport, on_delete=models.CASCADE, related_name='fuels')
    grade = models.CharField(max_length=5, choices=FuelGrade.choices)
    consumed_mt = models.DecimalField('tüketim (MT)', validators=[MinValueValidator(Decimal('0'))], **MT)
    rob_mt = models.DecimalField('ROB (MT)', validators=[MinValueValidator(Decimal('0'))], **MT)

    class Meta:
        ordering = ['grade']
        constraints = [models.UniqueConstraint(fields=['report', 'grade'], name='uniq_grade_per_report')]


TOLERANCE_MT = Decimal('0.5')


def fuel_ledger(vessel, limit=None):
    """Noon reports newest first, each fuel row annotated with `bunkered` since the previous report,
    `expected` ROB (previous ROB + bunkered - consumed) and `diff` (reported ROB - expected).
    A diff beyond TOLERANCE_MT means the figures do not add up and someone should check them."""
    reports = list(vessel.noon_reports.prefetch_related('fuels').order_by('date'))
    bunkers = list(vessel.bunkers.order_by('date'))
    prev_rob, prev_date = {}, None
    for r in reports:
        for f in r.fuels.all():
            got = sum((b.quantity_mt for b in bunkers if b.grade == f.grade
                       and (prev_date is None or b.date > prev_date) and b.date <= r.date), Decimal('0'))
            f.bunkered = got
            f.prev_rob = prev_rob.get(f.grade)
            if f.grade in prev_rob:
                f.expected = prev_rob[f.grade] + got - f.consumed_mt
                f.diff = f.rob_mt - f.expected
                f.flag = abs(f.diff) > TOLERANCE_MT
            else:
                f.expected = f.diff = None
                f.flag = False
            prev_rob[f.grade] = f.rob_mt
        r.fuel_list = sorted(r.fuels.all(), key=lambda f: GRADE_ORDER[f.grade])
        r.flagged = any(f.flag for f in r.fuel_list)
        prev_date = r.date
    reports.reverse()
    return reports[:limit] if limit else reports
