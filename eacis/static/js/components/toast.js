// Enhanced toast manager — accessible structure and timer handling
const Toast = (function(){
  const stack = document.createElement('div');
  stack.className = 'toast-stack';
  stack.setAttribute('aria-live','polite');
  stack.setAttribute('aria-atomic','false');
  document.body.appendChild(stack);

  function createIcon(type){
    const wrap = document.createElement('div');
    wrap.className = 'toast__icon';
    const icons = {
      success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
      danger:  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info:    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };
    wrap.innerHTML = icons[type] || icons.info;
    return wrap;
  }

  function show(message, type='info', opts={duration:5000, title:null}){
    const duration = (opts && opts.duration) || 5000;

    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.setAttribute('role','status');
    el.setAttribute('aria-live','polite');
    el.setAttribute('aria-atomic','false');

    // icon
    el.appendChild(createIcon(type));

    // content
    const content = document.createElement('div');
    content.className = 'toast__content';
    if (opts.title) {
      const t = document.createElement('div'); t.className = 'toast__title'; t.textContent = opts.title;
      content.appendChild(t);
    }
    const msg = document.createElement('div'); msg.className = 'toast__message'; msg.textContent = message;
    content.appendChild(msg);
    el.appendChild(content);

    // dismiss
    const dismissBtn = document.createElement('button');
    dismissBtn.className = 'toast__dismiss';
    dismissBtn.setAttribute('aria-label','Dismiss notification');
    dismissBtn.innerHTML = '✕';
    dismissBtn.addEventListener('click', ()=> dismiss(true));
    el.appendChild(dismissBtn);

    // timer bar
    const timer = document.createElement('div'); timer.className = 'toast__timer';
    const timerFill = document.createElement('div'); timerFill.className = 'toast__timer-fill';
    timer.appendChild(timerFill);
    el.appendChild(timer);

    // set animation duration via CSS custom property
    el.style.setProperty('--toast-duration', duration + 'ms');
    timerFill.style.animationDuration = duration + 'ms';

    let timeoutId = null;
    function startTimer(){
      timeoutId = setTimeout(()=> dismiss(), duration);
      // restart CSS animation
      timerFill.classList.remove('running');
      // trigger reflow
      void timerFill.offsetWidth;
      timerFill.classList.add('running');
    }

    function clearTimer(){
      if (timeoutId) { clearTimeout(timeoutId); timeoutId = null; }
      timerFill.classList.remove('running');
    }

    function dismiss(manual=false){
      clearTimer();
      el.classList.add('toast--exit');
      el.addEventListener('animationend', ()=> { if(el.parentNode) el.parentNode.removeChild(el); }, { once: true });
    }

    el.addEventListener('mouseenter', clearTimer);
    el.addEventListener('mouseleave', startTimer);

    stack.appendChild(el);
    // microtask to allow animations to start
    requestAnimationFrame(()=> startTimer());

    return { dismiss };
  }

  return { show };
})();

window.Toast = Toast;
