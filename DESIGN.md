---
name: Liman360
description: Maritime and logistics ERP where every record reads as a bill-of-lading form and every approval is a stamp.
colors:
  form-paper: "#FBFBF8"
  sheet-white: "#FFFFFF"
  navy-ink: "#1B2A4A"
  ink-secondary: "#4A5874"
  form-rule: "#9DB3CF"
  rule-strong: "#6F84A6"
  selected-wash: "#EAF0F8"
  hover-wash: "#F2F5FA"
  stamp-violet: "#5B3E96"
  stamp-violet-deep: "#482F7A"
  stamp-tint: "#E6DFF3"
  reject-red: "#B42318"
typography:
  display:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "0.005em"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 650
    lineHeight: 1.2
  amount:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 650
    lineHeight: 1.2
    fontFeature: "tnum"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.01em"
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.06em"
  stamp:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "0.1em"
  overprint:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "0.16em"
rounded:
  none: "0px"
spacing:
  xs: "0.5rem"
  sm: "0.75rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2.5rem"
components:
  button-stamp:
    backgroundColor: "{colors.stamp-violet}"
    textColor: "{colors.sheet-white}"
    rounded: "{rounded.none}"
    padding: "0.55rem 1rem"
    height: "40px"
  button-stamp-hover:
    backgroundColor: "{colors.stamp-violet-deep}"
    textColor: "{colors.sheet-white}"
  button-quiet-ink:
    backgroundColor: "transparent"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    padding: "0.55rem 1rem"
    height: "40px"
  button-quiet-ink-hover:
    backgroundColor: "{colors.hover-wash}"
    textColor: "{colors.navy-ink}"
  button-reject:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.reject-red}"
    rounded: "{rounded.none}"
    padding: "0.55rem 1rem"
    height: "40px"
  button-reject-hover:
    backgroundColor: "{colors.reject-red}"
    textColor: "{colors.sheet-white}"
  input:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.navy-ink}"
    rounded: "{rounded.none}"
    height: "40px"
  form-field:
    backgroundColor: "{colors.form-paper}"
    textColor: "{colors.navy-ink}"
    typography: "{typography.body}"
    padding: "0.55rem 0.75rem 0.75rem"
  ledger-row:
    backgroundColor: "{colors.sheet-white}"
    textColor: "{colors.navy-ink}"
    padding: "0.8rem 1rem"
  ledger-row-selected:
    backgroundColor: "{colors.selected-wash}"
    textColor: "{colors.navy-ink}"
  top-bar:
    backgroundColor: "{colors.navy-ink}"
    textColor: "{colors.form-paper}"
    height: "56px"
  stamp:
    textColor: "{colors.stamp-violet}"
    typography: "{typography.stamp}"
    padding: "0.45rem 0.9rem 0.5rem"
  overprint:
    textColor: "{colors.stamp-violet}"
    typography: "{typography.overprint}"
    padding: "0.3rem 1.1rem 0.35rem"
---

# Design System: Liman360

## Overview

**Creative North Star: "The Konşimento"**

Every record is a document, drawn as a bill-of-lading form: a navy-ink outer rule, a grid of numbered boxed fields separated by pale blue form rules, small tracked caps for each caption. The user reads an invoice the way they would read the paper original, then stamps it. Approval is not a badge or a toggle; it is a rotated violet stamp pressed onto the form, and a finished document carries its result as a large overprint across its head.

The surface is dense and calm. A navy top bar holds one module nav and the day's exchange rates; below it a ruled ledger lists records on the left and the selected document sits on the right. Nothing floats: there are no cards, no shadows, no rounded corners. Hierarchy comes from rules, weight and the single violet voice.

The world refuses the generic Bootstrap admin: cards, pill badges, soft shadows, and a sidebar duplicating the top nav.

**Key Characteristics:**
- Records rendered as boxed, numbered form fields on off-white form paper.
- Square corners everywhere; 1px rules, 1.5px ink outer rule on the form.
- One accent, stamp violet, meaning approval and the single primary action.
- Stamps and overprints are the only rotated, uppercase-heavy elements.
- Tabular numerals for every amount, date and count; currency always printed beside the figure.

## Colors

Navy ink on cool off-white form paper, ruled in pale print blue, with one violet stamp and one red rejection.

### Primary
- **Stamp Violet** (stamp-violet): approval stamps, the approved state, the finished-document overprint, focus rings, caret, and the one primary action per screen. **Stamp Violet Deep** is its hover/pressed state and the text colour of confirmation flashes. **Stamp Tint** washes the stamp interior (at 35%) and text selection.

### Secondary
- **Reject Red** (reject-red): rejection stamps and overprint, the outlined reject button, field errors, the required-field asterisk, invalid input borders. Never decorative.

### Neutral
- **Form Paper** (form-paper): page ground and the interior of every form field.
- **Sheet White** (sheet-white): inputs, ledger rows, flashes, the reject button ground; it reads as a fresh slip lying on the paper.
- **Navy Ink** (navy-ink): all primary text, the top bar, the form's outer rule, the selected ledger row's border, the pending state, and the next-approval slot.
- **Ink Secondary** (ink-secondary): field captions, metadata, supplier lines, hints (7:1 on paper).
- **Form Rule** (form-rule): the 1px rules between form fields and ledger rows, the ledger/sheet divider, the subnav underline.
- **Rule Strong** (rule-strong): control borders, field-number boxes, dashed future-approval slots, empty-state border (3.9:1 on paper).
- **Selected Wash** / **Hover Wash**: the selected ledger row and hover on rows and outlined buttons.

### Named Rules
**The One Stamp Rule.** Violet means approval. It marks approved states, stamps, and exactly one primary action per screen; every other action is outlined ink. If two violet buttons appear on one screen, one is wrong.

**The No Amber Rule.** Pending has no hue of its own. Pending is navy ink text with an empty square marker; the next approval slot is a solid 1.5px ink box, later slots are dashed rule-strong boxes.

## Typography

**Display Font:** Archivo variable, self-hosted (latin + latin-ext), with system-ui fallback
**Body Font:** system-ui stack (-apple-system, Segoe UI, Roboto)

**Character:** Archivo's sturdy grotesque carries document numbers, captions, stamps and amounts, the printed parts of the form; the system face carries what was written into it.

### Hierarchy
- **Display** (650, 1.75rem, 1.15): the document number heading the form.
- **Headline** (650, 1.375rem, 1.2): the ledger heading.
- **Amount** (650, 1.625rem, 1.2, tabular): the full-width amount box.
- **Title** (600, 1rem, 1.3): the record number in a ledger row.
- **Body** (400-500, 0.9375rem): field values, rows, controls. Field values sit at 500.
- **Label** (600, 0.75rem, 0.06em, uppercase): field captions, always preceded by a boxed field number (0.6875rem, tabular, rule-strong 1px box).
- **Stamp** (700, 0.875rem, 0.1em, uppercase) and **Overprint** (800, 1.375rem, 0.16em, uppercase): stamp lettering only.
- Brand wordmark: Archivo 700, 0.1-0.12em tracking, uppercase.

### Named Rules
**The Real Stamp Rule.** Stamp lettering (heavy, widely tracked caps) is reserved for real stamps and overprints that record a decision. Pending slots, statuses in lists and buttons use body type.

**The Tabular Rule.** Every amount, date, rate and count uses tabular numerals, and every amount prints its currency code beside it. Mixed currencies are listed side by side, never summed.

## Layout

A full-width app shell: navy top bar (56px) with module nav, rates and user; a paper subnav (52px) with section tabs, counts in boxed numerals, and the "new" action at the right. Below 768px the top bar collapses behind a toggler and items stack with paper-tinted dividers.

The work area is a two-column grid from 992px: a ledger column (minmax(400px, 34rem)) separated by a form-rule line from a sticky, independently scrolling sheet holding the document (max 60rem). Below 992px the ledger is the page and the document opens on its own URL with a back link.

The form is a 4-column grid with 1px gaps showing the rule colour; fields span 1, 2 or 4 columns. Below 576px it drops to 2 columns and two-span fields go full width. Spacing runs on 0.5 / 0.75 / 1 / 1.5 / 2.5rem; ledger padding 1.5rem, sheet padding 1.5rem 2.5rem on desktop, 1rem on phones.

## Elevation & Depth

Flat. There are no shadows. Depth is conveyed by rules, by white slips on paper, and by the selected row lifting its border to navy. The only stacking is the overprint stamp, which sits above the form's top rule with `mix-blend-mode: multiply` so the rule shows through like ink over print. Box-shadow appears only as inset 3px underlines marking the active tab and as the 3px violet focus ring on inputs.

### Named Rules
**The Ink Not Shadow Rule.** Nothing casts a shadow. Separation is a rule; emphasis is ink weight.

## Shapes

Square corners throughout (Bootstrap radii set to 0). Rules are 1px; the form's outer rule is 1.5px navy ink. Stamps have a double frame: a 2.5px border plus a 1px outline offset 2px (overprint: 3px plus 1.5px offset 3px). Stamps rotate a few degrees (-3deg, alternating +2deg; overprint -6deg). Status markers are small squares: empty for pending, filled for approved, struck diagonally for rejected.

## Components

### Buttons
- **Shape:** square (0), min height 40px (44px on coarse pointers), 600 weight, icon 1em leading.
- **Primary (stamp):** violet fill, white text; deepens on hover/focus. One per screen: approve, save-and-submit, sign in.
- **Outlined ink:** transparent with rule-strong border, navy text; border goes navy with hover wash. All secondary actions, including "Yeni fatura" and cancel.
- **Reject:** white with red border and text, fills red on hover.
- **On the top bar:** outlined paper at 45% opacity (sign out).
- **Busy/disabled:** 60% opacity, no pointer events; forms submit once.

### Inputs / Fields
- **Style:** white, rule-strong 1px border, square, 40px min height; 1rem text on phones.
- **Focus:** violet border plus 3px violet ring at 35%.
- **Error:** red border, field cell washed #FFF7F6, red 0.8125rem message beneath.

### Navigation
- Top bar: paper text at 78% opacity, full paper on hover; active item gets an inset 3px paper underline (underline text on mobile).
- Subnav: ink-secondary text, active tab navy with inset 3px navy underline; counts in a 1px current-colour box.

### Ledger Rows
Stacked white rows sharing 1px form rules; record number (Title), amount with small currency code right-aligned, supplier, then status square and due date. Selected row takes the selected wash and a navy border.

### Bill-of-Lading Form (signature)
Paper cells in a ruled 4-column grid inside a 1.5px navy outer rule; each cell a numbered caption over its value. The amount occupies a full-width box. Approvals are a numbered field holding the stamp row; the decision (note textarea plus approve and reject buttons) is itself the last numbered field inside the form. Entry forms use the same grid with inputs inside the cells.

### Stamps and Overprint (signature)
- **Approval stamp:** violet double-framed box, rotated, stamp lettering for step and approver role, body type for name and timestamp, faint violet tint inside. Rejection stamps are red and quote the reason in italic.
- **Pending slots:** body type; the next slot is a solid 1.5px navy box marked "Bekliyor", later slots dashed rule-strong.
- **Overprint:** a finished document's result (approved or rejected plus date), large stamp lettering, rotated -6deg across the head and the form's top rule, multiply-blended. It is the status text; no separate status label.
- **Motion:** a fresh stamp lands in 0.45s (from 1.35x scale, -9deg, blurred, cubic-bezier(.16,1,.3,1)); none under reduced motion.

## Do's and Don'ts

### Do:
- **Do** draw every record as numbered boxed fields on form paper inside a 1.5px navy outer rule, ruled at 1px in form rule blue.
- **Do** keep one violet primary action per screen; make every other action outlined ink.
- **Do** show pending as navy ink with an empty square, the next approval slot as a solid ink box, later slots dashed.
- **Do** mark a finished document with the rotated, multiply-blended overprint across its head.
- **Do** print every amount with tabular numerals and its currency code.

### Don't:
- **Don't** use rounded corners, cards, pill badges or shadows.
- **Don't** introduce an amber or yellow pending colour.
- **Don't** use stamp lettering for anything that is not a recorded decision.
- **Don't** use violet decoratively or for a second action on the same screen.
- **Don't** add a sidebar that repeats the top nav.
