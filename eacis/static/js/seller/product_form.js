// Handles product form prefilling and image upload preview
(function(){
  function qs(id){ return document.getElementById(id); }

  function readQuery(){
    const params = new URLSearchParams(window.location.search);
    const context = document.getElementById('seller-product-context');
    return params.get('ref') || (context && context.dataset.productRef) || '';
  }

  function createPreview(file){
    const url = URL.createObjectURL(file);
    const img = document.createElement('img'); img.src = url; img.style.width='96px'; img.style.height='96px'; img.style.objectFit='cover'; img.style.borderRadius='8px';
    const wrapper = document.createElement('div'); wrapper.style.position='relative';
    const btn = document.createElement('button'); btn.type='button'; btn.textContent='✕'; btn.className='btn btn-ghost btn-sm'; btn.style.position='absolute'; btn.style.top='4px'; btn.style.right='4px';
    btn.addEventListener('click', ()=>{ wrapper.remove(); });
    wrapper.appendChild(img); wrapper.appendChild(btn);
    return wrapper;
  }

  document.addEventListener('DOMContentLoaded', ()=>{
    const ref = readQuery();
    const refInput = qs('prd-ref');
    const nameInput = qs('prd-name');
    const previews = qs('image-previews');
    const imageInput = qs('image-input');
    const uploadBtn = qs('image-upload-btn');
    const cancelBtn = qs('cancel-btn');

    // if ref present, prefill with demo values
    if(ref && refInput && nameInput){
      refInput.value = ref;
      nameInput.value = 'Prefilled name for ' + ref;
      const category = qs('prd-category'); if(category) category.value = 'Kitchen & Cooking';
      const price = qs('prd-price'); if(price) price.value = '9999';
      const stock = qs('prd-stock'); if(stock) stock.value = '10';
      const warranty = qs('prd-warranty'); if(warranty) warranty.value = '12';
    } else if (refInput) {
      // new product ref generator
      refInput.value = 'PRD-SLR01-' + String(Math.floor(Math.random()*9000)+1000);
    }

    if (uploadBtn && imageInput) {
      uploadBtn.addEventListener('click', ()=> imageInput.click());
      imageInput.addEventListener('change', (e)=>{
        const files = Array.from(e.target.files || []);
        files.forEach(f=>{ const p = createPreview(f); if (previews) previews.appendChild(p); });
      });
    }

    // drag and drop
    const drop = qs('image-drop');
    if (drop) {
      drop.addEventListener('dragover', (ev)=>{ ev.preventDefault(); drop.classList.add('dragover'); });
      drop.addEventListener('dragleave', ()=>{ drop.classList.remove('dragover'); });
      drop.addEventListener('drop', (ev)=>{
        ev.preventDefault(); drop.classList.remove('dragover');
        const files = Array.from(ev.dataTransfer.files || []).filter(f=>f.type.startsWith('image/'));
        files.forEach(f=>{ const p = createPreview(f); if (previews) previews.appendChild(p); });
      });
    }

    if (cancelBtn) cancelBtn.addEventListener('click', ()=> window.history.back());

    // simple save handler (no backend) — serialize to localStorage demo
    const form = qs('product-form');
    if (!form) return;
    form.addEventListener('submit', (e)=>{
      e.preventDefault();
      const obj = {
        ref: refInput.value, name: nameInput.value, category: qs('prd-category').value,
        price: parseFloat(qs('prd-price').value||0), stock: parseInt(qs('prd-stock').value||0,10), warranty: parseInt(qs('prd-warranty').value||0,10)
      };
      const saved = JSON.parse(localStorage.getItem('eacis_seller_products')||'[]');
      saved.unshift(obj);
      localStorage.setItem('eacis_seller_products', JSON.stringify(saved));
      alert('Saved (demo) — product serialized to localStorage');
      window.location.href = '/seller/products';
    });
  });
})();
