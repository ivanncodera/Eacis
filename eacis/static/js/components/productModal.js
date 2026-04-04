// Quickview modal API
(function(){
  function buildQuickviewContent(product){
    const wrapper = document.createElement('div');
    wrapper.className = 'product-quickview grid-2';

    const media = document.createElement('div'); media.className = 'pq-media';
    const img = document.createElement('img'); img.src = product.image; img.alt = product.name; img.loading = 'lazy'; media.appendChild(img);

    const body = document.createElement('div'); body.className = 'pq-body';
    const ref = document.createElement('div'); ref.className = 'ref-code'; ref.textContent = product.ref;
    const title = document.createElement('h3'); title.textContent = product.name;
    const meta = document.createElement('div'); meta.className = 'pq-meta'; meta.textContent = `${product.category} • ${product.reviews} reviews`;
    const price = document.createElement('div'); price.className = 'pq-price'; price.textContent = `PHP ${Number(product.price).toLocaleString('en-PH',{minimumFractionDigits:2})}`;

    const actions = document.createElement('div'); actions.className = 'pq-actions';
    const addBtn = document.createElement('button'); addBtn.className = 'btn btn-primary'; addBtn.textContent = 'Add to cart';
    addBtn.dataset.ref = product.ref;
    const viewBtn = document.createElement('a'); viewBtn.className = 'btn btn-ghost'; viewBtn.href = `/products/${product.ref}`; viewBtn.textContent = 'View details';
    actions.appendChild(addBtn); actions.appendChild(viewBtn);

    body.appendChild(ref); body.appendChild(title); body.appendChild(meta); body.appendChild(price); body.appendChild(actions);
    wrapper.appendChild(media); wrapper.appendChild(body);
    return { node: wrapper, addBtn, viewBtn };
  }

  function openProductModal(product){
    if(!product) return null;
    const built = buildQuickviewContent(product);
    const m = Modal.open(built.node);
    // wire add to cart
    try{
      built.addBtn.addEventListener('click', ()=>{
        if(window.eacis && typeof window.eacis.addToCart === 'function') window.eacis.addToCart(product.ref, 1);
        if(m && typeof m.close === 'function') m.close();
        if(window.Toast && typeof window.Toast.show === 'function') window.Toast.show('Added to cart','success');
      });
    }catch(e){ console.error(e); }
    return m;
  }

  // expose helper
  window.openProductModal = openProductModal;
})();
