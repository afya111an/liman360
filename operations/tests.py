from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.models import Company, Invoice, Supplier, Vessel
from invoices.validators import imo_ok

from .models import BunkerDelivery, NoonFuel, NoonReport, Port, Voyage, fuel_ledger

V = Voyage.Status
TODAY = timezone.localdate()


def day(n):
    return TODAY + timedelta(days=n)


class Base(TestCase):
    def setUp(self):
        self.op = User.objects.create_user('op', password='x')
        self.op.user_permissions.add(*Permission.objects.filter(codename__in=[
            'add_voyage', 'change_voyage', 'add_bunkerdelivery', 'change_bunkerdelivery', 'add_noonreport',
            'change_noonreport', 'add_vessel', 'change_vessel']))
        self.viewer = User.objects.create_user('viewer', password='x')
        self.ship = Vessel.objects.create(name='M/V A', imo='9074729')
        self.ship2 = Vessel.objects.create(name='M/V B')
        self.a = Port.objects.create(name='Mersin', country='TR')
        self.b = Port.objects.create(name='Pire', country='GR')
        self.sup = Supplier.objects.create(name='Fuel SA')
        self.v = self.voyage('V-1')

    def voyage(self, number, ship=None, **kw):
        args = dict(number=number, vessel=ship or self.ship, load_port=self.a, discharge_port=self.b,
                    planned_departure=day(-10), planned_arrival=day(-2), cargo_mt=Decimal('1000'),
                    freight_rate=Decimal('20'), created_by=self.op)
        args.update(kw)
        return Voyage.objects.create(**args)


class ImoTests(TestCase):
    def test_checksum(self):
        self.assertTrue(imo_ok('9074729'))
        self.assertTrue(imo_ok('IMO 9074729'))
        self.assertFalse(imo_ok('9074728'))
        self.assertFalse(imo_ok('907472'))


class VoyageFlowTests(Base):
    def test_full_flow_sets_actual_dates_and_events(self):
        for d in (-9, -8, -3, -1):
            self.v.advance(self.op, day(d))
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, V.COMPLETED)
        self.assertEqual((self.v.actual_departure, self.v.actual_arrival), (day(-8), day(-1)))
        self.assertEqual(list(self.v.events.values_list('status', flat=True)),
                         [V.LOADING, V.AT_SEA, V.DISCHARGING, V.COMPLETED])
        with self.assertRaises(ValidationError):
            self.v.advance(self.op, day(0))  # nothing after completed
        self.assertFalse(self.v.editable)

    def test_dates_must_not_go_backwards_or_into_future(self):
        with self.assertRaises(ValidationError):
            self.v.advance(self.op, day(1))
        self.v.advance(self.op, day(-5))
        with self.assertRaises(ValidationError):
            self.v.advance(self.op, day(-6))

    def test_permission(self):
        with self.assertRaises(PermissionDenied):
            self.v.advance(self.viewer, day(0))

    def test_one_running_voyage_per_ship(self):
        self.v.advance(self.op, day(-9))
        other = self.voyage('V-2')
        with self.assertRaises(ValidationError):
            other.advance(self.op, day(0))
        self.voyage('V-3', ship=self.ship2).advance(self.op, day(0))  # another ship is fine

    def test_cancel(self):
        with self.assertRaises(ValidationError):
            self.v.cancel(self.op, ' ')
        self.v.cancel(self.op, 'charter iptal')
        self.assertEqual(self.v.status, V.CANCELLED)
        v2 = self.voyage('V-2')
        v2.advance(self.op, day(-9))
        v2.advance(self.op, day(-8))
        with self.assertRaises(ValidationError):
            v2.cancel(self.op, 'geç')  # at sea cannot be cancelled

    def test_clean_dates(self):
        bad = Voyage(number='X', vessel=self.ship, load_port=self.a, discharge_port=self.b,
                     planned_departure=day(5), planned_arrival=day(1))
        with self.assertRaises(ValidationError):
            bad.clean()


class InvoiceLinkTests(Base):
    def test_voyage_sets_and_checks_vessel(self):
        co = Company.objects.create(code='C', name='C')
        inv = Invoice(number='I-1', supplier=self.sup, company=co, amount=Decimal('10'), currency='USD',
                      invoice_date=day(0), created_by=self.op, voyage=self.v)
        inv.clean()
        self.assertEqual(inv.vessel, self.ship)
        inv.vessel = self.ship2
        with self.assertRaises(ValidationError):
            inv.clean()


class FuelLedgerTests(Base):
    def report(self, d, cons, rob, grade='VLSFO'):
        r = NoonReport.objects.create(vessel=self.ship, date=day(d), created_by=self.op)
        NoonFuel.objects.create(report=r, grade=grade, consumed_mt=Decimal(cons), rob_mt=Decimal(rob))
        return r

    def test_expected_rob_includes_bunkers_and_flags_mismatch(self):
        self.report(-4, '0', '100')
        BunkerDelivery.objects.create(vessel=self.ship, date=day(-3), port=self.a, supplier=self.sup, grade='VLSFO',
                                      quantity_mt=Decimal('50'), price_per_mt=Decimal('600'), bdn_no='B1',
                                      created_by=self.op)
        self.report(-3, '20', '130')       # 100 + 50 - 20 = 130: fine
        self.report(-2, '20', '105')       # expected 110: off by 5
        self.report(-1, '20', '85.3')      # expected 85 from the reported 105: within 0.5
        rows = {r.date: r for r in fuel_ledger(self.ship)}
        self.assertFalse(rows[day(-3)].flagged)
        self.assertEqual(rows[day(-3)].fuels.all()[0].bunkered, Decimal('50'))
        self.assertTrue(rows[day(-2)].flagged)
        self.assertEqual(rows[day(-2)].fuels.all()[0].diff, Decimal('-5'))
        self.assertFalse(rows[day(-1)].flagged)


class ViewTests(Base):
    def test_viewer_can_read_but_not_change(self):
        self.client.force_login(self.viewer)
        r = self.client.get(reverse('operations:voyage_detail', args=[self.v.pk]))
        self.assertContains(r, 'V-1')
        self.assertNotContains(r, 'Yüklemeye başla')
        self.assertEqual(self.client.get(reverse('operations:voyage_create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('operations:noon_create')).status_code, 403)
        self.client.post(reverse('operations:voyage_action', args=[self.v.pk]),
                         {'islem': 'ilerle', 'tarih': TODAY.isoformat()})
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, V.PLANNED)

    def test_advance_via_post_and_costs(self):
        co = Company.objects.create(code='C', name='C')
        for n, (amt, cur) in enumerate([('100', 'USD'), ('50.5', 'USD'), ('20', 'EUR')]):
            Invoice.objects.create(number=f'I-{n}', supplier=self.sup, company=co, amount=Decimal(amt), currency=cur,
                                   invoice_date=day(-5), created_by=self.op, voyage=self.v, vessel=self.ship)
        self.client.force_login(self.op)
        url = reverse('operations:voyage_detail', args=[self.v.pk])
        r = self.client.get(url)
        self.assertContains(r, 'Yüklemeye başla')
        self.assertContains(r, '150,50 USD')     # USD costs, EUR listed separately
        self.assertContains(r, '20,00 EUR')
        self.assertContains(r, '19.849,50 USD')  # freight 20.000 - USD costs 150,50
        self.client.post(reverse('operations:voyage_action', args=[self.v.pk]),
                         {'islem': 'ilerle', 'tarih': day(-1).isoformat(), 'next': url})
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, V.LOADING)

    def test_create_voyage_and_bunker(self):
        self.client.force_login(self.op)
        r = self.client.post(reverse('operations:voyage_create'), {
            'number': 'V-9', 'vessel': self.ship.pk, 'planned_departure': day(3).isoformat(),
            'planned_arrival': day(9).isoformat(), 'load_port': self.a.pk, 'discharge_port': self.b.pk,
            'freight_currency': 'USD'})
        v = Voyage.objects.get(number='V-9')
        self.assertRedirects(r, reverse('operations:voyage_detail', args=[v.pk]))
        r = self.client.post(reverse('operations:bunker_create'), {
            'vessel': self.ship2.pk, 'voyage': v.pk, 'date': TODAY.isoformat(), 'port': self.a.pk,
            'supplier': self.sup.pk, 'grade': 'MGO', 'quantity_mt': '10', 'price_per_mt': '800', 'currency': 'USD',
            'bdn_no': 'B-7'})
        self.assertContains(r, 'Sefer bu gemiye ait değil')

    def test_noon_form_rules_and_voyage_link(self):
        self.v.advance(self.op, day(-9))
        self.v.advance(self.op, day(-8))
        self.client.force_login(self.op)
        url = reverse('operations:noon_create')
        base = {'vessel': self.ship.pk, 'date': day(-1).isoformat()}
        self.assertContains(self.client.post(url, base), 'En az bir yakıt')
        self.assertContains(self.client.post(url, {**base, 'cons_VLSFO': '25'}), 'birlikte girilmeli')
        self.client.post(url, {**base, 'cons_VLSFO': '25', 'rob_VLSFO': '500'})
        r = NoonReport.objects.get()
        self.assertEqual(r.voyage, self.v)
        self.assertContains(self.client.post(url, {**base, 'cons_VLSFO': '25', 'rob_VLSFO': '475'}), 'zaten var')

    def test_edit_noon_report_replaces_fuel_rows(self):
        self.client.force_login(self.op)
        self.client.post(reverse('operations:noon_create'), {'vessel': self.ship.pk, 'date': day(-2).isoformat(),
                                                              'cons_VLSFO': '25', 'rob_VLSFO': '500'})
        r = NoonReport.objects.get()
        url = reverse('operations:noon_edit', args=[r.pk])
        self.assertContains(self.client.get(url), 'value="500')        # current values prefilled
        self.client.post(url, {'vessel': self.ship.pk, 'date': day(-2).isoformat(),
                               'cons_VLSFO': '24', 'rob_VLSFO': '501', 'cons_MGO': '2', 'rob_MGO': '80'})
        r.refresh_from_db()
        self.assertEqual(sorted((f.grade, f.rob_mt) for f in r.fuels.all()),
                         [('MGO', Decimal('80')), ('VLSFO', Decimal('501'))])
        self.assertEqual(NoonReport.objects.count(), 1)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_turkish_decimal_input_and_tonnage_format(self):
        from invoices.templatetags.liman import mt
        self.assertEqual([mt(Decimal(x)) for x in ('28500.000', '650.500', '747.7', '0')], ['28.500', '650,5', '747,7', '0'])
        self.client.force_login(self.op)
        self.client.post(reverse('operations:noon_create'), {'vessel': self.ship.pk, 'date': day(-1).isoformat(),
                                                              'cons_VLSFO': '28,1', 'rob_VLSFO': '1.250,5'})
        f = NoonReport.objects.get().fuels.get()
        self.assertEqual((f.consumed_mt, f.rob_mt), (Decimal('28.1'), Decimal('1250.5')))
        r = self.client.get(reverse('operations:noon_edit', args=[f.report_id]))
        self.assertContains(r, 'value="1.250,5"')

    def test_bunker_edit_permission(self):
        b = BunkerDelivery.objects.create(vessel=self.ship, date=day(-1), port=self.a, supplier=self.sup,
                                          grade='MGO', quantity_mt=Decimal('10'), price_per_mt=Decimal('800'),
                                          bdn_no='B1', created_by=self.op)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('operations:bunker_edit', args=[b.pk])).status_code, 403)
        self.client.force_login(self.op)
        self.assertEqual(self.client.get(reverse('operations:bunker_edit', args=[b.pk])).status_code, 200)
