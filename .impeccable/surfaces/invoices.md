---
version: 1
slug: "invoices"
primary_target: "invoices"
related_targets: []
---

## Scope

Invoice approval flow: approval pool, all expense invoices list, invoice detail with approve/reject, new invoice entry, plus the shared app shell and login. Visitor mode: Operate.

## Audience and task

Finance staff enter invoices; department and finance approvers approve or reject, often on a phone; managers check pending totals. Success: an approver finds what is waiting, sees every fact needed, and decides in one action without double submits. Constraints: Turkish UI, per-currency totals, Django templates with Bootstrap 5.3.9, works on phones and poor connections.

## Direction contract

THESIS: Every invoice is a document, shown as a bill-of-lading form with numbered boxed fields; approval is a stamp on that document. Refuses the generic Bootstrap admin of cards, badges and a sidebar duplicating the top nav.

OWN-WORLD: Form-paper ground #FBFBF8, navy ink #1B2A4A for text and the top bar, pale blue form rules #9DB3CF, stamp violet #5B3E96 for approval states and the primary action. Square corners, 1px rules, small tracked caps for field captions with a boxed field number.

STORY: The approver sees how much is waiting and what falls due first, opens one invoice, reads it like the paper original, and stamps it approved or rejected with a reason.

FIRST VIEWPORT: Navy top bar with one module nav. Left column (about 520px) lists pending invoices as ruled rows: number, supplier, amount with currency. Right: the selected invoice as a 4-column boxed form, number as headline, state at top right, amount box full width, existing approvals as rotated violet stamps, actions Onayla / Reddet below. On phones the list is the page and the form opens on its own URL.

FORM: Konşimento (bill of lading), grounded candidate 1 of 7, chosen as the pick. seed:2f1781a97d0116ed

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

Tenancy model; TCMB rate fetching; number of approval levels per customer.
