// Admin audit helper: reveal IP toggles and expand JSON details
(function(){
  const init = () => {
    const table = document.getElementById('audit-table'); if(!table) return;
    table.querySelectorAll('[data-action="reveal-ip"]').forEach(btn => btn.addEventListener('click', (e)=>{
      const tr = btn.closest('tr'); if(!tr) return;
      const ipCell = tr.querySelector('[data-key="ip"]'); if(!ipCell) return;
      e.preventDefault();
      const prompt = 'Reveal full IP for this row?';
      const run = () => {
        ipCell.textContent = ipCell.dataset.full || ipCell.textContent;
        btn.remove();
        window.EACIS && window.EACIS.showToast ? window.EACIS.showToast('IP revealed','info') : null;
      };
      if (window.confirmModal) { confirmModal(prompt).then(ok => { if (!ok) return; run(); }); } else { if (!confirm(prompt)) return; run(); }
    }));

    table.querySelectorAll('[data-action="expand"]').forEach(btn=> btn.addEventListener('click', ()=>{
      const tr = btn.closest('tr'); if(!tr) return;
      const details = tr.querySelector('.meta-json'); if(!details) return;
      details.style.display = details.style.display === 'block' ? 'none' : 'block';
    }));
  };
  document.addEventListener('DOMContentLoaded', init);
})();
