"""Store TCMB döviz satış rates. Run daily after 15:30 on business days (see README)."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from invoices import tcmb
from invoices.models import Currency, ExchangeRate

CODES = {c for c in Currency.values if c != Currency.TRY}


class Command(BaseCommand):
    help = "Fetch TCMB exchange rates (latest by default; --days N also fills the past N days)."

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=0, help='Also backfill this many past days')

    def handle(self, *args, days, **opts):
        today = timezone.localdate()
        targets = [None] + [today - timedelta(days=n) for n in range(1, days + 1)]
        saved = 0
        for day in targets:
            if day is not None and not tcmb.is_business_day(day):
                continue
            try:
                raw = tcmb.download(day)
            except OSError as e:  # network errors, timeouts, 5xx
                raise CommandError(f'TCMB unreachable ({tcmb.url_for(day)}): {e}')
            if raw is None:
                self.stdout.write(f'{day}: no TCMB bulletin (holiday)')
                continue
            bulletin_day, rates = tcmb.parse(raw, CODES)
            missing = CODES - rates.keys()
            if missing:
                raise CommandError(f'{bulletin_day}: TCMB file has no rate for {", ".join(sorted(missing))}')
            for code, rate in rates.items():
                ExchangeRate.objects.update_or_create(
                    date=bulletin_day, currency=code, defaults={'rate': rate, 'source': ExchangeRate.Source.TCMB})
                saved += 1
            self.stdout.write(f'{bulletin_day}: ' + ', '.join(f'{c} {r}' for c, r in sorted(rates.items())))
        self.stdout.write(self.style.SUCCESS(f'{saved} rates saved.'))
