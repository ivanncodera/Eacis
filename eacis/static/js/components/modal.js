// Modal manager: attach to #modal-root, create overlay, trap focus, handle open/close
(function(){
  const Modal = {
    root: null,
    overlay: null,
    activeModal: null,
    lastFocused: null,

    init() {
      this.root = document.getElementById('modal-root');
      if (!this.root) {
        this.root = document.createElement('div');
        this.root.id = 'modal-root';
        this.root.style.display = 'none';
        document.body.appendChild(this.root);
      }
      // create overlay container if not present
      if (!this.root.classList.contains('modal-root')) this.root.classList.add('modal-root');
    },

    open(content, opts = {}) {
      this.init();
      this.close();
      this.lastFocused = document.activeElement;

      // build overlay
      this.overlay = document.createElement('div');
      this.overlay.className = 'modal-overlay';
      this.overlay.tabIndex = -1;

      // build modal panel
      const panel = document.createElement('div');
      panel.className = 'modal modal--md';
      panel.setAttribute('role','dialog');
      panel.setAttribute('aria-modal','true');
      panel.innerHTML = typeof content === 'string' ? content : '';
      if (content instanceof Node) panel.appendChild(content);

      // close button if not present
      if (!panel.querySelector('[data-modal-close]')) {
        const closeBtn = document.createElement('button');
        closeBtn.className = 'modal__close';
        closeBtn.setAttribute('aria-label','Close');
        closeBtn.innerHTML = '&#10005;';
        closeBtn.dataset.modalClose = 'true';
        closeBtn.addEventListener('click', ()=> this.close());
        panel.insertBefore(closeBtn, panel.firstChild);
      }

      this.overlay.appendChild(panel);
      this.root.appendChild(this.overlay);
      this.root.style.display = 'flex';
      document.body.style.overflow = 'hidden';
      // Hide main content from assistive technologies while modal is open
      const main = document.getElementById('main');
      if (main) main.setAttribute('aria-hidden', 'true');
      this.activeModal = panel;

      // click outside to close
      this.overlay.addEventListener('click', (e)=>{ if (e.target === this.overlay) this.close(); });

      // focus management
      const focusable = this._focusable(panel);
      (focusable[0] || panel).focus();

      // key handlers
      this._keydown = (e)=>{
        if (e.key === 'Escape') this.close();
        if (e.key === 'Tab') this._trap(e, panel);
      };
      document.addEventListener('keydown', this._keydown);
      return panel;
    },

    close() {
      if (!this.root) return;
      if (this.overlay && this.root.contains(this.overlay)) {
        this.overlay.remove();
      }
      this.overlay = null;
      this.activeModal = null;
      this.root.style.display = 'none';
      document.body.style.overflow = '';
      // Restore main content accessibility
      const main = document.getElementById('main');
      if (main) main.removeAttribute('aria-hidden');
      document.removeEventListener('keydown', this._keydown);
      try { this.lastFocused && this.lastFocused.focus(); } catch(e){}
    },

    _focusable(container){
      return Array.from(container.querySelectorAll('a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'))
        .filter(el => el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    },

    _trap(e, panel){
      const nodes = this._focusable(panel);
      if (!nodes.length) { e.preventDefault(); return; }
      const first = nodes[0];
      const last = nodes[nodes.length-1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };

  // expose API
  window.Modal = Modal;

  // auto-init: delegate data-modal-open attributes
  document.addEventListener('click', (e)=>{
    const t = e.target.closest('[data-modal-open]');
    if (!t) return;
    e.preventDefault();
    const selector = t.dataset.modalTarget;
    if (selector) {
      const content = document.querySelector(selector);
      if (content) {
        Modal.open(content.cloneNode(true));
        return;
      }
    }
    // fallback: open inline HTML from data-modal-content
    const html = t.dataset.modalContent;
    if (html) Modal.open(html);
  });

})();
// Accessible modal manager: open/close, overlay, Esc to close, focus trap
const Modal = (function(){
  function createOverlay(){
    const ov = document.createElement('div'); ov.className='modal-overlay'; ov.tabIndex = -1; return ov;
  }

  function focusableElements(container){
    return Array.from(container.querySelectorAll('a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'))
      .filter(el=> !el.hasAttribute('disabled'));
  }

  function open(nodeOrHtml, opts={}){
    const overlay = createOverlay();
    const modal = document.createElement('div'); modal.className='modal';
    modal.setAttribute('role','dialog');
    modal.setAttribute('aria-modal','true');
    if(typeof nodeOrHtml === 'string') modal.innerHTML = nodeOrHtml; else modal.appendChild(nodeOrHtml);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const previouslyFocused = document.activeElement;
    const focusables = focusableElements(modal);
    if(focusables.length) focusables[0].focus(); else modal.focus();

    function close(){
      if(overlay.parentNode) overlay.parentNode.removeChild(overlay);
      document.removeEventListener('keydown', onKey);
      // restore accessibility on main
      const main = document.getElementById('main');
      if (main) main.removeAttribute('aria-hidden');
      previouslyFocused && previouslyFocused.focus();
    }

    function onKey(e){
      if(e.key === 'Escape') { e.preventDefault(); close(); }
      if(e.key === 'Tab'){
        const elems = focusableElements(modal);
        if(elems.length === 0) { e.preventDefault(); return; }
        const first = elems[0], last = elems[elems.length -1];
        if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
        else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
      }
    }

    overlay.addEventListener('click', (e)=>{ if(e.target === overlay) close(); });
    document.addEventListener('keydown', onKey);
    return { close };
  }

  return { open };
})();

window.Modal = Modal;
