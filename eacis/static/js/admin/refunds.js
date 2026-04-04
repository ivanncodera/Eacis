// Admin refunds interactivity: view, approve, decline, CSV export, toasts
(() => {
  const createToastContainer = () => {
    let c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      c.style.position = 'fixed';
      c.style.top = '72px';
      c.style.right = '20px';
      c.style.zIndex = 9999;
      document.body.appendChild(c);
    }
    return c;
  };

  const showToast = (message, type = 'info', timeout = 5000) => {
    const container = createToastContainer();
    const t = document.createElement('div');
    t.className = `admin-toast admin-toast--${type}`;
    t.style.minWidth = '280px';
    t.style.marginBottom = '8px';
    t.style.padding = '12px 14px';
    t.style.borderRadius = '12px';
    t.style.boxShadow = '0 8px 24px rgba(0,0,0,0.12)';
    t.style.background = 'rgba(255,255,255,0.82)';
    t.style.backdropFilter = 'blur(6px)';
    t.textContent = message;
    container.appendChild(t);

    let dismissed = false;
    const remove = () => { if (!dismissed) { dismissed = true; t.remove(); }};
    const id = setTimeout(remove, timeout);
    t.addEventListener('mouseenter', ()=> clearTimeout(id));
    t.addEventListener('mouseleave', ()=> setTimeout(remove, 1500));
    t.addEventListener('click', remove);
  };

  const downloadCSV = (rows, filename = 'refunds.csv') => {
    const cols = Object.keys(rows[0] || {});
    const csv = [cols.join(',')].concat(rows.map(r => cols.map(c => `"${String(r[c]||'').replace(/"/g,'""')}"`).join(','))).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const buildModal = ({ title = 'Modal', body = '', footer = '' } = {}) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.style.position = 'fixed';
    overlay.style.inset = 0;
    overlay.style.background = 'rgba(0,0,0,0.4)';
    overlay.style.display = 'flex';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';
    overlay.style.zIndex = 10000;

    const dialog = document.createElement('div');
    dialog.className = 'modal-dialog glass-card';
    dialog.style.maxWidth = '920px';
    dialog.style.width = 'min(96%,920px)';
    dialog.style.padding = '18px';

    const h = document.createElement('div');
    h.innerHTML = `<h3 id="modal-title">${title}</h3>`;
    const b = document.createElement('div');
    b.className = 'modal-body';
    if (typeof body === 'string') b.innerHTML = body; else b.appendChild(body);
    const f = document.createElement('div');
    f.className = 'modal-footer';
    if (typeof footer === 'string') f.innerHTML = footer; else if (footer) f.appendChild(footer);

    dialog.appendChild(h);
    dialog.appendChild(b);
    dialog.appendChild(f);
    overlay.appendChild(dialog);

    overlay.addEventListener('click', (ev) => { if (ev.target === overlay) overlay.remove(); });
    document.addEventListener('keyup', function esc(e){ if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keyup', esc); }});
    document.body.appendChild(overlay);
    return overlay;
  };

  const parseTableRows = (table) => {
    const rows = [];
    table.querySelectorAll('tbody tr').forEach(tr => {
      const obj = {};
      tr.querySelectorAll('td[data-key]').forEach(td => obj[td.dataset.key] = td.textContent.trim());
      obj._status = tr.dataset.status || '';
      obj._ref = tr.dataset.ref || '';
      rows.push(obj);
    });
    return rows;
  };

  const init = () => {
    const table = document.getElementById('refunds-table');
    if (!table) return;

    // Export CSV button
    const exportBtn = document.getElementById('export-refunds-csv');
    if (exportBtn) exportBtn.addEventListener('click', ()=>{
      const rows = parseTableRows(table);
      if (rows.length === 0) { showToast('No refunds to export', 'warning'); return; }
      downloadCSV(rows, 'refunds_export.csv');
      showToast('CSV export started', 'info');
    });

    // Row action handlers
    table.querySelectorAll('tbody tr').forEach(tr => {
      const ref = tr.dataset.ref;
      tr.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const action = btn.dataset.action;
          if (action === 'view') {
            const evidence = tr.dataset.evidence || '';
            const body = document.createElement('div');
            body.innerHTML = `
              <p><strong>Refund:</strong> <span class="ref-code">${ref}</span></p>
              <p><strong>Status:</strong> ${tr.dataset.status}</p>
              <p><strong>Customer:</strong> ${tr.querySelector('[data-key="customer"]')?.textContent || ''}</p>
              <p><strong>Amount:</strong> ${tr.querySelector('[data-key="amount"]')?.textContent || ''}</p>
              <div style="margin-top:12px;">${evidence ? `<img src="${evidence}" style="max-width:220px;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.12)"/>` : '<em>No evidence attached</em>'}</div>
            `;
            buildModal({ title: `Refund ${ref}`, body });
          }

          if (action === 'decline' || action === 'approve') {
            const isApprove = action === 'approve';
            const input = document.createElement('input');
            input.placeholder = 'Type REFUND to confirm';
            input.style.width = '100%';
            input.style.margin = '8px 0 12px';
            const approveBtn = document.createElement('button');
            approveBtn.textContent = isApprove ? 'Approve Refund' : 'Decline Refund';
            approveBtn.disabled = true;
            approveBtn.className = isApprove ? 'btn btn--danger' : 'btn btn--muted';
            const footer = document.createElement('div');
            footer.style.display = 'flex';
            footer.style.gap = '8px';
            footer.appendChild(approveBtn);
            const modal = buildModal({ title: `${isApprove ? 'Approve' : 'Decline'} refund ${ref}`, body: input, footer });

            input.addEventListener('input', ()=>{ approveBtn.disabled = input.value.trim() !== 'REFUND'; });
            approveBtn.addEventListener('click', ()=>{
              // update UI state
              tr.dataset.status = isApprove ? 'approved' : 'declined';
              const badge = tr.querySelector('.status-badge');
              if (badge) { badge.textContent = isApprove ? 'approved' : 'declined'; badge.className = `status-badge status-badge--${isApprove ? 'success' : 'danger'}`; }
              showToast(isApprove ? `Refund ${ref} approved` : `Refund ${ref} declined`, isApprove ? 'success' : 'error');
              modal.remove();
            });
          }
        });
      });
    });
  };

  document.addEventListener('DOMContentLoaded', init);
})();
