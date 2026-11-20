from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import ApprovalLevel, Company, ExchangeRate, Invoice, Supplier, waiting_for
from .templatetags.liman import money


class Base(TestCase):
    def setUp(self):
        self.ops = Group.objects.create(name='Operasyon')
        self.fin = Group.objects.create(name='Finans')
        ApprovalLevel.objects.create(order=1, name='Operasyon', group=self.ops)
        ApprovalLevel.objects.create(order=2, name='Finans', group=self.fin)
        self.clerk = User.objects.create_user('clerk', password='x')
        self.op = User.objects.create_user('op', password='x')
        self.op.groups.add(self.ops)
        self.fi = User.objects.create_user('fi', password='x')
        self.fi.groups.add(self.fin)
        self.co = Company.objects.create(code='DEMO', name='Demo')
        self.sup = Supplier.objects.create(name='Fuel SA')
        self.inv = self.make('INV-1', '187200.00', 'USD')

    def make(self, number, amount, currency):
        return Invoice.objects.create(number=number, supplier=self.sup, company=self.co, amount=Decimal(amount),
                                      currency=currency, invoice_date=date(2026, 9, 23), created_by=self.clerk)


class ApprovalChainTests(Base):
    def test_two_levels_then_approved(self):
        self.inv.decide(self.op, approve=True)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invoice.Status.PENDING)
        self.assertEqual(self.inv.next_level().order, 2)
        self.inv.decide(self.fi, approve=True)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invoice.Status.APPROVED)
        self.assertIsNone(self.inv.next_level())

    def test_wrong_group_denied(self):
        with self.assertRaises(PermissionDenied):
            self.inv.decide(self.fi, approve=True)  # level 1 belongs to Operasyon

    def test_creator_cannot_approve_own_invoice(self):
        self.clerk.groups.add(self.ops)
        with self.assertRaises(PermissionDenied):
            self.inv.decide(self.clerk, approve=True)

    def test_same_user_cannot_pass_two_levels(self):
        self.op.groups.add(self.fin)
        self.inv.decide(self.op, approve=True)
        with self.assertRaises(PermissionDenied):
            self.inv.decide(self.op, approve=True)

    def test_double_decision_on_finished_invoice(self):
        self.inv.decide(self.op, approve=False, note='Yanlış tutar')
        with self.assertRaises(ValidationError):
            self.inv.decide(self.fi, approve=True)

    def test_reject_needs_reason_and_stops_chain(self):
        with self.assertRaises(ValidationError):
            self.inv.decide(self.op, approve=False, note='  ')
        self.inv.decide(self.op, approve=False, note='Yanlış tutar')
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invoice.Status.REJECTED)

    def test_waiting_for(self):
        self.assertEqual(waiting_for(self.op), [self.inv.pk])
        self.assertEqual(waiting_for(self.fi), [])
        self.assertEqual(waiting_for(self.clerk), [])
        self.inv.decide(self.op, approve=True)
        self.assertEqual(waiting_for(self.op), [])
        self.assertEqual(waiting_for(self.fi), [self.inv.pk])

    def test_try_equivalent_uses_rate_on_or_before_invoice_date(self):
        ExchangeRate.objects.create(date=date(2026, 9, 1), currency='USD', rate=Decimal('34.0000'))
        ExchangeRate.objects.create(date=date(2026, 10, 1), currency='USD', rate=Decimal('99.0000'))
        self.assertEqual(self.inv.try_equivalent, Decimal('6364800.00'))
        self.assertIsNone(self.make('INV-2', '10', 'EUR').try_equivalent)


class FormatTests(TestCase):
    def test_money_uses_turkish_grouping(self):
        self.assertEqual(money(Decimal('187200')), '187.200,00')
        self.assertEqual(money(Decimal('0.02')), '0,02')
        self.assertEqual(money(None), '—')


class ViewTests(Base):
    def test_login_required(self):
        r = self.client.get(reverse('invoices:pool'))
        self.assertRedirects(r, reverse('login') + '?next=' + reverse('invoices:pool'))

    def test_pool_and_decide_flow(self):
        self.client.force_login(self.op)
        r = self.client.get(reverse('invoices:pool'))
        self.assertContains(r, 'INV-1')
        self.assertContains(r, '187.200,00')
        url = reverse('invoices:pool_detail', args=[self.inv.pk])
        r = self.client.post(reverse('invoices:decide', args=[self.inv.pk]), {'karar': 'onayla', 'next': url})
        self.assertRedirects(r, url)
        self.assertEqual(self.inv.approvals.count(), 1)
        # A replayed POST (double click that got through) is refused, not recorded twice.
        r = self.client.post(reverse('invoices:decide', args=[self.inv.pk]), {'karar': 'onayla', 'next': url},
                             follow=True)
        self.assertEqual(self.inv.approvals.count(), 1)
        self.assertContains(r, 'yetkiniz yok')

    def test_decide_rejects_offsite_next(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse('invoices:decide', args=[self.inv.pk]),
                             {'karar': 'onayla', 'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('invoices:all_detail', args=[self.inv.pk]), fetch_redirect_response=False)

    def test_decide_requires_post(self):
        self.client.force_login(self.op)
        self.assertEqual(self.client.get(reverse('invoices:decide', args=[self.inv.pk])).status_code, 405)

    def test_totals_are_per_currency(self):
        self.make('INV-2', '1000', 'EUR')
        self.client.force_login(self.clerk)
        r = self.client.get(reverse('invoices:all'))
        self.assertContains(r, '187.200,00</span> USD')
        self.assertContains(r, '1.000,00</span> EUR')

    def test_filters(self):
        self.make('XYZ-9', '5', 'TRY')
        self.client.force_login(self.clerk)
        r = self.client.get(reverse('invoices:all'), {'q': 'xyz'})
        self.assertContains(r, 'XYZ-9')
        self.assertNotContains(r, 'INV-1')

    def test_create_and_duplicate_number(self):
        self.client.force_login(self.clerk)
        data = {'number': 'NEW-1', 'invoice_date': '2026-11-20', 'supplier': self.sup.pk, 'company': self.co.pk,
                'amount': '1250.50', 'currency': 'USD'}
        r = self.client.post(reverse('invoices:create'), data)
        inv = Invoice.objects.get(number='NEW-1')
        self.assertRedirects(r, reverse('invoices:all_detail', args=[inv.pk]))
        self.assertEqual(inv.created_by, self.clerk)
        self.assertEqual(inv.status, Invoice.Status.PENDING)
        r = self.client.post(reverse('invoices:create'), data)
        self.assertContains(r, 'zaten kayıtlı')

    def test_due_before_invoice_date_rejected(self):
        self.client.force_login(self.clerk)
        r = self.client.post(reverse('invoices:create'), {
            'number': 'N-2', 'invoice_date': '2026-11-20', 'due_date': '2026-11-01', 'supplier': self.sup.pk,
            'company': self.co.pk, 'amount': '10', 'currency': 'USD'})
        self.assertContains(r, 'Vade tarihi fatura tarihinden önce olamaz')

    def test_no_levels_means_auto_approved(self):
        ApprovalLevel.objects.all().delete()
        self.client.force_login(self.clerk)
        self.client.post(reverse('invoices:create'), {
            'number': 'N-3', 'invoice_date': '2026-11-20', 'supplier': self.sup.pk, 'company': self.co.pk,
            'amount': '10', 'currency': 'USD'})
        self.assertEqual(Invoice.objects.get(number='N-3').status, Invoice.Status.APPROVED)


SAMPLE = b'''<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="20.11.2026" Date="11/20/2026" Bulten_No="2026/219">
  <Currency Kod="USD" CurrencyCode="USD"><Unit>1</Unit><ForexBuying>50.4028</ForexBuying><ForexSelling>50.4936</ForexSelling></Currency>
  <Currency Kod="JPY" CurrencyCode="JPY"><Unit>100</Unit><ForexSelling>32.5000</ForexSelling></Currency>
  <Currency Kod="EUR" CurrencyCode="EUR"><Unit>1</Unit><ForexSelling>58.1234</ForexSelling></Currency>
  <Currency Kod="XDR" CurrencyCode="XDR"><Unit>1</Unit><ForexSelling></ForexSelling></Currency>
</Tarih_Date>'''


class TcmbTests(Base):
    def test_parse_uses_forex_selling_per_unit(self):
        from . import tcmb
        day, rates = tcmb.parse(SAMPLE, {'USD', 'EUR', 'JPY', 'XDR'})
        self.assertEqual(day, date(2026, 11, 20))
        self.assertEqual(rates, {'USD': Decimal('50.4936'), 'EUR': Decimal('58.1234'), 'JPY': Decimal('0.3250')})

    def test_parse_rejects_other_xml(self):
        from . import tcmb
        with self.assertRaises(ValueError):
            tcmb.parse(b'<html/>', {'USD'})

    def test_command_saves_and_is_idempotent(self):
        from unittest import mock

        from django.core.management import call_command
        with mock.patch('invoices.tcmb.download', return_value=SAMPLE):
            call_command('fetch_tcmb_rates', stdout=__import__('io').StringIO())
            call_command('fetch_tcmb_rates', stdout=__import__('io').StringIO())
        rows = ExchangeRate.objects.filter(date=date(2026, 11, 20))
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.get(currency='EUR').source, ExchangeRate.Source.TCMB)

    def test_command_holiday_and_missing_currency(self):
        from io import StringIO
        from unittest import mock

        from django.core.management import CommandError, call_command
        with mock.patch('invoices.tcmb.download', return_value=None):
            out = StringIO()
            call_command('fetch_tcmb_rates', stdout=out)
            self.assertIn('no TCMB bulletin', out.getvalue())
        no_eur = SAMPLE.replace(b'CurrencyCode="EUR"', b'CurrencyCode="EUX"')
        with mock.patch('invoices.tcmb.download', return_value=no_eur), self.assertRaises(CommandError):
            call_command('fetch_tcmb_rates', stdout=StringIO())

    def test_document_names_tcmb_source(self):
        ExchangeRate.objects.create(date=date(2026, 9, 22), currency='USD', rate=Decimal('34.0000'),
                                    source=ExchangeRate.Source.TCMB)
        self.client.force_login(self.clerk)
        r = self.client.get(reverse('invoices:all_detail', args=[self.inv.pk]))
        self.assertContains(r, 'TCMB döviz satış 34,0000 (22.09.2026)')
