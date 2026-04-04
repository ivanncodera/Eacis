// Customer interactions: product detail, cart, checkout, orders, returns, loyalty, profile
(function(){
  const qs = id => document.getElementById(id);
  const qsa = sel => document.querySelectorAll(sel);
  
  // Use user-specific keys if authenticated
  const userId = (window.EACIS && window.EACIS.user_id) || 'guest';
  const CART_KEY = `eacis_cart_${userId}`;
  const ORDERS_KEY = `eacis_orders_${userId}`;
  const PROFILE_KEY = `eacis_profile_${userId}`;
  const LOYALTY_KEY = `eacis_loyalty_${userId}`;

  function loadProducts(){ return window.PRODUCTS || []; }
  function findProduct(ref){ return loadProducts().find(p=>p.ref===ref); }

  /* CART helpers */
  function loadCart(){ try{ return JSON.parse(localStorage.getItem(CART_KEY)||'[]'); }catch(e){return[]} }
  function saveCart(c){ 
    localStorage.setItem(CART_KEY, JSON.stringify(c));
    updateCartBadges(c);
    renderMiniCart(c);
  }
  
  function updateCartBadges(cart){
    if(!cart) cart = loadCart();
    const count = cart.reduce((s, i) => s + i.qty, 0);
    const badges = qsa('.topbar__cart-badge, .bottom-nav__badge');
    badges.forEach(b => {
      b.textContent = count;
      b.classList.add('pop');
      setTimeout(() => b.classList.remove('pop'), 400);
    });
  }

  function addToCart(ref, qty){ 
    const cart = loadCart(); 
    const item = cart.find(i=>i.ref===ref); 
    if(item) item.qty += qty; 
    else cart.push({ref,qty}); 
    saveCart(cart); 
    if(window.Toast) window.Toast.success('Added to cart', `${qty} item(s) added.`); 
  }

  /* MINI CART (Dropdown) */
  function renderMiniCart(cart){
    const container = qs('mini-cart-items');
    const subtotalEl = qs('mini-cart-subtotal');
    if(!container) return;
    
    if(!cart || cart.length === 0){
      container.innerHTML = `
        <div style="padding: var(--sp-12) 0; text-align: center; color: var(--grey-400);">
          <svg width="32" height="32" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24" style="margin-bottom:var(--sp-2); opacity:0.2;"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>
          <div class="type-body-sm">Your cart is empty</div>
        </div>
      `;
      if(subtotalEl) subtotalEl.textContent = 'PHP 0.00';
      return;
    }

    let subtotal = 0;
    container.innerHTML = cart.map(item => {
      const p = findProduct(item.ref) || { name: item.ref, price: 0, image: '/static/assets/placeholders/placeholder.png' };
      subtotal += (p.price || 0) * item.qty;
      return `
        <div class="mini-cart-item">
          <img src="${p.image || '/static/assets/placeholders/placeholder.png'}" alt="${p.name}">
          <div class="mini-cart-info">
            <span class="mini-cart-name">${p.name}</span>
            <span class="mini-cart-meta">${item.qty} × PHP ${(p.price || 0).toLocaleString()}</span>
          </div>
          <div class="mini-cart-price">PHP ${((p.price || 0) * item.qty).toLocaleString()}</div>
        </div>
      `;
    }).join('');
    
    if(subtotalEl) subtotalEl.textContent = 'PHP ' + subtotal.toLocaleString();
  }

  /* PRODUCT DETAIL */
  function initProductDetail(){
    const el = qs('pd-name'); if(!el) return;
    const params = new URLSearchParams(window.location.search); const ref = params.get('ref');
    const p = findProduct(ref); if(!p) return;
    qs('pd-name').textContent = p.name; qs('pd-ref').textContent = p.ref; qs('pd-price').textContent = 'PHP '+p.price.toLocaleString();
    qs('pd-desc').textContent = p.description || p.name + ' — details.'; qs('pd-stock').textContent = p.stock>0? 'In Stock ('+p.stock+')':'Out of Stock';

    const main = qs('pd-main-image'); const thumbs = qs('pd-thumbs');
    const images = Array.isArray(p.images) && p.images.length ? p.images : [p.image || '/static/assets/placeholders/placeholder.png'];
    thumbs.innerHTML = '';

    main.innerHTML = '';
    const mainImg = document.createElement('img'); mainImg.src = images[0]; mainImg.alt = p.name; main.appendChild(mainImg);
    main.classList.add('zoom-enabled');

    function setMain(src){ 
      mainImg.src = src; 
      mainImg.style.transform = 'scale(1)'; 
      mainImg.style.transformOrigin = '50% 50%';
      Array.from(thumbs.querySelectorAll('img')).forEach(i=> i.classList.toggle('selected', i.src === src));
    }

    images.forEach((src, idx)=>{
      const t = document.createElement('img'); t.src = src; t.alt = p.name + ' ' + (idx+1); t.addEventListener('click', ()=> setMain(src));
      if(idx===0) t.classList.add('selected'); thumbs.appendChild(t);
    });

    let isTouch = false;
    main.addEventListener('touchstart', ()=> isTouch = true);
    main.addEventListener('mousemove', (e)=>{
      if(isTouch) return; const rect = mainImg.getBoundingClientRect(); const x = ((e.clientX - rect.left) / rect.width) * 100; const y = ((e.clientY - rect.top) / rect.height) * 100; mainImg.style.transformOrigin = `${x}% ${y}%`; mainImg.style.transform = 'scale(1.6)'; main.classList.add('zooming');
    });
    main.addEventListener('mouseleave', ()=>{ mainImg.style.transform = 'scale(1)'; main.classList.remove('zooming'); });
    main.addEventListener('mouseenter', ()=>{ if(isTouch) return; mainImg.style.transform = 'scale(1.2)'; });

    qs('pd-add').addEventListener('click', (e)=>{ 
      addToCart(p.ref, parseInt(qs('pd-qty').value||1,10));
      try{ const img = main.querySelector('img'); const cartIcon = document.querySelector('.topbar .cart-icon'); if(window.EACIS && typeof window.EACIS.flyToCart === 'function') window.EACIS.flyToCart(img, cartIcon); }catch(ex){}
    });
    qs('pd-buy').addEventListener('click', ()=>{ addToCart(p.ref, parseInt(qs('pd-qty').value||1,10)); window.location.href='/cart'; });
  }

  /* CART page */
  function renderCart(){ 
    const container = qs('cart-items'); if(!container) return; 
    const cart = loadCart(); 
    if(cart.length===0){ 
      qs('cart-empty').style.display='block'; container.innerHTML=''; qs('cart-subtotal').textContent='PHP 0.00'; 
      return; 
    } 
    qs('cart-empty').style.display='none'; container.innerHTML=''; 
    let subtotal=0; 
    cart.forEach(item=>{ 
      const p = findProduct(item.ref) || {name:item.ref,price:0}; 
      const row = document.createElement('div'); 
      row.style.display='flex'; row.style.justifyContent='space-between'; row.style.alignItems='center'; row.style.padding='16px 0'; row.style.borderBottom='1px solid var(--border-subtle)';
      row.innerHTML = `
        <div><div class="ref-code">${item.ref}</div><div class="fw-semibold">${p.name}</div></div>
        <div style="text-align:right">
          <div class="fw-bold color-primary">PHP ${(p.price||0).toLocaleString()}</div>
          <div style="display:flex;gap:8px;align-items:center;margin-top:8px;">
            <button class="btn btn-ghost qty-decr" style="padding:4px 8px">−</button>
            <input class="type-body-sm" value="${item.qty}" style="width:40px;text-align:center;border:none;background:var(--grey-50);border-radius:4px" readonly>
            <button class="btn btn-ghost qty-incr" style="padding:4px 8px">+</button>
          </div>
        </div>`; 
      container.appendChild(row); 
      subtotal += (p.price||0)*item.qty; 
      row.querySelector('.qty-decr').addEventListener('click', ()=>{ if(item.qty>1) item.qty--; saveCart(cart); renderCart(); }); 
      row.querySelector('.qty-incr').addEventListener('click', ()=>{ item.qty++; saveCart(cart); renderCart(); }); 
    }); 
    qs('cart-subtotal').textContent = 'PHP ' + subtotal.toLocaleString(); 
    renderMiniCart(cart);
  }

  /* CHECKOUT */
  function initCheckout(){ 
    const next = qs('checkout-next'); if(!next) return; 
    let step=1; const totalSteps=3; const back = qs('checkout-back'); 
    function show(){ 
      for(let i=1;i<=totalSteps;i++){ 
        const s=qs('step-'+i); if(s) s.style.display = (i===step)?'block':'none'; 
      } 
      back.style.display = step>1? 'inline-block':'none'; 
      next.textContent = step<totalSteps? 'Next':'Place order'; 
    }
    show(); next.addEventListener('click', ()=>{ 
      if(step<totalSteps){ step++; show(); } 
      else { 
        const cart = loadCart(); if(cart.length===0){ Toast.show('Cart empty','error'); return; }
        const orders = JSON.parse(localStorage.getItem(ORDERS_KEY)||'[]'); 
        const ref = 'ORD-'+Date.now(); 
        orders.unshift({ref, date: new Date().toISOString(), amount: cart.reduce((s,it)=>{ const p=findProduct(it.ref); return s + (p? p.price*it.qty:0); },0), items: cart}); 
        localStorage.setItem(ORDERS_KEY, JSON.stringify(orders)); 
        localStorage.removeItem(CART_KEY); 
        if(window.Toast) window.Toast.success('Order placed', ref);
        window.location.href = '/customer/orders'; 
      } 
    }); 
    back.addEventListener('click', ()=>{ if(step>1) step--; show(); }); 
  }

  /* ORDERS */
  function renderOrders(){ 
    const el = qs('orders-list'); if(!el) return; 
    const orders = JSON.parse(localStorage.getItem(ORDERS_KEY)||'[]'); 
    if(!orders.length){ el.innerHTML = '<div class="empty-state">No orders yet.</div>'; return;} 
    el.innerHTML=''; 
    orders.forEach(o=>{ 
      const node = document.createElement('div'); 
      node.className='glass-card'; node.style.marginBottom='12px'; 
      node.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div><div class="ref-code">${o.ref}</div><div class="type-body-sm">${new Date(o.date).toLocaleDateString()}</div></div>
          <div class="fw-bold">PHP ${o.amount.toLocaleString()}</div>
        </div>
        <div style="margin-top:12px;display:flex;gap:8px;">
          <a href="/customer/order/${o.ref}" class="btn btn--sm btn--ghost">View Details</a>
        </div>`; 
      el.appendChild(node); 
    }); 
  }

  /* PROFILE */
  function initProfile(){ 
    const form = qs('profile-form'); if(!form) return; 
    const saved = JSON.parse(localStorage.getItem(PROFILE_KEY)||'{}'); 
    qs('pf-name').value = saved.name||''; qs('pf-email').value = saved.email||''; qs('pf-phone').value = saved.phone||''; 
    form.addEventListener('submit',(e)=>{ 
      e.preventDefault(); 
      const obj = {name:qs('pf-name').value,email:qs('pf-email').value,phone:qs('pf-phone').value}; 
      localStorage.setItem(PROFILE_KEY, JSON.stringify(obj)); 
      if(window.Toast) window.Toast.success('Profile saved', 'Settings updated.'); 
    }); 
  }

  /* Init dispatcher */
  document.addEventListener('DOMContentLoaded', ()=>{
    const cart = loadCart();
    updateCartBadges(cart);
    renderMiniCart(cart);
    
    initProductDetail(); 
    renderCart(); 
    initCheckout(); 
    renderOrders(); 
    initProfile();
    
    // Auto-update cart if another tab changes it
    window.addEventListener('storage', (e) => {
      if(e.key === CART_KEY){
        const newCart = loadCart();
        updateCartBadges(newCart);
        renderMiniCart(newCart);
        renderCart();
      }
    });
  });

  window.eacis = { addToCart };
})();
