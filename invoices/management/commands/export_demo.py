"""Render the app with synthetic demo data into static HTML for GitHub Pages.

Uses a throwaway test database, so the real database is never touched. The demo is exported once per demo
user, each with their real role and permissions; a switcher in the top bar moves between them:
Selin Demir (Finans) at the site root, Mert Kaya (Operasyon) under /mert/, Kemal Aydın (Ödeme onayı) under /kemal/.
"""
import io
import logging
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

from invoices.models import Invoice, Vessel, waiting_for

MARKER = '.liman-demo'
# (username, URL prefix inside the site, role shown in the switcher, start page)
DEMO_USERS = [
    ('finans', '', 'Finans', '/faturalar/onay/'),
    ('operasyon', 'mert', 'Operasyon', '/operasyon/seferler/'),
    ('mudur', 'kemal', 'Ödeme onayı', '/odemeler/onay/'),
]
SWITCH = '__DEMO_SWITCH__'  # placeholder href the template writes; replaced with the real URL after rendering


class Command(BaseCommand):
    help = 'Export a static, click-through demo (synthetic data, no saving) for GitHub Pages.'

    def add_arguments(self, parser):
        parser.add_argument('--out', default='docs', help='Output folder (default: docs)')
        parser.add_argument('--base', default='/liman360', help='URL path the site is served under')

    def handle(self, *args, out, base, **opts):
        out = Path(out).resolve()
        site = '/' + base.strip('/') if base.strip('/') else ''
        if out.exists() and any(out.iterdir()) and not (out / MARKER).exists():
            raise CommandError(f'{out} is not empty and was not made by export_demo; refusing to overwrite it.')
        shutil.rmtree(out, ignore_errors=True)

        # Screens a demo user may not open are skipped on purpose; don't log each 403.
        logging.getLogger('django.request').setLevel(logging.ERROR)
        old_name = connection.creation.create_test_db(verbosity=0, autoclobber=True)
        try:
            call_command('seed_demo', stdout=io.StringIO())
            # Replace the seed's sample rates with real TCMB rates as of today, when TCMB is reachable.
            try:
                call_command('fetch_tcmb_rates', days=14, stdout=io.StringIO())
                self.stdout.write('TCMB rates fetched.')
            except CommandError as e:
                self.stderr.write(f'TCMB not reachable, demo keeps sample rates: {e}')
            switcher = [{'username': u, 'role': role, 'name': User.objects.get(username=u).get_full_name()}
                        for u, _, role, _ in DEMO_USERS]
            trees = {}
            with override_settings(LIMAN_STATIC_DEMO=True, LIMAN_DEMO_USERS=switcher, STATIC_URL='/static/',
                                   ALLOWED_HOSTS=['testserver']):
                for username, prefix, _, _ in DEMO_USERS:
                    trees[username] = self._render(username, site, self._user_base(site, prefix))
        finally:
            connection.creation.destroy_test_db(old_name, verbosity=0)

        written = {}
        for username, prefix, _, start in DEMO_USERS:
            ubase = self._user_base(site, prefix)
            for path, html in trees[username].items():
                for other, oprefix, _, ostart in DEMO_USERS:
                    # same screen for the other user when they can see it, otherwise their start page
                    target = self._user_base(site, oprefix) + (path if path in trees[other] else ostart)
                    html = html.replace(f'{SWITCH}{other}{SWITCH}', target)
                f = out / prefix / path.strip('/') / 'index.html'
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(html, encoding='utf-8')
                written[f'{prefix}{path}'] = html
            self._redirect(out / prefix / 'index.html', ubase + start)
        shutil.copytree(settings.BASE_DIR / 'static', out / 'static', dirs_exist_ok=True)
        (out / '.nojekyll').touch()
        (out / MARKER).touch()
        self._check(out, site, written)
        counts = ', '.join(f'{u} {len(trees[u])}' for u, *_ in DEMO_USERS)
        self.stdout.write(self.style.SUCCESS(f'Exported {len(written)} pages ({counts}) to {out}'))

    @staticmethod
    def _user_base(site, prefix):
        return f'{site}/{prefix}' if prefix else site

    @staticmethod
    def _redirect(file, url):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f'<!doctype html><meta charset="utf-8"><title>Liman360 demo</title>'
                        f'<meta http-equiv="refresh" content="0; url={url}"><a href="{url}">Liman360 demo</a>',
                        encoding='utf-8')

    def _render(self, username, site, ubase):
        client = Client()
        user = User.objects.get(username=username)
        client.force_login(user)
        from operations.models import BunkerDelivery, NoonReport, Voyage
        from payments.models import PaymentOrder
        paths = ['/faturalar/onay/', '/faturalar/tumu/', '/faturalar/yeni/']
        paths += [f'/faturalar/tumu/{pk}/' for pk in Invoice.objects.values_list('pk', flat=True)]
        paths += [f'/faturalar/onay/{pk}/' for pk in waiting_for(user)]
        paths += ['/odemeler/onay/', '/odemeler/odenecek/', '/odemeler/tumu/', '/odemeler/yeni/']
        for o in PaymentOrder.objects.all():
            paths.append(f'/odemeler/tumu/{o.pk}/')
            scope = {'PENDING': 'onay', 'APPROVED': 'odenecek'}.get(o.status)
            if scope:
                paths.append(f'/odemeler/{scope}/{o.pk}/')
        paths += ['/operasyon/seferler/', '/operasyon/gemiler/', '/operasyon/bunker/', '/operasyon/raporlar/',
                  '/operasyon/seferler/yeni/', '/operasyon/gemiler/yeni/', '/operasyon/bunker/yeni/',
                  '/operasyon/raporlar/yeni/']
        paths += [f'/operasyon/seferler/{pk}/' for pk in Voyage.objects.values_list('pk', flat=True)]
        paths += [f'/operasyon/gemiler/{pk}/' for pk in Vessel.objects.values_list('pk', flat=True)]
        paths += [f'/operasyon/bunker/{pk}/' for pk in BunkerDelivery.objects.values_list('pk', flat=True)]
        paths += [f'/operasyon/raporlar/{pk}/' for pk in NoonReport.objects.values_list('pk', flat=True)]
        pages = {}
        for p in paths:
            r = client.get(p)
            if r.status_code == 403:
                continue  # this user's role cannot open the screen, exactly as in the app
            if r.status_code != 200:
                raise CommandError(f'{username} {p} returned {r.status_code}')
            html = r.content.decode()
            # Static files are shared by all users; page links stay inside this user's tree.
            html = re.sub(r'((?:href|src)=")/static/', rf'\1{site}/static/', html)
            html = re.sub(rf'((?:href|src|action)=")/(?!/|{re.escape(site.lstrip("/"))}/static/)', rf'\1{ubase}/', html)
            pages[p] = html
        return pages

    def _check(self, out, site, pages):
        """Every internal link and asset must point at a file this export wrote; no placeholder may remain."""
        for path, html in pages.items():
            assert SWITCH not in html, f'{path}: unresolved user switch link'
            for url in re.findall(r'(?:href|src)="(/[^"#?]*)', html):
                rel = url[len(site):] if site and url.startswith(site) else None
                assert rel is not None, f'{path}: link {url} is outside {site}'
                if rel.endswith(('/cikis/', '/tanimlar/')):
                    continue
                f = out / rel.lstrip('/')
                assert f.is_file() or (f / 'index.html').is_file(), f'{path}: {url} has no exported file'
