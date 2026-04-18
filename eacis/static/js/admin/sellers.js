// Admin sellers interactivity: approve/reject onboarding, quick search, CSV export
(function(){
  const init = () => {
    const table = document.getElementById('sellers-table');
    if (!table) return;
    const exportBtn = document.getElementById('export-sellers-csv');
    if (exportBtn) exportBtn.addEventListener('click', ()=>{
      const rows = [];
      table.querySelectorAll('tbody tr').forEach(tr=>{
        const r = {};
        tr.querySelectorAll('td[data-key]').forEach(td=>r[td.dataset.key]=td.textContent.trim());
        rows.push(r);
      });
      if (rows.length) {
        const cols = Object.keys(rows[0]);
        const csv = [cols.join(',')].concat(rows.map(r => cols.map(c => '"'+String(r[c]||'').replace(/"/g,'""')+'"').join(','))).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'sellers.csv'; document.body.appendChild(a); a.click(); a.remove();
      }
    });

    table.querySelectorAll('[data-action]').forEach(btn=> btn.addEventListener('click', (e)=>{
      const tr = btn.closest('tr');
      const action = btn.dataset.action;
      const ref = tr && tr.dataset.ref;
      if (action === 'approve' || action === 'reject') {
        e.preventDefault();
        const prompt = `${action.toUpperCase()} seller ${ref}?`;
        const run = () => {
          tr.dataset.status = action === 'approve' ? 'active' : 'rejected';
          const badge = tr.querySelector('.status-badge'); if (badge) badge.textContent = action === 'approve' ? 'active' : 'rejected';
          const msg = action === 'approve' ? `Seller ${ref} approved` : `Seller ${ref} rejected`;
          window.EACIS && window.EACIS.showToast ? window.EACIS.showToast(msg,'info') : alert(msg);
        };
        if (window.confirmModal) { confirmModal(prompt).then(ok => { if (!ok) return; run(); }); } else { if (!confirm(prompt)) return; run(); }
      }
    }))
  };
  document.addEventListener('DOMContentLoaded', init);
})();
