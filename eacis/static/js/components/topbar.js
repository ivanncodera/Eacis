// Topbar: search toggle, cart badge update, mobile hamburger
(function(){
  const initTopbar = () => {
    const search = document.querySelector('.topbar .topbar-search');
    const searchToggle = document.querySelector('[data-topbar-search-toggle]');
    if (search) {
      search.setAttribute('role','search');
    }
    if (search && searchToggle) {
      searchToggle.setAttribute('role','button');
      searchToggle.setAttribute('aria-label','Toggle search');
      searchToggle.setAttribute('aria-expanded','false');
      searchToggle.addEventListener('click', (e)=>{
        e.preventDefault();
        const active = search.classList.toggle('active');
        searchToggle.setAttribute('aria-expanded', active ? 'true' : 'false');
        const input = search.querySelector('input'); if (input) input.focus();
      });

      // close search on Escape and restore focus
      search.addEventListener('keydown', (ev)=>{
        if (ev.key === 'Escape') { search.classList.remove('active'); searchToggle.setAttribute('aria-expanded','false'); searchToggle.focus(); }
      });

      // keyboard shortcut: '/' focuses search when not typing
      document.addEventListener('keydown', (ev)=>{
        const tag = document.activeElement && document.activeElement.tagName;
        if (ev.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') {
          ev.preventDefault(); const input = search.querySelector('input'); if (input) { search.classList.add('active'); searchToggle.setAttribute('aria-expanded','true'); input.focus(); }
        }
      });
    }

    // Topnav mobile toggle
    const nav = document.getElementById('main-nav');
    const navToggle = document.querySelector('[data-topnav-toggle]');
    if (nav && navToggle) {
      navToggle.addEventListener('click', (e)=>{
        e.preventDefault();
        const isOpen = nav.classList.toggle('topnav--open');
        navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });

      // close on Escape
      document.addEventListener('keydown', (ev)=>{ if (ev.key === 'Escape') { nav.classList.remove('topnav--open'); navToggle.setAttribute('aria-expanded','false'); } });
      // click outside closes
      document.addEventListener('click', (ev)=>{ if (!nav.contains(ev.target) && !navToggle.contains(ev.target)) { nav.classList.remove('topnav--open'); navToggle.setAttribute('aria-expanded','false'); } });
    }

    // Cart count update (reads from localStorage key eacis_cart)
    const cartBadge = document.querySelector('.topbar .cart-badge');
    const updateCartBadge = () => {
      try {
        const cart = JSON.parse(localStorage.getItem('eacis_cart')||'[]');
        const count = Array.isArray(cart) ? cart.reduce((s,i)=>s + (i.qty||1),0) : 0;
        if (cartBadge) { cartBadge.textContent = count; cartBadge.style.display = count>0?'inline-block':'none'; }
      } catch(e){ if (cartBadge) cartBadge.style.display='none'; }
    };
    updateCartBadge();
    window.addEventListener('storage', updateCartBadge);

    // Mobile hamburger
    const hamb = document.querySelector('.topbar [data-topbar-hamb]');
    if (hamb) {
      hamb.setAttribute('role','button');
      hamb.setAttribute('aria-label','Toggle sidebar');
      hamb.setAttribute('aria-expanded', document.documentElement.classList.contains('sidebar-open') ? 'true' : 'false');
      hamb.addEventListener('click', ()=>{
        // no-op if sidebar is guest-hidden
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && (sidebar.dataset.guest === 'true' || sidebar.hasAttribute('data-guest'))) return;
        const open = document.documentElement.classList.toggle('sidebar-open');
        hamb.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }
  };
  document.addEventListener('DOMContentLoaded', initTopbar);
})();
// Topbar behaviors: optional search focus + mobile hamburger (basic)
document.addEventListener('click', (e)=>{
  const t = e.target;
  if(t && t.matches && t.matches('.topbar .icon-btn[aria-label="Search"]')){
    const input = document.querySelector('.topbar .search input[type=search]'); if(input) input.focus();
  }
});

window.Topbar = { focusSearch: ()=>{ const input = document.querySelector('.topbar .search input[type=search]'); if(input) input.focus(); } };
