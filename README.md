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
