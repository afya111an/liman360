from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils.functional import cached_property


class Currency(models.TextChoices):
    USD = 'USD', 'USD - Amerikan Doları'
    EUR = 'EUR', 'EUR - Euro'
    TRY = 'TRY', 'TRY - Türk Lirası'


class Company(models.Model):
    code = models.CharField('kod', max_length=12, unique=True)
    name = models.CharField('ünvan', max_length=200)

    class Meta:
        verbose_name = 'grup şirketi'
        verbose_name_plural = 'grup şirketleri'
        ordering = ['code']

    def __str__(self):
        return self.code


class Supplier(models.Model):
    name = models.CharField('ünvan', max_length=200, unique=True)
    tax_no = models.CharField('vergi no', max_length=20, blank=True)

    class Meta:
        verbose_name = 'cari'
        verbose_name_plural = 'cariler'
        ordering = ['name']

    def __str__(self):
        return self.name


class Vessel(models.Model):
    name = models.CharField('gemi adı', max_length=100, unique=True)

    class Meta:
        verbose_name = 'gemi'
        verbose_name_plural = 'gemiler'
        ordering = ['name']

    def __str__(self):
        return self.name


class ExpenseCategory(models.Model):
    name = models.CharField('kategori', max_length=100, unique=True)

    class Meta:
        verbose_name = 'gider kategorisi'
        verbose_name_plural = 'gider kategorileri'
        ordering = ['name']

    def __str__(self):
        return self.name


class ApprovalLevel(models.Model):
    """One step of the approval chain; every expense invoice passes the levels in order."""

    order = models.PositiveSmallIntegerField('sıra', unique=True)
    name = models.CharField('onay adımı', max_length=100)
    group = models.ForeignKey(Group, on_delete=models.PROTECT, verbose_name='onaylayan grup')

    class Meta:
        verbose_name = 'onay adımı'
        verbose_name_plural = 'onay adımları'
        ordering = ['order']

    def __str__(self):
        return f'{self.order}. {self.name}'


class ExchangeRate(models.Model):
    class Source(models.TextChoices):
        TCMB = 'TCMB', 'TCMB'
        MANUAL = 'MANUAL', 'Elle girildi'

    date = models.DateField('tarih')
    currency = models.CharField('döviz', max_length=3, choices=Currency.choices)
    rate = models.DecimalField('döviz satış kuru (TRY)', max_digits=12, decimal_places=4)
    source = models.CharField('kaynak', max_length=6, choices=Source.choices, default=Source.MANUAL)

    class Meta:
        verbose_name = 'döviz kuru'
        verbose_name_plural = 'döviz kurları'
        ordering = ['-date']
        constraints = [models.UniqueConstraint(fields=['date', 'currency'], name='uniq_rate_per_day')]

    @classmethod
    def on(cls, currency, date):
        """Latest rate record on or before date, or None (TRY needs no rate)."""
        return cls.objects.filter(currency=currency, date__lte=date).first()


class Invoice(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Onay bekliyor'
        APPROVED = 'APPROVED', 'Onaylandı'
        REJECTED = 'REJECTED', 'Reddedildi'

    number = models.CharField('fatura / belge no', max_length=40)
    ref_no = models.CharField('evrak / ref no', max_length=40, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='cari / tedarikçi')
    company = models.ForeignKey(Company, on_delete=models.PROTECT, verbose_name='borçlu şirket')
    vessel = models.ForeignKey(Vessel, on_delete=models.PROTECT, null=True, blank=True, verbose_name='gemi')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, null=True, blank=True,
                                 verbose_name='gider kategorisi')
    invoice_date = models.DateField('fatura tarihi')
    due_date = models.DateField('vade tarihi', null=True, blank=True)
    amount = models.DecimalField('tutar', max_digits=14, decimal_places=2,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField('para birimi', max_length=3, choices=Currency.choices, default=Currency.USD)
    description = models.CharField('gider kalemi açıklaması', max_length=200, blank=True)
    notes = models.TextField('notlar', blank=True)
    status = models.CharField('durum', max_length=10, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'gider faturası'
        verbose_name_plural = 'gider faturaları'
        ordering = ['due_date', 'invoice_date', 'pk']
        constraints = [models.UniqueConstraint(
            fields=['supplier', 'number'], name='uniq_invoice_per_supplier',
            violation_error_message='Bu cari için bu fatura numarası zaten kayıtlı.')]

    def __str__(self):
        return self.number

    def clean(self):
        if self.due_date and self.invoice_date and self.due_date < self.invoice_date:
            raise ValidationError({'due_date': 'Vade tarihi fatura tarihinden önce olamaz.'})

    @cached_property
    def rate(self):
        """ExchangeRate used for the TRY equivalent: latest on or before the invoice date."""
        return None if self.currency == Currency.TRY else ExchangeRate.on(self.currency, self.invoice_date)

    @property
    def try_equivalent(self):
        return (self.amount * self.rate.rate).quantize(Decimal('0.01')) if self.rate else None

    def next_level(self):
        """The approval level this invoice is waiting on, or None."""
        if self.status != self.Status.PENDING:
            return None
        done = self.approvals.values_list('level_id', flat=True)
        return ApprovalLevel.objects.exclude(pk__in=done).first()

    def can_decide(self, user):
        level = self.next_level()
        if level is None or user.pk == self.created_by_id:
            return False
        if self.approvals.filter(user=user).exists():
            return False
        return user.groups.filter(pk=level.group_id).exists()

    def decide(self, user, approve, note=''):
        """Record user's decision on the current level. Raises PermissionDenied / ValidationError."""
        note = note.strip()
        if not approve and not note:
            raise ValidationError('Reddetmek için bir gerekçe yazın.')
        with transaction.atomic():
            # Lock the row so two approvers (or a double click) cannot decide the same level twice.
            inv = Invoice.objects.select_for_update().get(pk=self.pk)
            level = inv.next_level()
            if level is None:
                raise ValidationError('Bu fatura için bekleyen bir onay yok.')
            if not inv.can_decide(user):
                raise PermissionDenied('Bu onay adımı için yetkiniz yok.')
            Approval.objects.create(invoice=inv, level=level, user=user, approved=approve, note=note)
            if not approve:
                inv.status = self.Status.REJECTED
            elif inv.next_level() is None:
                inv.status = self.Status.APPROVED
            inv.save(update_fields=['status'])
        self.status = inv.status
        return inv


def waiting_for(user, qs=None):
    """Pending invoices whose current approval level this user may decide (constant query count)."""
    levels = list(ApprovalLevel.objects.all())
    my_groups = set(user.groups.values_list('pk', flat=True))
    qs = (qs if qs is not None else Invoice.objects.all()).filter(status=Invoice.Status.PENDING)
    out = []
    for inv in qs.prefetch_related('approvals'):
        decided = {a.level_id for a in inv.approvals.all()}
        level = next((lv for lv in levels if lv.pk not in decided), None)
        if (level and level.group_id in my_groups and inv.created_by_id != user.pk
                and all(a.user_id != user.pk for a in inv.approvals.all())):
            out.append(inv.pk)
    return out


class Approval(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='approvals')
    level = models.ForeignKey(ApprovalLevel, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    approved = models.BooleanField()
    note = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['level__order']
        constraints = [models.UniqueConstraint(fields=['invoice', 'level'], name='uniq_decision_per_level')]
