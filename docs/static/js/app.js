// Block double submits: the first submit disables the form's buttons (the server also locks the row).
document.addEventListener('submit', (e) => {
  const form = e.target.closest('form[data-once]');
  if (!form) return;
  if (form.dataset.sent) { e.preventDefault(); return; }
  const note = form.querySelector('[name=gerekce]');
  if (note && e.submitter && e.submitter.value === 'reddet' && !note.value.trim()) {
    e.preventDefault();
    note.setAttribute('aria-invalid', 'true');
    note.setCustomValidity('Reddetmek için bir gerekçe yazın.');
    note.reportValidity();
    note.addEventListener('input', () => { note.setCustomValidity(''); note.removeAttribute('aria-invalid'); }, { once: true });
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
