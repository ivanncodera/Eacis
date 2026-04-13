// Button micro interactions: ripple and auto-init
(function(){
  function createRipple(event){
    const btn = event.currentTarget;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2;
    const x = (event.clientX || rect.left + rect.width/2) - rect.left - size/2;
    const y = (event.clientY || rect.top + rect.height/2) - rect.top - size/2;
    const ripple = document.createElement('span');
    ripple.className = 'btn__ripple';
    ripple.style.cssText = `width:${size}px;height:${size}px;left:${x}px;top:${y}px;`;
    btn.appendChild(ripple);
    ripple.addEventListener('animationend', ()=> ripple.remove());
  }

  function initButtons(root=document){
    const selectors = ['.btn--primary', '.btn--danger', '.btn--ghost', '.btn--white', '.btn'];
    selectors.forEach(sel => {
      root.querySelectorAll(sel).forEach(btn => {
        if(btn.__rippleInit) return; btn.__rippleInit = true;
        if (!btn.style.position) btn.style.position = 'relative';
        btn.style.overflow = 'hidden';
        btn.addEventListener('pointerdown', createRipple);
      });
    });
  }

  // Button loading helper
  function setButtonLoading(btn, isLoading=true, opts={}){
    if(!btn) return;
    const label = btn.querySelector('.btn__label');
    if(isLoading){
      btn.classList.add('btn--loading');
      btn.setAttribute('aria-busy','true');
      btn.setAttribute('aria-disabled','true');
      btn.disabled = true;
      if(label) label.setAttribute('aria-hidden','true');
      // prevent multiple submissions: disable form elements
      const form = btn.closest('form');
      if(form) form.querySelectorAll('button, input, select, textarea').forEach(el=> el.setAttribute('data-eacis-disabled','true'));
    } else {
      btn.classList.remove('btn--loading');
      btn.removeAttribute('aria-busy');
      btn.removeAttribute('aria-disabled');
      btn.disabled = false;
      if(label) label.removeAttribute('aria-hidden');
      const form = btn.closest('form');
      if(form) form.querySelectorAll('[data-eacis-disabled]').forEach(el=> el.removeAttribute('data-eacis-disabled'));
    }
  }

  function clearButtonLoading(btn){ setButtonLoading(btn, false); }

  // Auto-wire forms that declare data-enhance="submit-loading"
  function wireFormLoading(root=document){
    root.querySelectorAll('form[data-enhance="submit-loading"]').forEach(form => {
      if(form.__eacisWired) return; form.__eacisWired = true;
      form.addEventListener('submit', (e)=>{
        try{
          const btn = form.querySelector('button[type="submit"].btn--primary')
            || form.querySelector('button[type="submit"].btn--secondary')
            || form.querySelector('[type="submit"]');
          if(btn){ setButtonLoading(btn, true); }
        }catch(err){/* noop */}
      });
    });
  }

  // Auto init on DOM ready
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ()=>{ initButtons(); wireFormLoading(); });
  else { initButtons(); wireFormLoading(); }

  // expose public API
  window.EACIS = window.EACIS || {};
  window.EACIS.initButtons = initButtons;
  window.EACIS.setButtonLoading = setButtonLoading;
  window.EACIS.clearButtonLoading = clearButtonLoading;
  window.EACIS.wireFormLoading = wireFormLoading;
})();
