// Microinteractions: ripple, counters, scroll reveals, fly-to-cart
(function(){
  // Ripple effect (delegated)
  function createRipple(btn, clientX, clientY) {
    const rect = btn.getBoundingClientRect();
    const diameter = Math.max(rect.width, rect.height) * 1.2;
    const radius = diameter / 2;
    const circle = document.createElement('span');
    circle.className = 'ripple';
    circle.style.width = circle.style.height = diameter + 'px';
    circle.style.left = (clientX - rect.left - radius) + 'px';
    circle.style.top = (clientY - rect.top - radius) + 'px';
    btn.style.position = btn.style.position || 'relative';
    btn.style.overflow = 'hidden';
    const old = btn.querySelector('.ripple'); if(old) old.remove();
    btn.appendChild(circle);
    setTimeout(()=> circle.remove(), 700);
  }

  document.addEventListener('click', (e)=>{
    const btn = e.target.closest('.btn--primary, .btn-primary');
    if(!btn) return;
    createRipple(btn, e.clientX, e.clientY);
  }, {capture:false});

  // Animate number counter for KPI elements with data-count
  function animateCounterEl(el, target, duration){
    const start = 0;
    const startTime = performance.now();
    const isDecimal = (target % 1) !== 0;
    function update(now){
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (target - start) * eased;
      el.textContent = isDecimal ? current.toLocaleString('en-PH', {minimumFractionDigits:2}) : Math.floor(current).toLocaleString('en-PH');
      if(progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
  }

  // Intersection observer for counters and scroll reveals
  const io = new IntersectionObserver((entries, obs)=>{
    entries.forEach(entry=>{
      if(!entry.isIntersecting) return;
      const el = entry.target;
      if(el.dataset.count){
        const val = parseFloat(el.dataset.count);
        animateCounterEl(el, val, parseInt(el.dataset.duration||1200,10));
      }
      if(el.classList.contains('animate-on-scroll')){
        el.style.opacity = 0;
        const delay = el.dataset.delay || '0ms';
        el.style.animation = `fadeUp ${el.dataset.duration || '320ms'} var(--ease-out) ${delay} forwards`;
      }
      obs.unobserve(el);
    });
  }, {threshold:0.1});

  document.querySelectorAll('[data-count], .animate-on-scroll').forEach(el=> io.observe(el));

  // Fly to cart animation
  function flyToCart(productImageEl, cartIconEl){
    if(!productImageEl || !cartIconEl) return;
    const imgRect = productImageEl.getBoundingClientRect();
    const cartRect = cartIconEl.getBoundingClientRect();
    const ghost = productImageEl.cloneNode(true);
    ghost.style.position = 'fixed';
    ghost.style.left = imgRect.left + 'px';
    ghost.style.top = imgRect.top + 'px';
    ghost.style.width = imgRect.width + 'px';
    ghost.style.height = imgRect.height + 'px';
    ghost.style.borderRadius = getComputedStyle(productImageEl).borderRadius || '8px';
    ghost.style.pointerEvents = 'none';
    ghost.style.zIndex = 99999;
    ghost.style.transition = 'all 720ms cubic-bezier(0.4,0,0.2,1)';
    document.body.appendChild(ghost);
    requestAnimationFrame(()=>{
      ghost.style.left = (cartRect.left + cartRect.width/2 - 12) + 'px';
      ghost.style.top = (cartRect.top + cartRect.height/2 - 12) + 'px';
      ghost.style.width = '24px';
      ghost.style.height = '24px';
      ghost.style.opacity = '0';
      ghost.style.borderRadius = '50%';
    });
    setTimeout(()=> ghost.remove(), 800);
  }

  // Expose helpers
  window.EACIS = window.EACIS || {};
  window.EACIS.flyToCart = flyToCart;

  // Image zoom: toggle zoom on click within #pd-main-image
  document.addEventListener('click', (e)=>{
    const root = e.target.closest('#pd-main-image');
    if(!root) return;
    const img = root.querySelector('img');
    if(!img) return;
    // toggle zoom state
    if(root.classList.contains('zooming')){
      root.classList.remove('zooming');
      img.style.transform = '';
      img.style.transformOrigin = '';
    } else {
      root.classList.add('zooming');
      // set transform origin based on click position
      const rect = img.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      img.style.transformOrigin = `${x}% ${y}%`;
      img.style.transform = 'scale(2)';
    }
  });

  // Pan while zoomed (mousemove)
  document.addEventListener('mousemove', (e)=>{
    const root = e.target.closest('#pd-main-image.zooming');
    if(!root) return;
    const img = root.querySelector('img');
    if(!img) return;
    const rect = img.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    img.style.transformOrigin = `${x}% ${y}%`;
  });

  // Toast close and pause on hover
  function enhanceToast(t){
    if(t.__enhanced) return; t.__enhanced = true;
    // close button
    const btn = document.createElement('button'); btn.className='toast-close'; btn.setAttribute('aria-label','Close notification'); btn.innerHTML='✕';
    btn.addEventListener('click', ()=> t.remove());
    t.appendChild(btn);
    // pause progress on hover
    t.addEventListener('mouseenter', ()=>{
      const fill = t.querySelector('.toast__progress-fill'); if(fill) fill.style.animationPlayState = 'paused';
    });
    t.addEventListener('mouseleave', ()=>{
      const fill = t.querySelector('.toast__progress-fill'); if(fill) fill.style.animationPlayState = 'running';
    });
  }

  // wire existing toasts and observe additions
  document.querySelectorAll('.toast').forEach(enhanceToast);
  const mo2 = new MutationObserver((m)=>{ m.forEach(rec=>{ rec.addedNodes.forEach(n=>{ if(n.nodeType===1 && n.classList.contains('toast')) enhanceToast(n); }); }); });
  mo2.observe(document.body, { childList:true, subtree:true });

  // Toast progress auto-wire: add progress bar when toast has data-timeout
  function wireToastProgress(){
    document.querySelectorAll('.toast').forEach(t=>{
      if(t.querySelector('.toast__progress')) return;
      const timeout = parseInt(t.dataset.timeout||5000,10);
      const wrap = document.createElement('div'); wrap.className = 'toast__progress';
      const fill = document.createElement('div'); fill.className = 'toast__progress-fill';
      fill.style.animationDuration = (timeout/1000)+'s';
      wrap.appendChild(fill);
      t.appendChild(wrap);
    });
  }

  // Observe body for toasts being added
  const mo = new MutationObserver(()=> wireToastProgress());
  mo.observe(document.body, {childList:true, subtree:true});

  // Accessibility: respect reduced-motion by disabling animations
  if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    document.documentElement.classList.add('reduced-motion');
  }

})();
