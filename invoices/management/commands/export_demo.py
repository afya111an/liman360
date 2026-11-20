"""Render the app with synthetic demo data into static HTML for GitHub Pages.

Uses a throwaway test database, so the real database is never touched.
"""
import io
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import Client
from django.test.utils import override_settings

from invoices.models import Invoice, waiting_for

MARKER = '.liman-demo'


class Command(BaseCommand):
    help = 'Export a static, click-through demo (synthetic data, no saving) for GitHub Pages.'

    def add_arguments(self, parser):
        parser.add_argument('--out', default='docs', help='Output folder (default: docs)')
        parser.add_argument('--base', default='/liman360', help='URL path the site is served under')
        parser.add_argument('--as-user', default='operasyon', help='Demo user whose view is exported')

    def handle(self, *args, out, base, as_user, **opts):
        out = Path(out).resolve()
        base = '/' + base.strip('/') if base.strip('/') else ''
        if out.exists() and any(out.iterdir()) and not (out / MARKER).exists():
            raise CommandError(f'{out} is not empty and was not made by export_demo; refusing to overwrite it.')
        shutil.rmtree(out, ignore_errors=True)

        old_name = connection.creation.create_test_db(verbosity=0, autoclobber=True)
        try:
            call_command('seed_demo', stdout=io.StringIO())
            with override_settings(LIMAN_STATIC_DEMO=True, STATIC_URL='/static/', ALLOWED_HOSTS=['testserver']):
                pages = self._render(as_user, base)
        finally:
            connection.creation.destroy_test_db(old_name, verbosity=0)

        for path, html in pages.items():
            target = out / path.strip('/') / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding='utf-8')
        start = f'{base}/faturalar/onay/'
        (out / 'index.html').write_text(
            f'<!doctype html><meta charset="utf-8"><title>Liman360 demo</title>'
            f'<meta http-equiv="refresh" content="0; url={start}"><a href="{start}">Liman360 demo</a>',
            encoding='utf-8')
        shutil.copytree(settings.BASE_DIR / 'static', out / 'static', dirs_exist_ok=True)
        (out / '.nojekyll').touch()
        (out / MARKER).touch()
        self._check(out, base, pages)
        self.stdout.write(self.style.SUCCESS(f'Exported {len(pages)} pages to {out}'))

    def _render(self, username, base):
        client = Client()
        user = User.objects.get(username=username)
        client.force_login(user)
        paths = ['/faturalar/onay/', '/faturalar/tumu/', '/faturalar/yeni/']
        paths += [f'/faturalar/tumu/{pk}/' for pk in Invoice.objects.values_list('pk', flat=True)]
        paths += [f'/faturalar/onay/{pk}/' for pk in waiting_for(user)]
        pages = {}
        for p in paths:
            r = client.get(p)
            if r.status_code != 200:
                raise CommandError(f'{p} returned {r.status_code}')
            # Root-relative URLs get the Pages base path (e.g. /liman360/...).
            pages[p] = re.sub(r'((?:href|src|action)=")/(?!/)', rf'\1{base}/', r.content.decode())
        return pages

    def _check(self, out, base, pages):
        """Every internal link and asset must point at a file this export wrote."""
        for path, html in pages.items():
            for url in re.findall(r'(?:href|src)="(/[^"#?]*)', html):
                rel = url[len(base):] if base and url.startswith(base) else None
                assert rel is not None, f'{path}: link {url} is outside {base}'
                if rel in ('/cikis/', '/tanimlar/'):
                    continue
                f = out / rel.lstrip('/')
                assert f.is_file() or (f / 'index.html').is_file(), f'{path}: {url} has no exported file'
