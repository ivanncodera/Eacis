/* ============================================
   E-ACIS INTERACTION SYSTEM
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ── RIPPLE EFFECT ──
  function createRipple(event) {
    const button = event.currentTarget;
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;

    const ripple = document.createElement('span');
    ripple.className = 'btn__ripple';
    ripple.style.cssText = `
      width: ${size}px; height: ${size}px;
      left: ${x}px; top: ${y}px;
    `;
    button.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
  }

  document.querySelectorAll('.btn--primary, .btn--danger, .btn').forEach(btn => {
    btn.addEventListener('click', createRipple);
  });

  // ── SCROLL REVEAL ──
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const delay = parseInt(el.dataset.delay || 0);
        const stagger = el.closest('.stagger-children');
        
        let finalDelay = delay;
        if (stagger) {
          const index = Array.from(stagger.children).indexOf(el);
          finalDelay += index * 80;
        }

        setTimeout(() => {
          el.classList.add('is-visible');
        }, finalDelay);
        revealObserver.unobserve(el);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  function initReveal() {
    document.querySelectorAll('.reveal:not(.is-visible)').forEach((el) => {
      revealObserver.observe(el);
    });
  }
  
  initReveal();
  window.initReveal = initReveal; // expose for dynamic content

  // ── LAYOUT TOGGLES ──
  const sidebarToggles = document.querySelectorAll('#base-sidebar-toggle, .sidebar__toggle-btn');
  const sidebar = document.querySelector('.sidebar');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const sidebarToggleBtn = document.getElementById('base-sidebar-toggle');

  const setSidebarExpanded = (isExpanded) => {
    if (sidebarToggleBtn) {
      sidebarToggleBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
    }
  };

  const closeMobileSidebar = () => {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    document.body.classList.remove('sidebar-open');
    setSidebarExpanded(false);
  };
  
  if(sidebar) {
    sidebarToggles.forEach(btn => {
      btn.addEventListener('click', () => {
        if (window.innerWidth <= 1023) {
          sidebar.classList.toggle('is-open');
          const isOpen = sidebar.classList.contains('is-open');
          document.body.classList.toggle('sidebar-open', isOpen);
          setSidebarExpanded(isOpen);
        } else {
          sidebar.classList.toggle('collapsed');
          setSidebarExpanded(!sidebar.classList.contains('collapsed'));
        }
      });
    });

    if (window.innerWidth <= 1023) {
      setSidebarExpanded(false);
    }

    if (sidebarBackdrop) {
      sidebarBackdrop.addEventListener('click', closeMobileSidebar);
    }

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
        closeMobileSidebar();
      }
    });

    document.addEventListener('click', (e) => {
      if (window.innerWidth > 1023 || !sidebar.classList.contains('is-open')) return;
      if (e.target.closest('.sidebar') || e.target.closest('#base-sidebar-toggle')) return;
      closeMobileSidebar();
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth > 1023) {
        closeMobileSidebar();
      }
    });
  }

  // Mobile search toggle
  const searchToggle = document.getElementById('base-search-toggle');
  const searchBar = document.querySelector('.topbar__search');
  
  if (searchToggle && searchBar) {
    searchToggle.addEventListener('click', () => {
      searchBar.classList.toggle('is-open');
      searchToggle.setAttribute('aria-expanded', searchBar.classList.contains('is-open') ? 'true' : 'false');
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && searchBar.classList.contains('is-open')) {
        searchBar.classList.remove('is-open');
        searchToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

});

// ── GLOBAL EACIS NAMESPACE ──
window.EACIS = window.EACIS || {};

// ── FLY TO CART ANIMATION ──
window.EACIS.flyToCart = function(imgEl, cartIconEl) {
  const target = cartIconEl || document.querySelector('.cart-icon');
  if (!imgEl || !target) return;
  
  const rect = imgEl.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  
  const clone = imgEl.cloneNode(true);
  
  Object.assign(clone.style, {
    position: 'fixed',
    top: rect.top + 'px',
    left: rect.left + 'px',
    width: rect.width + 'px',
    height: rect.height + 'px',
    zIndex: '9999',
    transition: 'all 0.85s cubic-bezier(0.19, 1, 0.22, 1)',
    pointerEvents: 'none',
    borderRadius: '12px',
    boxShadow: 'var(--shadow-lg)',
    objectFit: 'cover'
  });
  
  document.body.appendChild(clone);
  
  // Trigger animation
  requestAnimationFrame(() => {
    Object.assign(clone.style, {
      top: (targetRect.top + targetRect.height / 2 - 15) + 'px',
      left: (targetRect.left + targetRect.width / 2 - 15) + 'px',
      width: '30px',
      height: '30px',
      opacity: '0.4',
      transform: 'scale(0.1) rotate(720deg)',
      borderRadius: '50%'
    });
  });
  
  clone.addEventListener('transitionend', () => {
    clone.remove();
    target.classList.add('cart-bounce');
    setTimeout(() => target.classList.remove('cart-bounce'), 400);
  }, { once: true });
};

// ── KPI COUNTER ──
function animateValue(el, from, to, duration = 1400) {
  const isCurrency = el.dataset.format === 'currency';
  const startTime = performance.now();

  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 4); // ease out quart
    const current = from + (to - from) * eased;

    el.textContent = isCurrency
      ? 'PHP ' + current.toLocaleString('en-PH', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
      : Math.round(current).toLocaleString('en-PH');

    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── TOAST MANAGER ──
const ToastManager = {
  container: null,

  init() {
    this.container = document.querySelector('.toast-stack');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-stack';
      this.container.setAttribute('aria-live', 'polite');
      this.container.setAttribute('aria-atomic', 'false');
      document.body.appendChild(this.container);
    }
  },

  show(options) {
    if (!this.container) this.init();
    const { type = 'info', title, message, duration = 5000 } = options;

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', 'status');
    toast.innerHTML = `
      <div class="toast__icon">${this.getIcon(type)}</div>
      <div class="toast__content">
        <div class="toast__title">${title}</div>
        ${message ? `<div class="toast__message">${message}</div>` : ''}
      </div>
      <button class="toast__dismiss" aria-label="Dismiss">✕</button>
      <div class="toast__timer">
        <div class="toast__timer-fill" style="animation-duration: ${duration}ms"></div>
      </div>
    `;

    toast.querySelector('.toast__dismiss').addEventListener('click', () => {
      this.dismiss(toast);
    });

    this.container.appendChild(toast);

    const timer = setTimeout(() => this.dismiss(toast), duration);
    toast.addEventListener('mouseenter', () => clearTimeout(timer));

    return toast;
  },

  dismiss(toast) {
    toast.classList.add('toast--exit');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  },

  success(title, message) { return this.show({ type: 'success', title, message }); },
  error(title, message)   { return this.show({ type: 'danger',  title, message }); },
  warning(title, message) { return this.show({ type: 'warning', title, message }); },
  info(title, message)    { return this.show({ type: 'info',    title, message }); },

  getIcon(type) {
    const icons = {
      success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
      danger:  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info:    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    };
    return icons[type] || icons.info;
  }
};

window.Toast = ToastManager;

// ── MODAL MANAGER ──
const ModalManager = {
  stack: [],
  previousFocus: null,

  open(modalEl) {
    this.previousFocus = document.activeElement;
    this.stack.push(modalEl);

    const overlay = modalEl.closest('.modal-overlay') || modalEl.parentElement;
    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Need slight delay for display: flex to apply before focusing
    setTimeout(() => {
        const firstFocusable = modalEl.querySelector(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        firstFocusable?.focus();
    }, 10);

    overlay.addEventListener('click', (e) => {
      // Check if click was strictly on the overlay, not its children
      if (e.target === overlay) this.close(modalEl);
    });

    this.boundHandleKey = this.handleKey.bind(this);
    document.addEventListener('keydown', this.boundHandleKey);
    modalEl.setAttribute('aria-modal', 'true');
    modalEl.setAttribute('role', 'dialog');
  },

  close(modalEl) {
    const overlay = modalEl.closest('.modal-overlay') || modalEl.parentElement;
    modalEl.style.animation = 'modal-out 200ms ease-in forwards';
    setTimeout(() => {
      overlay.style.display = 'none';
      modalEl.style.animation = '';
      document.body.style.overflow = '';
      this.previousFocus?.focus();
      this.stack.pop();
    }, 200);
    document.removeEventListener('keydown', this.boundHandleKey);
  },

  handleKey(e) {
    if (e.key === 'Escape' && this.stack.length) {
      this.close(this.stack[this.stack.length - 1]);
    }
    if (e.key === 'Tab' && this.stack.length) {
      this.trapFocus(e, this.stack[this.stack.length - 1]);
    }
  },

  trapFocus(e, modalEl) {
    const focusable = [...modalEl.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  }
};
window.ModalManager = ModalManager;

// Bind all close buttons
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.modal__close, .close-btn, [data-dismiss="modal"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            if(modal) ModalManager.close(modal);
        });
    });
});

// ── KEBAB MENU ──
class KebabMenu {
  constructor(trigger) {
    this.trigger = trigger;
    this.menu = trigger.nextElementSibling;
    this.isOpen = false;
    this.bind();
  }

  bind() {
    this.trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.isOpen ? this.close() : this.open();
    });

    this.trigger.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); this.open(); this.focusItem(0); }
      if (e.key === 'Escape')    this.close();
    });

    this.menu?.querySelectorAll('[role="menuitem"]').forEach((item, i) => {
      item.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') { e.preventDefault(); this.focusItem(i + 1); }
        if (e.key === 'ArrowUp')   { e.preventDefault(); this.focusItem(i - 1); }
        if (e.key === 'Escape')    { this.close(); this.trigger.focus(); }
      });
    });

    document.addEventListener('click', () => this.close());
  }

  open() {
    this.menu.style.display = 'block';
    this.trigger.setAttribute('aria-expanded', 'true');
    this.isOpen = true;
  }

  close() {
    this.menu.style.display = 'none';
    this.trigger.setAttribute('aria-expanded', 'false');
    this.isOpen = false;
  }

  focusItem(index) {
    const items = [...this.menu.querySelectorAll('[role="menuitem"]')];
    const target = items[(index + items.length) % items.length];
    target?.focus();
  }
}
window.KebabMenu = KebabMenu;
