"""Synthetic demo data for local development. Never run against a customer database."""
import os
import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError

from invoices.models import (ApprovalLevel, Company, ExchangeRate, ExpenseCategory, Invoice, Supplier,
                             Vessel)
from operations.models import BunkerDelivery, NoonFuel, NoonReport, Port, Voyage
from payments.models import BankAccount, create_order


def demo_iban(account16, bank='00099'):
    """A checksum-valid but fictional Turkish IBAN (bank code 00099 is not a real bank)."""
    bban = f'{bank}0{account16}'
    check = 98 - int(''.join(str(int(c, 36)) for c in bban + 'TR00')) % 97
    return f'TR{check:02d}{bban}'


class Command(BaseCommand):
    help = 'Fill an empty database with synthetic demo data (users: muhasebe, operasyon, finans, yonetici).'

    def handle(self, *args, **opts):
        if Invoice.objects.exists():
            raise CommandError('Database already has invoices; seed_demo only runs on an empty database.')
        password = os.environ.get('LIMAN_DEMO_PASSWORD') or secrets.token_urlsafe(9)
        ops, fin = Group.objects.get_or_create(name='Operasyon')[0], Group.objects.get_or_create(name='Finans')[0]
        ApprovalLevel.objects.create(order=1, name='Operasyon', group=ops)
        ApprovalLevel.objects.create(order=2, name='Finans müdürü', group=fin)

        def user(name, first, last, group=None, **kw):
            u = User.objects.create_user(name, password=password, first_name=first, last_name=last, **kw)
            if group:
                u.groups.add(group)
            return u
        clerk = user('muhasebe', 'Ayşe', 'Yılmaz')
        op = user('operasyon', 'Mert', 'Kaya', ops)
        fi = user('finans', 'Selin', 'Demir', fin)
        pay_ok = Group.objects.get_or_create(name='Ödeme onayı')[0]
        mudur = user('mudur', 'Kemal', 'Aydın', pay_ok)
        perms = {p.codename: p for p in Permission.objects.filter(content_type__app_label='payments')}
        fin.permissions.add(perms['view_paymentorder'], perms['add_paymentorder'], perms['pay_paymentorder'])
        pay_ok.permissions.add(perms['view_paymentorder'], perms['approve_paymentorder'])
        user('yonetici', 'Demo', 'Yönetici', is_staff=True, is_superuser=True)

        today = date.today()
        ExchangeRate.objects.bulk_create([
            ExchangeRate(date=today - timedelta(days=90), currency='USD', rate=Decimal('33.9000')),
            ExchangeRate(date=today - timedelta(days=90), currency='EUR', rate=Decimal('36.8000')),
            ExchangeRate(date=today, currency='USD', rate=Decimal('34.2500')),
            ExchangeRate(date=today, currency='EUR', rate=Decimal('37.1500')),
        ])
        co = Company.objects.create(code='DEMO', name='Demo Denizcilik A.Ş. (örnek veri)')
        Company.objects.create(code='DEMOLOJ', name='Demo Lojistik Ltd. (örnek veri)')
        v1 = Vessel.objects.create(name='M/V DEMO STAR', imo='9074729', flag='Malta', dwt=37500)
        v2 = Vessel.objects.create(name='M/V DEMO WAVE', imo='9123453', flag='Türkiye', dwt=28200,
                                   vessel_type=Vessel.Type.GENERAL)
        ops.permissions.add(*Permission.objects.filter(codename__in=[
            'add_voyage', 'change_voyage', 'add_bunkerdelivery', 'change_bunkerdelivery', 'add_noonreport',
            'change_noonreport', 'add_vessel', 'change_vessel']))
        fuel = ExpenseCategory.objects.create(name='Yakıt ve madeni yağ')
        port = ExpenseCategory.objects.create(name='Liman masrafları / D/A')
        ExpenseCategory.objects.create(name='Genel masraf')
        s = {n: Supplier.objects.create(name=n, iban=demo_iban(f'{i + 1:016d}')) for i, n in enumerate([
            'Örnek Marine Fuels SA', 'Örnek Port Agency Services', 'Örnek Liman Hizmetleri Ltd.',
            'Örnek Tersane A.Ş.', 'Örnek Kumanya Tedarik'])}
        accounts = {cur: BankAccount.objects.create(company=co, bank='Örnek Bankası', currency=cur,
                                                    iban=demo_iban(f'{900 + n:016d}'))
                    for n, cur in enumerate(['USD', 'EUR', 'TRY'])}

        p = {n: Port.objects.create(name=n, country=c, unlocode=u) for n, c, u in [
            ('Novorossiysk', 'Rusya', 'RUNVS'), ('Alexandria', 'Mısır', 'EGALY'), ('Mersin', 'Türkiye', 'TRMER'),
            ('Constanța', 'Romanya', 'ROCND'), ('Ambarlı', 'Türkiye', 'TRAMB'), ('Pire', 'Yunanistan', 'GRPIR')]}
        grain = Supplier.objects.create(name='Örnek Grain Trading SA')

        def voyage(no, vessel, a, b, dep, arr, cargo, mt, rate, phases):
            v = Voyage.objects.create(number=no, vessel=vessel, load_port=p[a], discharge_port=p[b],
                                      planned_departure=today + timedelta(days=dep),
                                      planned_arrival=today + timedelta(days=arr), cargo=cargo,
                                      cargo_mt=Decimal(mt), charterer=grain, freight_rate=Decimal(rate),
                                      created_by=op)
            for days in phases:
                v.advance(op, today + timedelta(days=days))
            return v
        # synthetic voyages: one finished, one at sea, one planned
        wave = voyage('DW-26/05', v2, 'Mersin', 'Constanța', -40, -24, 'Demir çelik (rulo)', '24800', '18.75',
                      [-40, -37, -25, -22])
        star = voyage('DS-26/08', v1, 'Novorossiysk', 'Alexandria', -14, 2, 'Dökme buğday', '28500', '24.50',
                      [-14, -11])
        voyage('DS-26/09', v1, 'Alexandria', 'Pire', 12, 15, 'Dökme mısır', '27000', '19.00', [])

        rows = [
            ('INV-2026-0891', 'Örnek Marine Fuels SA', v1, fuel, '187200.00', 'USD', 20, 'VLSFO ikmali'),
            ('DA-26-044', 'Örnek Port Agency Services', v1, port, '42850.00', 'USD', 5, 'Liman masrafları, final D/A'),
            ('LH-2026-117', 'Örnek Liman Hizmetleri Ltd.', v2, port, '18400.00', 'EUR', 12, 'Römorkör ve pilotaj'),
            ('TRS-2026-090', 'Örnek Tersane A.Ş.', v2, None, '640000.00', 'TRY', 30, 'Ara bakım işçiliği'),
            ('KMN-2026-031', 'Örnek Kumanya Tedarik', v1, None, '3125.50', 'USD', 9, 'Kumanya'),
            ('LH-2026-104', 'Örnek Liman Hizmetleri Ltd.', v1, port, '9760.00', 'EUR', 3, 'Rıhtım ve barınma ücreti'),
        ]
        invs = []
        for no, sup, vessel, cat, amt, cur, due, desc in rows:
            invs.append(Invoice.objects.create(
                number=no, supplier=s[sup], company=co, vessel=vessel, category=cat, amount=Decimal(amt),
                currency=cur, invoice_date=today - timedelta(days=10), due_date=today + timedelta(days=due),
                description=desc, created_by=clerk,
                voyage={'INV-2026-0891': star, 'DA-26-044': star, 'KMN-2026-031': star, 'LH-2026-104': star,
                        'LH-2026-117': wave}.get(no)))

        # bunker at Novorossiysk before sailing, then daily noon reports at sea (one day does not add up)
        for grade, qty, price, bdn in [('VLSFO', '650', '590.00', 'NV-26-3310'), ('MGO', '80', '815.00', 'NV-26-3311')]:
            BunkerDelivery.objects.create(vessel=v1, voyage=star, date=today - timedelta(days=13), port=p['Novorossiysk'],
                                          supplier=s['Örnek Marine Fuels SA'], grade=grade, quantity_mt=Decimal(qty),
                                          price_per_mt=Decimal(price), bdn_no=bdn, created_by=op)
        rob = {'VLSFO': Decimal('980.0'), 'MGO': Decimal('120.0')}
        for n, days in enumerate(range(-12, 0)):
            burn = {'VLSFO': Decimal('27.5') + Decimal(n % 3) * Decimal('0.7'), 'MGO': Decimal('2.4')}
            r = NoonReport.objects.create(vessel=v1, voyage=star, date=today + timedelta(days=days), created_by=op,
                                          remarks='Ege Denizi, hava iyi' if days == -3 else '')
            for g in ('VLSFO', 'MGO'):
                if n:
                    rob[g] -= burn[g]
                shown = rob[g] - (Decimal('6.0') if g == 'VLSFO' and days == -4 else 0)
                NoonFuel.objects.create(report=r, grade=g, consumed_mt=burn[g], rob_mt=shown)
                rob[g] = shown
        invs[0].decide(op, approve=True)                     # waits for Finans
        invs[3].decide(op, approve=False, note='Teklifle uyuşmuyor, revize fatura istendi.')
        invs[5].decide(op, approve=True)                     # fully approved: shows both stamps
        invs[5].decide(fi, approve=True)
        invs[4].decide(op, approve=True)                     # KMN: approved, paid in two parts below
        invs[4].decide(fi, approve=True)

        def order(inv, amount, days):
            return create_order(fi, company=co, supplier=inv.supplier, currency=inv.currency,
                                account=accounts[inv.currency], payee_iban=inv.supplier.iban,
                                pay_date=today + timedelta(days=days), note='', amounts={inv.pk: Decimal(amount)})
        paid = order(invs[5], '9760.00', 0)
        paid.decide(mudur, approve=True)
        paid.mark_paid(fi, today, 'DK-2026-114508')
        part = order(invs[4], '1000.00', 0)                        # KMN: first part paid -> "Kısmen ödendi"
        part.decide(mudur, approve=True)
        part.mark_paid(fi, today, 'DK-2026-114611')
        order(invs[4], '500.00', 2).decide(mudur, approve=True)    # approved, waiting to be paid
        order(invs[4], '1500.00', 5)                               # waiting for payment approval
        self.stdout.write(self.style.SUCCESS('Demo data created.'))
        if not os.environ.get('LIMAN_DEMO_PASSWORD'):
            self.stdout.write(f'Demo password for all users: {password}')
