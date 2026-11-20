from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.management.commands.seed_demo import demo_iban
from invoices.models import Company, Invoice, Supplier
from invoices.validators import iban_ok

from .models import BankAccount, OrderInvalid, PaymentOrder, create_order, payable_invoices

S = PaymentOrder.Status


class IbanTests(TestCase):
    def test_checksum_and_length(self):
        self.assertTrue(iban_ok('TR33 0006 1005 1978 6457 8413 26'))
        self.assertTrue(iban_ok('de89370400440532013000'))
        self.assertFalse(iban_ok('TR34 0006 1005 1978 6457 8413 26'))  # wrong check digits
        self.assertFalse(iban_ok('TR3300061005197864578413'))          # too short for TR
        self.assertFalse(iban_ok(''))
        self.assertTrue(iban_ok(demo_iban('0000000000000001')))


class Base(TestCase):
    def setUp(self):
        perms = {p.codename: p for p in Permission.objects.filter(content_type__app_label='payments')}
        fin = Group.objects.create(name='Finans')
        fin.permissions.add(perms['view_paymentorder'], perms['add_paymentorder'], perms['pay_paymentorder'])
        boss = Group.objects.create(name='Ödeme onayı')
        boss.permissions.add(perms['view_paymentorder'], perms['approve_paymentorder'])
        self.fi = User.objects.create_user('fi', password='x')
        self.fi.groups.add(fin)
        self.boss = User.objects.create_user('boss', password='x')
        self.boss.groups.add(boss)
        self.clerk = User.objects.create_user('clerk', password='x')
        self.co = Company.objects.create(code='DEMO', name='Demo')
        self.sup = Supplier.objects.create(name='Fuel SA', iban=demo_iban('0000000000000001'))
        self.other = Supplier.objects.create(name='Other Ltd')
        self.usd = BankAccount.objects.create(company=self.co, bank='B', currency='USD', iban=demo_iban('0000000000000900'))
        self.eur = BankAccount.objects.create(company=self.co, bank='B', currency='EUR', iban=demo_iban('0000000000000901'))
        self.inv = self.invoice('INV-1', '1000.00')
        self.inv2 = self.invoice('INV-2', '500.00')

    def invoice(self, number, amount, status=Invoice.Status.APPROVED, supplier=None, currency='USD'):
        return Invoice.objects.create(number=number, supplier=supplier or self.sup, company=self.co,
                                      amount=Decimal(amount), currency=currency, invoice_date=date(2026, 11, 1),
                                      status=status, created_by=self.clerk)

    def order(self, amounts, user=None, account=None, **kw):
        args = dict(company=self.co, supplier=self.sup, currency='USD', account=account or self.usd,
                    payee_iban=self.sup.iban, pay_date=timezone.localdate(), note='')
        args.update(kw)
        return create_order(user or self.fi, amounts={i.pk: Decimal(a) for i, a in amounts.items()}, **args)


class CreateOrderTests(Base):
    def test_one_order_several_invoices_partial(self):
        o = self.order({self.inv: '400', self.inv2: '500'})
        self.assertEqual(o.status, S.PENDING)
        self.assertTrue(o.number.startswith('OE-'))
        self.assertEqual(o.total, Decimal('900'))
        left = {i.pk: i.amount - i.committed for i in payable_invoices(self.co, self.sup, 'USD')}
        self.assertEqual(left, {self.inv.pk: Decimal('600')})  # INV-2 fully reserved, so no longer payable

    def test_cannot_exceed_open_balance_across_orders(self):
        self.order({self.inv: '700'})
        with self.assertRaises(OrderInvalid) as cm:
            self.order({self.inv: '300.01'})
        self.assertIn(self.inv.pk, cm.exception.lines)
        self.order({self.inv: '300'})  # exactly the rest is fine

    def test_rejected_or_cancelled_order_releases_balance(self):
        o = self.order({self.inv: '1000'})
        o.cancel(self.fi, 'yanlış hesap')
        self.order({self.inv: '1000'})

    def test_rules(self):
        pending = self.invoice('INV-P', '10', status=Invoice.Status.PENDING)
        other = self.invoice('INV-O', '10', supplier=self.other)
        for amounts, kw in [({pending: '10'}, {}), ({other: '10'}, {}), ({self.inv: '0'}, {}),
                            ({self.inv: '10'}, {'account': self.eur}),
                            ({self.inv: '10'}, {'pay_date': timezone.localdate() - timedelta(days=1)}),
                            ({}, {})]:
            with self.subTest(amounts=amounts, kw=kw), self.assertRaises(OrderInvalid):
                self.order(amounts, **kw)
        self.assertFalse(PaymentOrder.objects.exists())

    def test_needs_permission(self):
        with self.assertRaises(PermissionDenied):
            self.order({self.inv: '10'}, user=self.clerk)


class OrderFlowTests(Base):
    def test_approve_then_pay(self):
        o = self.order({self.inv: '1000'})
        with self.assertRaises(PermissionDenied):
            o.decide(self.fi, approve=True)  # creator, and no approve permission
        with self.assertRaises(ValidationError):
            o.mark_paid(self.fi, timezone.localdate(), 'REF')  # not approved yet
        o.decide(self.boss, approve=True)
        self.assertEqual(o.status, S.APPROVED)
        with self.assertRaises(ValidationError):
            o.mark_paid(self.fi, timezone.localdate(), '  ')
        with self.assertRaises(ValidationError):
            o.mark_paid(self.fi, timezone.localdate() + timedelta(days=1), 'REF')
        with self.assertRaises(PermissionDenied):
            o.mark_paid(self.boss, timezone.localdate(), 'REF')  # approver has no pay permission
        o.mark_paid(self.fi, timezone.localdate(), 'DK-1')
        o.refresh_from_db()
        self.assertEqual((o.status, o.bank_ref, o.paid_by), (S.PAID, 'DK-1', self.fi))
        self.assertFalse(o.can_cancel(self.boss))

    def test_creator_with_approve_permission_still_cannot_approve(self):
        self.fi.user_permissions.add(Permission.objects.get(codename='approve_paymentorder'))
        self.fi = User.objects.get(pk=self.fi.pk)  # drop the permission cache
        o = self.order({self.inv: '10'})
        with self.assertRaises(PermissionDenied):
            o.decide(self.fi, approve=True)

    def test_cancel_rules_and_audit_trail(self):
        o = self.order({self.inv: '10'})
        self.assertFalse(o.can_cancel(self.boss))  # an approver rejects a pending order instead
        with self.assertRaises(PermissionDenied):
            o.cancel(self.boss, 'x')
        o.decide(self.boss, approve=True, note='uygun')
        with self.assertRaises(ValidationError):
            o.cancel(self.boss, '  ')
        o.cancel(self.boss, 'yanlış hesap')
        o.refresh_from_db()
        self.assertEqual(o.status, S.CANCELLED)
        # the approval is still on record next to the cancellation
        self.assertEqual((o.decided_by, o.decision_note), (self.boss, 'uygun'))
        self.assertEqual((o.cancelled_by, o.cancel_note), (self.boss, 'yanlış hesap'))

    def test_reject_needs_reason(self):
        o = self.order({self.inv: '10'})
        with self.assertRaises(ValidationError):
            o.decide(self.boss, approve=False, note='')
        o.decide(self.boss, approve=False, note='Tutar hatalı')
        self.assertEqual(o.status, S.REJECTED)


class ViewTests(Base):
    def test_view_permission_required(self):
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(reverse('payments:pending')).status_code, 403)
        self.assertEqual(self.client.get(reverse('payments:create')).status_code, 403)

    def test_create_via_form_then_approve_and_pay(self):
        self.client.force_login(self.fi)
        url = reverse('payments:create') + f'?sirket={self.co.pk}&cari={self.sup.pk}&doviz=USD'
        r = self.client.get(url)
        self.assertContains(r, 'INV-1')
        self.assertContains(r, '1.000,00')
        r = self.client.post(url, {'account': self.usd.pk, 'payee_iban': 'tr' + self.sup.iban[2:],
                                   'pay_date': timezone.localdate().isoformat(), 'note': '',
                                   f'tutar_{self.inv.pk}': '1.000,00', f'tutar_{self.inv2.pk}': '250.5'})
        o = PaymentOrder.objects.get()
        self.assertRedirects(r, reverse('payments:pending_detail', args=[o.pk]))
        self.assertEqual(o.total, Decimal('1250.50'))
        self.assertEqual(o.payee_iban, self.sup.iban)

        self.client.force_login(self.boss)
        detail = reverse('payments:pending_detail', args=[o.pk])
        self.assertContains(self.client.get(detail), 'Ödemeyi onayla')
        self.client.post(reverse('payments:action', args=[o.pk]), {'islem': 'onayla', 'next': detail})
        self.client.force_login(self.fi)
        self.client.post(reverse('payments:action', args=[o.pk]),
                         {'islem': 'ode', 'odeme_tarihi': timezone.localdate().isoformat(), 'dekont': 'DK-9'})
        o.refresh_from_db()
        self.assertEqual(o.status, S.PAID)

        self.client.force_login(self.clerk)
        r = self.client.get(reverse('invoices:all_detail', args=[self.inv2.pk]))
        self.assertContains(r, o.number)
        self.assertContains(r, '249,50 USD')  # open balance after 250,50 of 500
        r = self.client.get(reverse('invoices:all'))
        self.assertContains(r, 'Kısmen ödendi')

    def test_form_shows_line_error_over_balance(self):
        self.client.force_login(self.fi)
        url = reverse('payments:create') + f'?sirket={self.co.pk}&cari={self.sup.pk}&doviz=USD'
        r = self.client.post(url, {'account': self.usd.pk, 'payee_iban': self.sup.iban,
                                   'pay_date': timezone.localdate().isoformat(), f'tutar_{self.inv.pk}': '1000,01'})
        self.assertContains(r, 'Açık bakiye')
        self.assertFalse(PaymentOrder.objects.exists())

    def test_bad_iban_rejected(self):
        self.client.force_login(self.fi)
        url = reverse('payments:create') + f'?sirket={self.co.pk}&cari={self.sup.pk}&doviz=USD'
        r = self.client.post(url, {'account': self.usd.pk, 'payee_iban': 'TR000000',
                                   'pay_date': timezone.localdate().isoformat(), f'tutar_{self.inv.pk}': '10'})
        self.assertContains(r, 'Geçerli bir IBAN')
        self.assertFalse(PaymentOrder.objects.exists())

    def test_action_errors_are_shown_not_raised(self):
        o = self.order({self.inv: '10'})
        self.client.force_login(self.fi)
        r = self.client.post(reverse('payments:action', args=[o.pk]), {'islem': 'onayla'}, follow=True)
        self.assertContains(r, 'onaylama yetkiniz yok')
