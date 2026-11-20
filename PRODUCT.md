# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

- **Backend:** Django, kept for the rebuild (user decision, 20 Nov 2026).
- **UI framework:** Bootstrap, latest stable release (user decision, 20 Nov 2026). Pinned at 5.3.9 and served from the project's own static files; upgrade deliberately rather than tracking a floating tag.
- The rebuild renders server-side Django templates (chosen for the first build because it suits slow connections and needs little JavaScript).

## Users

Every role in a shipping and logistics group works in it daily:

- **Finance and accounting:** enter incoming expense invoices, route them through department approval, create payment orders, bank transfers and inter-account transfers (virman), check bank balances.
- **Ship and voyage operations:** manage voyages, the fleet, ship budgets, bunker (fuel) deliveries and daily oil/fuel consumption.
- **Warehouse and logistics staff:** warehouse entry/exit slips, stock inventory, bonded warehouse (antrepo) facilities, service cards, project revenue and cost.
- **Holding management:** the executive dashboard, the approval pool and the consolidated holding finance report.

## Product Purpose

Liman360 is a maritime and logistics ERP: one system for a shipping group's voyages, fleet, fuel, warehouses, purchasing, invoices, payments and group-level reporting. It replaces scattered spreadsheets and separate tools with shared records and approval flows across companies in the group.

Success is not yet defined in measurable terms (open decision).

## Positioning

A new product built by KAFDEV Bilişim, separate from the Bplus / BattalNET logistics ERP. It is meant to be sold to many shipping companies, not built for a single client.

What makes it different from neighbouring ERPs has not been stated yet (open decision). The prototype's scope suggests the angle is one system that covers both ship operations (voyages, bunkers, consumption, ship budgets) and group finance across several companies, but this is an inference, not a confirmed claim.

## Operating Context

- Used in Turkish. Module names follow Turkish shipping and finance terms (Sefer, Bunker, Antrepo, Cari, Virman, Onay Havuzu).
- Multi-company groups: one holding with several group companies and their banks; invoices are assigned to a group company and optionally a ship.
- Multi-currency: USD, EUR and TRY, with daily TCMB (Central Bank of Turkey) exchange rates shown in the header.
- Approval flow: an entered expense invoice goes to a department approval pool before payment.
- Purchasing runs as purchase request (PR) then purchase order (PO).
- Reference data: customer/supplier accounts (cari), group companies and banks, ports and routes, currencies.
- Access is role-based, with a user list, a rights/role matrix and a system activity log.
- Used everywhere: office desktops all day, phones (managers approving and checking figures), and laptops/tablets aboard ships or at the port, sometimes on poor connections (confirmed 20 Nov 2026).

## Capabilities and Constraints

Modules in the current prototype (rebuild from scratch, same domain):

- Logistics and bonded warehouse: entry/exit slips, stock, service centre, warehouse facilities, project revenue/costs.
- Operations: voyages, fleet/ship management, ship budgets, bunker deliveries, daily oil/fuel consumption, proposal/feasibility worksheet.
- Invoices and expenses: incoming expense invoices, income invoices, new invoice entry, department approval pool.
- Payments and finance: payments and collections, bank transfer orders, virman, bank balances, payment orders.
- Purchasing: purchase requests (PR), purchase orders (PO).
- Definitions: customer/supplier accounts, group companies and banks, ports and routes, currencies and TCMB rates.
- Reports: report centre, consolidated holding finance report, proposal and feasibility worksheet.
- System: user management, rights/role matrix, system logs, help and support.

Constraints:

- Must work for many separate customer companies. How tenants are separated (separate databases, separate deployments or shared) is an open decision.
- Money must be handled per currency; totals must not silently add different currencies together.

Open decisions: what makes it different from other ERPs, how success is measured, tenancy model, accessibility standard, pricing and deployment model.

## Brand Commitments

- Product name: **Liman360** ("Liman360 ERP" in the prototype). The prototype uses an anchor icon as its mark; whether that is final has not been confirmed.
- Built and sold by KAFDEV Bilişim. KAFDEV's own brand rules are in `../BRAND.md`; how much of KAFDEV's brand shows inside Liman360 has not been decided.
- The prototype login shows "Karson Bilişim Denizcilik & Finans". That is customer/tenant text, not the product's own identity.

## Evidence on Hand

- Live prototype: https://liman360-server.krsn.dev/ (test account `deneme`, holding example data such as the ship M/V BATTAL G).
- UI audit of the prototype: `../liman360-audit/report.html`, screenshots in `../liman360-audit/shots/`, and `../raporlar/liman360-arayuz-denetimi.html`.
- Security report: `../liman360-audit/liman360-guvenlik-raporu.pdf`.
- Browse screenshots: `../.gstack/browse-reports/2026-11-20-1959/screenshots/`.
- No customers apart from the prototype's data, no testimonials, case studies, metrics, pricing or certifications exist. Do not invent any.

## Product Principles

1. **One record, every department.** A voyage, invoice or payment is entered once and seen by operations, finance and management, not re-keyed between modules.
2. **Approval before money moves.** Invoices and payments follow explicit approval steps with a visible audit trail.
3. **Currency is never ambiguous.** Every amount carries its currency, rates come from TCMB, and mixed currencies are never summed silently.
4. **Built for many customers.** Nothing customer-specific (names, banks, ships, categories) is hard-coded into the product.
5. **Turkish shipping language first.** Use the terms the users already use, in Turkish, with no translated or mixed-language labels.
