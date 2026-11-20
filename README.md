# Liman360

Maritime and logistics ERP (rebuild). First module: expense invoices with a multi-step approval flow.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
LIMAN_DEMO_PASSWORD=<choose one> .venv/bin/python manage.py seed_demo   # synthetic demo data, empty DB only
.venv/bin/python manage.py runserver 8360
```

Demo users: `muhasebe` (enters invoices), `operasyon` (1st approval), `finans` (2nd approval), `yonetici` (admin at `/tanimlar/`).

## Tests

```bash
.venv/bin/python manage.py test invoices
```

## Production settings

Set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS`; run `collectstatic`. The default database is SQLite for development only.

## Exchange rates (TCMB)

`fetch_tcmb_rates` stores TCMB's *döviz satış* rate for every currency the app uses (USD, EUR).
TCMB publishes around 15:30 on business days; there is no bulletin on weekends and holidays, and an invoice
then uses the latest earlier rate. Run it daily on the server, for example with cron:

```cron
# 16:05 Mon-Fri, Istanbul time
5 16 * * 1-5  cd /srv/liman360 && .venv/bin/python manage.py fetch_tcmb_rates >> /var/log/liman360-tcmb.log 2>&1
```

First install or after downtime: `manage.py fetch_tcmb_rates --days 30` fills the gap. The command exits
non-zero when TCMB is unreachable or a currency is missing, so cron mail or log monitoring will show failures.
Rates can still be corrected by hand in Tanımlar → Döviz kurları; those are marked "Elle girildi".

## How approval works

Approval steps are set up in Tanımlar → Onay adımları (order + user group). A new invoice waits on step 1, then step 2, and so on.
The person who entered an invoice cannot approve it, one person cannot approve two steps of the same invoice, and rejecting needs a reason.
If no steps are defined, new invoices are approved on save.

## Static demo (GitHub Pages)

`docs/` holds a click-through demo rendered from synthetic data (nothing saves). Regenerate it after UI changes:

```bash
.venv/bin/python manage.py export_demo   # writes docs/ for https://afya111an.github.io/liman360/
```

GitHub serves it once Pages is set to **Deploy from a branch → main → /docs** (repository Settings → Pages).

The **Refresh demo** workflow (`.github/workflows/demo.yml`) regenerates `docs/` every weekday at 16:30 Istanbul time
with that day's TCMB rates and commits it; the push starts the Pages build. Run it by hand from the Actions tab
("Refresh demo" → "Run workflow").
