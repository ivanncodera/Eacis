/**
 * E-ACIS Electronic Home Appliance UI Animation Controller
 * Architecture: Compositor-Only (transform & opacity), Duplication-Safe, Accessible
 * Timing: Natural cubic-bezier & ease-in-out (150ms - 300ms)
 */

(function () {
  'use strict';

  // Motion Sensitivity Check
  function isReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  // Toast Notification System (Hardware-Accelerated)
  function showApplianceToast(message, type = 'info') {
    let container = document.getElementById('appliance-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'appliance-toast-container';
      container.className = 'appliance-toast-container';
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'appliance-toast';
    toast.setAttribute('role', 'status');

    const iconSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    iconSvg.setAttribute('width', '18');
    iconSvg.setAttribute('height', '18');
    iconSvg.setAttribute('viewBox', '0 0 24 24');
    iconSvg.setAttribute('fill', 'none');
    iconSvg.setAttribute('stroke', '#10b981');
    iconSvg.setAttribute('stroke-width', '2');
    iconSvg.setAttribute('stroke-linecap', 'round');
    iconSvg.setAttribute('stroke-linejoin', 'round');

    const path1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path1.setAttribute('d', 'M22 11.08V12a10 10 0 1 1-5.93-9.14');
    const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    polyline.setAttribute('points', '22 4 12 14.01 9 11.01');
    iconSvg.appendChild(path1);
    iconSvg.appendChild(polyline);

    const textSpan = document.createElement('span');
    textSpan.textContent = message;

    toast.appendChild(iconSvg);
    toast.appendChild(textSpan);
    container.appendChild(toast);

    // Auto-dismiss with compositor transition
    setTimeout(function () {
      if (isReducedMotion()) {
        toast.remove();
        return;
      }

      toast.classList.add('is-dismissing');
      toast.addEventListener('animationend', function () {
        toast.remove();
      }, { once: true });
    }, 2800);
  }

  // Bind Add-to-Cart & Action Micro-Interactions
  function initCartMicroInteractions() {
    const buttons = document.querySelectorAll('.direct-cart-btn, .cart-action-btn, [data-cart-action-btn]');

    buttons.forEach(function (btn) {
      // Duplication Check: Prevent multiple bindings
      if (btn.dataset.animBound === 'true') return;
      btn.dataset.animBound = 'true';

      btn.addEventListener('click', function (e) {
        // State Validation: Prevent overlapping animations on rapid clicks
        if (btn.dataset.animating === 'true') return;
        btn.dataset.animating = 'true';

        const label = btn.querySelector('.btn-label, span:last-child');
        const originalText = label ? label.textContent : '';

        if (label && originalText && !originalText.includes('Added')) {
          label.textContent = 'Adding...';
        }

        if (isReducedMotion()) {
          setTimeout(function () {
            if (label && originalText) label.textContent = originalText;
            btn.dataset.animating = 'false';
          }, 600);
          return;
        }

        // Hardware-Accelerated Web Animations API Pulse (180ms, cubic-bezier)
        const pulseAnim = btn.animate(
          [
            { transform: 'scale(1)', opacity: 1 },
            { transform: 'scale(1.06)', opacity: 0.94 },
            { transform: 'scale(1)', opacity: 1 }
          ],
          {
            duration: 180,
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)'
          }
        );

        pulseAnim.onfinish = function () {
          setTimeout(function () {
            if (label && originalText) label.textContent = originalText;
            btn.dataset.animating = 'false';
          }, 450);
        };
      });
    });
  }

  // Bind Filter Chip Micro-Interactions
  function initFilterChipInteractions() {
    const chips = document.querySelectorAll('.filter-pill-link, .filter-chip, [data-filter-chip]');

    chips.forEach(function (chip) {
      if (chip.dataset.animBound === 'true') return;
      chip.dataset.animBound = 'true';

      chip.addEventListener('click', function () {
        if (isReducedMotion()) return;

        // Subtle tactile tap feedback (150ms)
        chip.animate(
          [
            { transform: 'scale(1)' },
            { transform: 'scale(0.95)' },
            { transform: 'scale(1)' }
          ],
          {
            duration: 150,
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)'
          }
        );
      });
    });
  }

  // Bind Quick Spec Trigger Micro-Interactions
  function initQuickSpecInteractions() {
    const triggers = document.querySelectorAll('[data-quick-spec-btn]');

    triggers.forEach(function (trigger) {
      if (trigger.dataset.animBound === 'true') return;
      trigger.dataset.animBound = 'true';

      trigger.addEventListener('click', function () {
        if (isReducedMotion()) return;

        // 160ms trigger spring feedback
        trigger.animate(
          [
            { transform: 'scale(1)' },
            { transform: 'scale(0.96)' },
            { transform: 'scale(1)' }
          ],
          {
            duration: 160,
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)'
          }
        );
      });
    });
  }

  // Main Initializer
  function initApplianceAnimations() {
    initCartMicroInteractions();
    initFilterChipInteractions();
    initQuickSpecInteractions();
  }

  // Auto-init on DOMContentLoaded or immediate if ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApplianceAnimations);
  } else {
    initApplianceAnimations();
  }

  // Export functions to global scope for dynamic components
  window.initApplianceAnimations = initApplianceAnimations;
  window.showApplianceToast = showApplianceToast;
})();
