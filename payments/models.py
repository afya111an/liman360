from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.template.defaultfilters import floatformat
from django.utils import timezone

from invoices.models import Company, Currency, Invoice, Supplier
from invoices.validators import validate_iban


class OrderInvalid(ValidationError):
    """create_order failed; .fields maps form field -> message, .lines maps invoice pk -> message."""

    def __init__(self, fields, lines):
        super().__init__('Ödeme emri kaydedilemedi.')
        self.fields, self.lines = fields, lines


class BankAccount(models.Model):
    """A bank account of a group company that payments are made from."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, verbose_name='şirket', related_name='bank_accounts')
    bank = models.CharField('banka', max_length=100)
    iban = models.CharField('IBAN', max_length=34, unique=True, validators=[validate_iban])
    currency = models.CharField('para birimi', max_length=3, choices=Currency.choices)
    active = models.BooleanField('kullanımda', default=True)

    class Meta:
        verbose_name = 'banka hesabı'
        verbose_name_plural = 'banka hesapları'
        ordering = ['company__code', 'bank', 'currency']

    def __str__(self):
        return f'{self.bank} · {self.currency} · {self.iban[-4:]}'

    def save(self, *args, **kwargs):
        self.iban = self.iban.replace(' ', '').upper()
        super().save(*args, **kwargs)


class PaymentOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Onay bekliyor'
        APPROVED = 'APPROVED', 'Ödenecek'
        PAID = 'PAID', 'Ödendi'
        REJECTED = 'REJECTED', 'Reddedildi'
        CANCELLED = 'CANCELLED', 'İptal edildi'

    # Orders in these states hold (reserve) the amounts they cover on each invoice.
    LIVE = (Status.PENDING, Status.APPROVED, Status.PAID)

    number = models.CharField('ödeme emri no', max_length=20, unique=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, verbose_name='ödeyen şirket')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name='alıcı')
    currency = models.CharField('para birimi', max_length=3, choices=Currency.choices)
    account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, verbose_name='ödeyen hesap')
    payee_iban = models.CharField('alıcı IBAN', max_length=34, validators=[validate_iban])
    pay_date = models.DateField('planlanan ödeme tarihi')
    note = models.CharField('açıklama', max_length=200, blank=True)
    status = models.CharField('durum', max_length=10, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                related_name='+')
    paid_on = models.DateField('ödeme tarihi', null=True, blank=True)
    paid_recorded_at = models.DateTimeField(null=True, blank=True)
    bank_ref = models.CharField('banka dekont / referans no', max_length=60, blank=True)
    # Cancellation has its own fields so it never overwrites an earlier approval (audit trail).
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='+')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_note = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = 'ödeme emri'
        verbose_name_plural = 'ödeme emirleri'
        ordering = ['pay_date', 'pk']
        permissions = [
            ('approve_paymentorder', 'Ödeme emri onaylayabilir'),
            ('pay_paymentorder', 'Ödeme emrini ödendi olarak işaretleyebilir'),
        ]

    def __str__(self):
        return self.number

    @property
    def total(self):
        return self.lines.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # ---- state changes. Each locks the row so two people cannot act on one order at once. ----

    def _locked(self):
        return PaymentOrder.objects.select_for_update().get(pk=self.pk)

    def _sync(self, o):
        for f in ('status', 'decided_by_id', 'decided_at', 'decision_note', 'paid_by_id', 'paid_on',
                  'paid_recorded_at', 'bank_ref', 'cancelled_by_id', 'cancelled_at', 'cancel_note'):
            setattr(self, f, getattr(o, f))

    def can_decide(self, user):
        return (self.status == self.Status.PENDING and user.pk != self.created_by_id
                and user.has_perm('payments.approve_paymentorder'))

    def can_pay(self, user):
        return self.status == self.Status.APPROVED and user.has_perm('payments.pay_paymentorder')

    def can_cancel(self, user):
        """The creator can withdraw a pending order; once approved, the creator or an approver can cancel it.
        (An approver facing a pending order rejects it instead.)"""
        if self.status == self.Status.PENDING:
            return user.pk == self.created_by_id
        return self.status == self.Status.APPROVED and (
            user.pk == self.created_by_id or user.has_perm('payments.approve_paymentorder'))

    def decide(self, user, approve, note=''):
        note = note.strip()
        if not approve and not note:
            raise ValidationError('Reddetmek için bir gerekçe yazın.')
        with transaction.atomic():
            o = self._locked()
            if o.status != self.Status.PENDING:
                raise ValidationError('Bu ödeme emri onay beklemiyor.')
            if not o.can_decide(user):
                raise PermissionDenied('Bu ödeme emrini onaylama yetkiniz yok.')
            o.status = self.Status.APPROVED if approve else self.Status.REJECTED
            o.decided_by, o.decided_at, o.decision_note = user, timezone.now(), note
            o.save()
        self._sync(o)

    def mark_paid(self, user, paid_on, bank_ref):
        bank_ref = (bank_ref or '').strip()
        if not bank_ref:
            raise ValidationError('Bankanın verdiği dekont / referans numarasını yazın.')
        if paid_on is None or paid_on > timezone.localdate():
            raise ValidationError('Ödeme tarihi bugünden ileri olamaz.')
        with transaction.atomic():
            o = self._locked()
            if o.status != self.Status.APPROVED:
                raise ValidationError('Yalnızca onaylanmış ödeme emri ödendi olarak işaretlenir.')
            if not o.can_pay(user):
                raise PermissionDenied('Ödeme kaydetme yetkiniz yok.')
            o.status, o.paid_by, o.paid_on, o.bank_ref = self.Status.PAID, user, paid_on, bank_ref
            o.paid_recorded_at = timezone.now()
            o.save()
        self._sync(o)

    def cancel(self, user, note=''):
        note = note.strip()
        if not note:
            raise ValidationError('İptal için bir gerekçe yazın.')
        with transaction.atomic():
            o = self._locked()
            if not o.can_cancel(user):
                raise PermissionDenied('Bu ödeme emri iptal edilemez.')
            o.status = self.Status.CANCELLED
            o.cancelled_by, o.cancelled_at, o.cancel_note = user, timezone.now(), note
            o.save()
        self._sync(o)


class PaymentLine(models.Model):
    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name='lines')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payment_lines')
    amount = models.DecimalField('ödenecek tutar', max_digits=14, decimal_places=2,
                                 validators=[MinValueValidator(Decimal('0.01'))])

    class Meta:
        ordering = ['invoice__due_date', 'pk']
        constraints = [models.UniqueConstraint(fields=['order', 'invoice'], name='uniq_invoice_per_order')]


# ---- invoice balances ----

def with_balances(invoices):
    """Annotate invoices with `committed` (in live orders) and `paid` (in paid orders)."""
    live = Q(payment_lines__order__status__in=PaymentOrder.LIVE)
    paid = Q(payment_lines__order__status=PaymentOrder.Status.PAID)
    return invoices.annotate(
        committed=Sum('payment_lines__amount', filter=live, default=Decimal('0')),
        paid=Sum('payment_lines__amount', filter=paid, default=Decimal('0')),
    )


def payable_invoices(company, supplier, currency):
    """Approved invoices of one company/supplier/currency that still have an open balance."""
    qs = with_balances(Invoice.objects.filter(
        status=Invoice.Status.APPROVED, company=company, supplier=supplier, currency=currency))
    return [i for i in qs.order_by('due_date', 'pk') if i.amount - i.committed > 0]


def create_order(user, *, company, supplier, currency, account, payee_iban, pay_date, note, amounts):
    """amounts: {invoice_pk: Decimal}. Validates every rule, then saves the order and its lines atomically."""
    if not user.has_perm('payments.add_paymentorder'):
        raise PermissionDenied('Ödeme emri oluşturma yetkiniz yok.')
    errors = {}
    if account.company_id != company.pk or account.currency != currency or not account.active:
        errors['account'] = 'Hesap, ödeyen şirketin bu para birimindeki kullanımda bir hesabı olmalı.'
    if pay_date < timezone.localdate():
        errors['pay_date'] = 'Planlanan ödeme tarihi geçmişte olamaz.'
    amounts = {pk: a for pk, a in amounts.items() if a}
    if not amounts:
        errors['lines'] = 'En az bir fatura için ödenecek tutar girin.'
    with transaction.atomic():
        # Lock the invoices so two orders cannot both reserve the same open balance.
        invs = {i.pk: i for i in Invoice.objects.select_for_update().filter(pk__in=amounts)}
        balances = {i.pk: i for i in with_balances(Invoice.objects.filter(pk__in=amounts))}
        line_errors = {}
        for pk, amount in amounts.items():
            inv = invs.get(pk)
            if (inv is None or inv.status != Invoice.Status.APPROVED or inv.company_id != company.pk
                    or inv.supplier_id != supplier.pk or inv.currency != currency):
                line_errors[pk] = 'Bu fatura bu ödeme emrine eklenemez.'
                continue
            open_ = inv.amount - balances[pk].committed
            if amount <= 0:
                line_errors[pk] = 'Tutar sıfırdan büyük olmalı.'
            elif amount > open_:
                line_errors[pk] = f'Açık bakiye {floatformat(open_, "2g")} {currency}; daha fazlası ödenemez.'
        if errors or line_errors:
            raise OrderInvalid(errors, line_errors)
        order = PaymentOrder.objects.create(
            company=company, supplier=supplier, currency=currency, account=account,
            payee_iban=payee_iban.replace(' ', '').upper(), pay_date=pay_date, note=note.strip(),
            created_by=user)
        order.number = f'OE-{order.created_at:%Y}-{order.pk:04d}'
        order.save(update_fields=['number'])
        PaymentLine.objects.bulk_create(
            [PaymentLine(order=order, invoice_id=pk, amount=a) for pk, a in amounts.items()])
    return order
