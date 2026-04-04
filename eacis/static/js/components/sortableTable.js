// Sortable table helper
(function(){
  function parseCell(value){
    if(!value) return '';
    // try number
    const n = value.replace(/[^0-9\.\-]/g,'');
    if(n !== '' && !isNaN(Number(n))) return Number(n);
    // try date
    const d = Date.parse(value);
    if(!isNaN(d)) return d;
    return value.toString().toLowerCase();
  }

  function sortTable(table, colIndex, direction){
    const tbody = table.tBodies[0]; if(!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const getKey = (tr)=>{
      const cell = tr.children[colIndex];
      return parseCell(cell && (cell.dataset.sortValue || cell.textContent.trim()));
    };
    rows.sort((a,b)=>{
      const A = getKey(a), B = getKey(b);
      if(A === B) return 0;
      if(A === null || A === undefined) return 1;
      if(B === null || B === undefined) return -1;
      if(typeof A === 'number' && typeof B === 'number') return direction === 'asc' ? A - B : B - A;
      if(typeof A === 'number' !== typeof B === 'number') return typeof A === 'number' ? -1 : 1;
      // fallback string compare
      return direction === 'asc' ? (A > B ? 1 : -1) : (A < B ? 1 : -1);
    });
    // re-attach
    rows.forEach(r=> tbody.appendChild(r));
  }

  function init(table){
    if(!table) return;
    const headers = Array.from(table.querySelectorAll('th'));
    headers.forEach((th, idx)=>{
      if(!th.dataset.sort) return;
      th.tabIndex = 0;
      th.setAttribute('role','button');
      th.setAttribute('aria-sort','none');
      th.classList.add('sortable');
      const toggle = ()=>{
        const cur = th.getAttribute('aria-sort');
        const next = cur === 'asc' ? 'desc' : 'asc';
        // reset others
        headers.forEach(h=> h.setAttribute('aria-sort','none'));
        th.setAttribute('aria-sort', next);
        sortTable(table, idx, next);
      };
      th.addEventListener('click', toggle);
      th.addEventListener('keydown', (e)=>{ if(e.key==='Enter' || e.key===' ') { e.preventDefault(); toggle(); } });
    });
  }

  document.addEventListener('DOMContentLoaded', ()=>{
    document.querySelectorAll('table.data-table').forEach(t=> init(t));
  });

  window.SortableTable = { init };
})();
