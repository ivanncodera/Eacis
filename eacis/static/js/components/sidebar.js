// Sidebar: collapse/expand, active item highlight, keyboard toggle
(function(){
  const initSidebar = () => {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    // accessibility
    sidebar.setAttribute('role','navigation');
    sidebar.setAttribute('aria-label','Main sidebar');
    const toggle = sidebar.querySelector('[data-sidebar-toggle]');
    const collapsePref = 'eacis_sidebar_collapsed';
    // If this sidebar is a guest placeholder, skip interactive behavior
    if (sidebar.dataset.guest === 'true' || sidebar.hasAttribute('data-guest')) {
      // expose aria attributes for a11y checks but do not bind interactions
      if (toggle) {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-hidden', 'true');
        toggle.disabled = true;
      }
      return;
    }
    const applyState = (collapsed) => {
      if (collapsed) document.documentElement.classList.add('sidebar-collapsed');
      else document.documentElement.classList.remove('sidebar-collapsed');
      if (toggle) toggle.setAttribute('aria-expanded', collapsed ? 'true' : 'false');
    };
    // restore
    applyState(localStorage.getItem(collapsePref) === '1');

    if (toggle) {
      toggle.setAttribute('role','button');
      toggle.setAttribute('aria-label','Collapse sidebar');
      toggle.setAttribute('aria-expanded', localStorage.getItem(collapsePref) === '1' ? 'true' : 'false');
      toggle.addEventListener('click', ()=>{
        const collapsed = !document.documentElement.classList.contains('sidebar-collapsed');
        applyState(collapsed);
        localStorage.setItem(collapsePref, collapsed? '1':'0');
      });
    }

    // keyboard: Ctrl+B toggles
    document.addEventListener('keydown', (e)=>{ if (e.ctrlKey && e.key.toLowerCase()==='b') { e.preventDefault(); toggle && toggle.click(); }});

    // Keyboard navigation within sidebar (ArrowUp/ArrowDown)
    const items = Array.from(sidebar.querySelectorAll('a,button')).filter(el=>el.tabIndex!==-1);
    items.forEach(it => { it.tabIndex = 0; it.setAttribute('role', it.tagName.toLowerCase()==='a' ? 'link' : 'button'); });
    sidebar.addEventListener('keydown', (ev)=>{
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        const active = document.activeElement;
        const idx = items.indexOf(active);
        if (idx === -1) return;
        const next = ev.key === 'ArrowDown' ? items[(idx+1)%items.length] : items[(idx-1+items.length)%items.length];
        next && next.focus();
      }
    });
  };
  document.addEventListener('DOMContentLoaded', initSidebar);
})();
// Sidebar collapse toggle
(function(){
  function toggle(){ const s = document.querySelector('.sidebar'); if(!s) return; s.classList.toggle('collapsed'); document.querySelector('.content-area').style.marginLeft = s.classList.contains('collapsed') ? '72px' : '240px'; }
  document.addEventListener('click', (e)=>{ if(e.target && e.target.matches && e.target.matches('.sidebar-toggle')) toggle(); });
  window.Sidebar = { toggle };
})();
