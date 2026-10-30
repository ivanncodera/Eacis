/*
 * return-modal-fix.js
 * Fallback modal wiring for the Returns page.
 * Idempotent: will not re-initialize if already applied.
 */
(function () {
  const overlay = document.getElementById('return-modal-overlay');
  if (!overlay) return;
  if (overlay.dataset.eacisModalInitialized === 'true') return;
  overlay.dataset.eacisModalInitialized = 'true';

  const trigger = document.getElementById('new-return-trigger');
  const modal = document.getElementById('return-modal');
  const closeX = document.getElementById('close-modal-x');
  const closeBtn = document.getElementById('close-modal-btn');
  const closeButtons = [closeX, closeBtn].filter(Boolean);
  let lastFocused = null;

  function openModal(ev) {
    try { if (ev && typeof ev.preventDefault === 'function') ev.preventDefault(); } catch (e) {}
    if (!overlay || !modal) return;
    if (trigger && trigger.disabled) return;
    lastFocused = document.activeElement;
    overlay.classList.add('is-open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    if (closeX && typeof closeX.focus === 'function') closeX.focus();
    else if (modal && typeof modal.focus === 'function') modal.focus();
  }

  function closeModal(ev) {
    try { if (ev && typeof ev.preventDefault === 'function') ev.preventDefault(); } catch (e) {}
    if (!overlay || !modal) return;
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    try { if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus(); } catch (e) {}
  }

  if (trigger) {
    trigger.addEventListener('click', openModal, { passive: false });
    trigger.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') openModal(ev); });
  }

  closeButtons.forEach((btn) => btn.addEventListener('click', closeModal));

  overlay.addEventListener('click', function (ev) {
    if (ev.target === overlay) closeModal(ev);
  });

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && overlay.classList.contains('is-open')) closeModal(ev);
  });

  // Auto-open when server indicated validation errors or via URL params
  try {
    if (modal && modal.dataset.hasErrors === 'true') openModal();
    const params = new URLSearchParams(window.location.search);
    if (params.has('order_ref')) {
      openModal();
      const targetRef = params.get('order_ref');
      const select = document.querySelector('select[name="order_ref"]');
      if (select) {
        select.value = targetRef;
        if (select.value !== targetRef) {
          const opt = new Option(targetRef + ' (Escalated)', targetRef, true, true);
          select.add(opt);
        }
      }
    }
  } catch (e) {
    console.warn('return-modal-fix auto-open failed', e);
  }

  console.debug('return-modal-fix initialized');
})();
