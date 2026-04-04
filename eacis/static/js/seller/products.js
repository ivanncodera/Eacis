// Seller products table population (placeholder)
(function(){
  const sample = [
    {ref:'PRD-SLR01-0001',name:'Two-Door Refrigerator',price:18000,stock:12,warranty:12,installment:true,active:true},
    {ref:'PRD-SLR01-0004',name:'Gas Range with Oven',price:14500,stock:6,warranty:12,installment:true,active:true}
  ];

  function renderTable(list){
    const tbody = document.getElementById('seller-products-tbody');
    if(!tbody) return;
    tbody.innerHTML = '';
    list.forEach(p=>{
      const tr = document.createElement('tr');
      tr.dataset.ref = p.ref;
      tr.className = p.active ? '' : 'muted';
      tr.innerHTML = `
        <td><input type="checkbox" aria-label="Select ${p.ref}"></td>
        <td class="ref-code">${p.ref}</td>
        <td>${p.name}</td>
        <td>PHP ${p.price.toLocaleString()}</td>
        <td>${p.stock}</td>
        <td>${p.warranty}m</td>
        <td>${p.installment? 'Yes':'No'}</td>
        <td>
          <button class="btn btn-ghost btn-sm edit" data-ref="${p.ref}" aria-label="Edit ${p.ref}">Edit</button>
          <button class="btn btn-ghost btn-sm duplicate" data-ref="${p.ref}" aria-label="Duplicate ${p.ref}">Duplicate</button>
          <button class="btn btn-ghost btn-sm deactivate" data-ref="${p.ref}" aria-label="Deactivate ${p.ref}">${p.active? 'Deactivate':'Activate'}</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  // in-memory list combining saved products from localStorage + sample data
  function loadSaved(){
    try{
      const raw = localStorage.getItem('eacis_seller_products');
      if(!raw) return [];
      const parsed = JSON.parse(raw);
      if(!Array.isArray(parsed)) return [];
      return parsed.map(p=> Object.assign({active:true}, p));
    }catch(e){ return []; }
  }

  let products = (function(){
    const saved = loadSaved();
    // merge by ref (saved overrides sample)
    const map = new Map();
    sample.forEach(s=> map.set(s.ref, Object.assign({}, s)));
    saved.forEach(s=> map.set(s.ref, Object.assign({}, s)));
    // ensure array order: saved first, then remaining sample
    const ordered = [];
    saved.forEach(s=> ordered.push(map.get(s.ref)));
    sample.forEach(s=>{ if(!saved.find(x=>x.ref===s.ref)) ordered.push(map.get(s.ref)); });
    return ordered;
  })();

  function findByRef(ref){ return products.find(p=>p.ref===ref); }

  document.addEventListener('DOMContentLoaded', ()=>{
    renderTable(products);

    // helper: confirm modal
    function confirmDialog(title, message, confirmLabel, onConfirm){
      const node = document.createElement('div');
      node.innerHTML = `<h3 style="margin:0">${title}</h3><p style="margin-top:8px;color:var(--muted)">${message}</p><div style="display:flex;justify-content:flex-end;gap:8px;margin-top:14px;"><button id="c-cancel" class="btn btn-ghost">Cancel</button><button id="c-confirm" class="btn btn-primary">${confirmLabel}</button></div>`;
      const modal = Modal.open(node);
      node.querySelector('#c-cancel').addEventListener('click', ()=> modal.close());
      node.querySelector('#c-confirm').addEventListener('click', ()=>{ onConfirm(); modal.close(); });
    }

    // event delegation for actions
    document.getElementById('seller-products-tbody').addEventListener('click', (e)=>{
      const btn = e.target.closest('button'); if(!btn) return;
      const tr = btn.closest('tr'); const ref = btn.dataset.ref || tr && tr.dataset.ref;
      if(btn.classList.contains('edit')){
        // navigate to form with ref query
        window.location.href = `/seller/product/create?ref=${encodeURIComponent(ref)}`;
      } else if(btn.classList.contains('duplicate')){
        const original = findByRef(ref); if(!original) return;
        confirmDialog('Duplicate product', `Create a copy of ${original.ref}? This will create an inactive draft.`, 'Create Copy', ()=>{
          const copy = Object.assign({}, original);
          const suffix = '-COPY'+String(Math.floor(Math.random()*9000)+1000);
          copy.ref = original.ref + suffix;
          copy.active = false;
          products.unshift(copy);
          renderTable(products);
          Toast.show(`Created copy ${copy.ref}`, 'success');
        });
      } else if(btn.classList.contains('deactivate')){
        const p = findByRef(ref); if(!p) return;
        const will = p.active ? 'deactivate' : 'activate';
        confirmDialog(`${will[0].toUpperCase()+will.slice(1)} product`, `Are you sure you want to ${will} ${p.ref}?`, will[0].toUpperCase()+will.slice(1), ()=>{
          p.active = !p.active;
          renderTable(products);
          Toast.show(`${p.ref} ${p.active? 'activated':'deactivated'}`, 'info');
        });
      }
    });

    // create product button
    const createBtn = document.getElementById('create-product');
    if(createBtn) createBtn.addEventListener('click', ()=> window.location.href='/seller/product/create');

    // search
    const search = document.getElementById('seller-search');
    if(search){
      search.addEventListener('input', ()=>{
        const q = search.value.trim().toLowerCase();
        if(!q) renderTable(products);
        else renderTable(products.filter(p=> p.name.toLowerCase().includes(q) || p.ref.toLowerCase().includes(q)));
      });
    }
  });
})();
