// Enhance data tables: sortable headers and accessible pagination
(function(){
  function ensureAnnouncer(){
    let a = document.getElementById('eacis-announce');
    if(!a){ a = document.createElement('div'); a.id='eacis-announce'; a.setAttribute('aria-live','polite'); a.setAttribute('aria-atomic','true'); a.style.position='absolute'; a.style.left='-9999px'; a.style.width='1px'; a.style.height='1px'; a.style.overflow='hidden'; document.body.appendChild(a); }
    return a;
  }

  function announce(msg){ const a = ensureAnnouncer(); a.textContent = msg; }

  function initSortable(table){
    table.querySelectorAll('th.sortable').forEach(th => {
      th.setAttribute('tabindex', '0');
      if(!th.hasAttribute('role')) th.setAttribute('role','button');
      if(!th.hasAttribute('aria-sort')) th.setAttribute('aria-sort','none');
      th.addEventListener('click', ()=> toggleSort(th, table));
      th.addEventListener('keydown', (e)=>{ if(e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSort(th, table); } });
    });
  }

  function toggleSort(th, table){
    const current = th.getAttribute('aria-sort') || 'none';
    const next = current === 'none' ? 'asc' : current === 'asc' ? 'desc' : 'none';
    // reset others
    table.querySelectorAll('th.sortable').forEach(h=>{ if(h !== th) h.setAttribute('aria-sort','none'); });
    th.setAttribute('aria-sort', next);
    // announce
    if(next === 'none') announce(`Removed sorting on ${th.textContent.trim()}`);
    else announce(`Sorted ${th.textContent.trim()} ${next === 'asc' ? 'ascending' : 'descending'}`);
    // TODO: implement actual sort of rows if desired; for now visual affordance only
  }

  function initPagination(){
    document.querySelectorAll('.pagination .pill').forEach(p => {
      p.setAttribute('role','button');
      p.setAttribute('tabindex','0');
      p.addEventListener('keydown', (e)=>{ if(e.key === 'Enter' || e.key === ' ') { e.preventDefault(); p.click(); } });
    });
  }

  function init(){
    document.querySelectorAll('.data-table').forEach(initSortable);
    initPagination();
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
