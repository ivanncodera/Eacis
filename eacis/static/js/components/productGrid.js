function formatPHP(n){ return 'PHP\u00A0' + Number(n).toLocaleString('en-PH', {minimumFractionDigits:2}); }

function getCsrfToken(){
  if (window.EACIS && window.EACIS.csrfToken) return window.EACIS.csrfToken;
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  return '';
}

async function addProductToCart(ref, qty){
  const token = getCsrfToken();
  const body = new URLSearchParams();
  body.set('csrf_token', token);
  body.set('action', 'add');
  body.set('product_ref', ref);
  body.set('qty', String(Math.max(parseInt(qty || 1, 10), 1)));

  const response = await fetch('/cart', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      'X-Requested-With': 'XMLHttpRequest'
    },
    credentials: 'same-origin',
    body: body.toString()
  });

  if (!response.ok) {
    throw new Error('Failed to add to cart');
  }

  if (window.EACIS && typeof window.EACIS.refreshMiniCart === 'function') {
    window.EACIS.refreshMiniCart();
  }

  return true;
}

window.renderProducts = function(sel, list){
  const root = document.querySelector(sel);
  if(!root) return;
  root.innerHTML = '';

  list.forEach(p => {
    const refValue = p.ref || p.product_ref || '';
    const imageValue = p.image || p.image_url || '/static/assets/products/refrigerator.webp';
    const reviewsValue = Number(p.reviews || 0);
    const ratingRaw = p.rating != null && p.rating !== '' ? Number(p.rating) : NaN;
    const ratingValue = Number.isFinite(ratingRaw) && ratingRaw > 0 ? ratingRaw : null;

    const card = document.createElement('article');
    card.className = 'product-card reveal';
    card.tabIndex = 0;
    const titleId = 'prod-title-' + (refValue || Math.random().toString(36).slice(2,8));
    card.setAttribute('aria-labelledby', titleId);

    /* ─── IMAGE WRAP ─── */
    const imgWrap = document.createElement('div');
    imgWrap.className = 'product-card__img-wrap';
    imgWrap.style.background = 'var(--glass-ultra)';
    imgWrap.style.backdropFilter = 'var(--glass-blur-sm)';

    const img = document.createElement('img');
    img.src = imageValue;
    img.alt = p.name;
    img.loading = 'lazy';
    imgWrap.appendChild(img);

    /* ─── BADGE ─── */
    if(p.badge){
      const badges = document.createElement('div');
      badges.className = 'product-card__badges-img';
      const b = document.createElement('span');
      b.className = 'badge badge--primary';
      b.textContent = p.badge;
      badges.appendChild(b);
      imgWrap.appendChild(badges);
    }

    /* ─── QUICK ACTIONS (bottom-center slide-up) ─── */
    const quickActions = document.createElement('div');
    quickActions.className = 'product-card__quick-actions';

    // Quick View button
    const btnQuick = document.createElement('button');
    btnQuick.className = 'product-card__action-btn';
    btnQuick.setAttribute('aria-label', 'Quick View');
    btnQuick.innerHTML = '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M21 12c-1.9 3-5.3 6-9 6s-7.1-3-9-6c1.9-3 5.3-6 9-6s7.1 3 9 6Z"/></svg>';

    btnQuick.addEventListener('click', (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      try {
        const content = document.createElement('div');
        content.className = 'modal modal--lg product-quickview';
        content.innerHTML = `
          <div class="modal__header">
            <button class="modal__close" aria-label="Close">
              <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
          <div class="modal__body pq-layout">
            <div class="pq-image-container">
              <img src="${imageValue}" alt="${p.name}">
            </div>
            <div class="pq-details">
              <div class="type-label--sm mb-2" style="letter-spacing:0.06em;">${p.category}</div>
              <h2 class="type-h2 mb-4">${p.name}</h2>
              <div class="pq-meta">
                <div class="rating-badge">
                  <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                  <span class="fw-bold">${ratingValue || '4.8'}</span>
                </div>
                <span class="dot-divider"></span>
                <span class="type-body-sm">${reviewsValue} reviews</span>
                <span class="dot-divider"></span>
                <span class="type-body-sm fw-semibold ${p.stock > 5 ? 'text-success' : 'text-danger'}">${p.stock > 0 ? (p.stock <= 5 ? 'Only '+p.stock+' left' : 'In Stock') : 'Out of Stock'}</span>
              </div>
              <div class="pq-price">${formatPHP(p.price)}</div>
              <div class="pq-actions">
                <button class="btn btn--primary btn--lg" data-add-ref="${refValue}" ${p.stock <= 0 ? 'disabled' : ''}>
                  <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
                  ${window.EACIS?.isAuthenticated ? 'Add to Cart' : 'Sign In to Buy'}
                </button>
                <a href="/products/${refValue}" class="btn btn--secondary btn--square btn--lg" aria-label="View full details" title="View full details">
                  <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </a>
              </div>
            </div>
          </div>`;

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.style.display = 'none';
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        if(window.ModalManager) ModalManager.open(content);
        
        // Handle Close Clicks
        const closeBtn = content.querySelector('.modal__close');
        if(closeBtn) {
          closeBtn.addEventListener('click', () => {
            if(window.ModalManager) ModalManager.close(content);
            setTimeout(() => overlay.remove(), 400); // Standard exit animation time
          });
        }

        // Handle Overlay Click-to-Close
        overlay.addEventListener('click', (e) => {
          if (e.target === overlay) {
            if(window.ModalManager) ModalManager.close(content);
            setTimeout(() => overlay.remove(), 400);
          }
        });

        const addBtn = content.querySelector('[data-add-ref]');
        if(addBtn){
          addBtn.addEventListener('click', async () => {
            try {
              await addProductToCart(refValue, 1);
            } catch (e) {
              if(window.Toast) Toast.error('Could not add to cart', 'Please try again.');
              return;
            }
            const cartIcon = document.querySelector('.topbar__icon-btn .cart-icon') || document.querySelector('.topbar__icon-btn svg');
            if(window.EACIS && window.EACIS.flyToCart) window.EACIS.flyToCart(img, cartIcon);
            if(window.ModalManager) ModalManager.close(content);
            if(window.Toast) Toast.success('Added to cart', p.name);
          });
        }
      } catch(e){ console.error(e); }
    });
    quickActions.appendChild(btnQuick);

    /* Session-aware cart / sign-in button */
    function attachAuthAction(){
      const session = window.EACIS;
      const existing = quickActions.querySelector('.auth-action');
      if(existing) existing.remove();

      const btn = document.createElement('button');
      btn.className = 'product-card__action-btn auth-action';

      if(session && session.isAuthenticated && session.userRole === 'customer'){
        btn.setAttribute('aria-label', 'Add to Cart');
        btn.innerHTML = '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>';
        btn.addEventListener('click', async (ev) => {
          ev.stopPropagation();
          try {
            await addProductToCart(refValue, 1);
          } catch (e) {
            if(window.Toast) Toast.error('Could not add to cart', 'Please try again.');
            return;
          }
          const cartIcon = document.querySelector('.cart-icon svg');
          if(window.EACIS && window.EACIS.flyToCart) window.EACIS.flyToCart(img, cartIcon);
          if(window.Toast) Toast.success('Product added', p.name);
        });
      } else {
        btn.setAttribute('aria-label', 'Sign In');
        btn.innerHTML = '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
        });
      }
      quickActions.appendChild(btn);
    }
    attachAuthAction();
    document.addEventListener('eacis:session', () => attachAuthAction());
    imgWrap.appendChild(quickActions);

    /* ─── BODY ─── */
    const body = document.createElement('div');
    body.className = 'product-card__body';

    const ref = document.createElement('div');
    ref.className = 'product-card__ref';
    ref.textContent = refValue;

    const title = document.createElement('div');
    title.className = 'product-card__name';
    title.textContent = p.name;
    title.id = titleId;

    const priceRow = document.createElement('div');
    priceRow.className = 'product-card__price-row';

    const price = document.createElement('div');
    price.className = 'product-card__price';
    price.style.fontWeight = '800';
    price.style.letterSpacing = '-0.02em';
    price.textContent = formatPHP(p.price);
    priceRow.appendChild(price);

    if(p.comparePrice){
      const compare = document.createElement('div');
      compare.className = 'product-card__compare-price';
      compare.textContent = formatPHP(p.comparePrice);
      priceRow.appendChild(compare);
    }

    if(p.installment_enabled){
      const inst = document.createElement('div');
      inst.className = 'product-card__installment';
      inst.textContent = 'Installments available';
      priceRow.appendChild(inst);
    }

    body.appendChild(ref);
    body.appendChild(title);
    if(ratingValue != null || reviewsValue > 0){
      const rating = document.createElement('div');
      rating.className = 'product-card__rating';
      let starsHTML = '<div class="product-card__stars">';
      if(ratingValue != null){
        const fullStars = Math.floor(ratingValue);
        const halfStar = ratingValue % 1 >= 0.5;
        for(let i = 0; i < fullStars; i++) starsHTML += '★';
        if(halfStar) starsHTML += '½';
      }
      starsHTML += '</div>';
      const reviewPart = reviewsValue > 0 ? `<div class="product-card__review-count">(${reviewsValue})</div>` : '';
      rating.innerHTML = `${starsHTML}${reviewPart}`;
      body.appendChild(rating);
    }
    body.appendChild(priceRow);

    /* ─── FOOTER ─── */
    const footer = document.createElement('div');
    footer.className = 'product-card__footer';
    if(p.stock <= 0){
      footer.innerHTML = '<span class="badge badge--danger">Out of Stock</span>';
    } else if(p.stock < 10){
      footer.innerHTML = `<span class="badge badge--warning">Low Stock: ${p.stock}</span>`;
    }

    /* ─── CLICK NAVIGATION ─── */
    card.addEventListener('click', (e) => {
      if(!e.target.closest('.product-card__action-btn')) window.location.href = `/products/${refValue}`;
    });
    card.addEventListener('keydown', (e) => {
      if(e.key === 'Enter') window.location.href = `/products/${refValue}`;
    });

    card.appendChild(imgWrap);
    card.appendChild(body);
    if(footer.innerHTML !== '') card.appendChild(footer);
    root.appendChild(card);
  });

  if(window.initReveal) window.initReveal();
};
