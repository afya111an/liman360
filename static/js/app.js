// Block double submits: the first submit disables the form's buttons (the server also locks the row).
document.addEventListener('submit', (e) => {
  const form = e.target.closest('form[data-once]');
  if (!form) return;
  if (form.dataset.sent) { e.preventDefault(); return; }
  // Fields marked data-required-for="reddet iptal" must be filled for those submit buttons only.
  const action = e.submitter && e.submitter.value;
  const missing = [...form.querySelectorAll('[data-required-for]')].find(
    (f) => f.dataset.requiredFor.split(' ').includes(action) && !f.value.trim());
  if (missing) {
    e.preventDefault();
    missing.setAttribute('aria-invalid', 'true');
    missing.setCustomValidity('Bu işlem için bu alanı doldurun.');
    missing.reportValidity();
    missing.addEventListener('input', () => { missing.setCustomValidity(''); missing.removeAttribute('aria-invalid'); }, { once: true });
    return;
  }
  form.dataset.sent = '1';
  // Defer so the clicked button's name/value is still submitted.
  setTimeout(() => form.querySelectorAll('button[type=submit]').forEach((b) => { b.disabled = true; }), 0);
});
// Restore buttons when the page comes back from the bfcache.
window.addEventListener('pageshow', (e) => {
  if (!e.persisted) return;
  document.querySelectorAll('form[data-sent]').forEach((f) => {
    delete f.dataset.sent;
    f.querySelectorAll('button').forEach((b) => { b.disabled = false; });
  });
});
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-toggle-pw]');
  if (!btn) return;
  const input = document.getElementById(btn.getAttribute('aria-controls'));
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.textContent = show ? 'Gizle' : 'Göster';
  btn.setAttribute('aria-pressed', String(show));
});
// After a failed save, put the cursor in the first field that needs fixing.
document.querySelector('form [aria-invalid="true"]')?.focus();

// Payment order entry: "Tamamı" fills the open balance; the footer shows the running total.
const totalOut = document.getElementById('po-total');
if (totalOut) {
  const num = (v) => Number(String(v).trim().replace(/\s/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.')) || 0;
  const fmt = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const inputs = [...document.querySelectorAll('input[data-open]')];
  const update = () => { totalOut.value = `${fmt.format(inputs.reduce((s, i) => s + num(i.value), 0))} ${totalOut.dataset.currency}`; };
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-fill]');
    if (!b) return;
    const input = document.getElementById(b.dataset.fill);
    input.value = fmt.format(Number(input.dataset.open));
    update();
  });
  inputs.forEach((i) => i.addEventListener('input', update));
  update();
}

// Payment order: changing who pays whom reloads the open invoices, so lines never belong to an older choice.
const pick = document.getElementById('po-pick');
if (pick) {
  pick.addEventListener('change', () => {
    const entry = document.getElementById('po-entry');
    if (entry) entry.querySelectorAll('input, select, textarea, button').forEach((el) => { el.disabled = true; });
    if ([...pick.elements].filter((el) => el.tagName === 'SELECT').every((el) => el.value)) pick.requestSubmit();
  });
}
