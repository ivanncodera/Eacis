// Top progress bar controller
(function(){
  const Progress = {
    el: null,
    timer: null,
    value: 0,
    init() {
      if (this.el) return;
      this.el = document.createElement('div');
      this.el.className = 'top-progress';
      document.body.appendChild(this.el);
    },
    start() {
      this.init();
      clearInterval(this.timer);
      this.value = 15;
      this.el.style.width = this.value + '%';
      this.el.classList.add('active');
      this.timer = setInterval(()=>{
        if (this.value < 80) {
          this.value += Math.max(2, Math.random()*8);
          this.el.style.width = Math.min(80, this.value) + '%';
        } else {
          clearInterval(this.timer);
        }
      }, 350);
    },
    set(p){ this.init(); this.value = Math.max(0, Math.min(100, p)); this.el.style.width = this.value + '%'; },
    done() {
      if (!this.el) return;
      clearInterval(this.timer);
      this.el.style.width = '100%';
      setTimeout(()=>{
        this.el.classList.remove('active');
        // reset after hide
        setTimeout(()=>{ if(this.el) this.el.style.width = '0%'; }, 200);
      }, 320);
    }
  };

  // expose
  window.TopProgress = Progress;

  // hook into document readiness
  document.addEventListener('readystatechange', ()=>{
    if (document.readyState === 'interactive') Progress.start();
    if (document.readyState === 'complete') Progress.done();
  });

  // beforeunload - show activity
  window.addEventListener('beforeunload', ()=> Progress.start());

  // Wrap fetch to show progress bar
  if (window.fetch) {
    const origFetch = window.fetch.bind(window);
    window.fetch = function(...args){
      Progress.start();
      return origFetch(...args).finally(()=>{ Progress.done(); });
    };
  }

  // XHR hook
  try {
    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...args){
      try { Progress.start(); this.addEventListener('loadend', ()=> Progress.done(), { once: true }); } catch(e){}
      return origSend.apply(this, args);
    };
  } catch(e) {}

})();
// Top progress bar: show/hide and simulate progress
(function(){
  const barId = 'eacis-top-progress';
  const ensure = () => {
    let b = document.getElementById(barId);
    if (!b) {
      b = document.createElement('div'); b.id = barId;
      b.className = 'top-progress';
      b.style.position = 'fixed'; b.style.top='0'; b.style.left='0'; b.style.height='3px';
      b.style.width='0%'; b.style.zIndex=99999; b.style.background='linear-gradient(90deg,#007AFF,#00C48C)';
      b.style.transition='width 400ms linear, opacity 300ms ease'; b.style.opacity='0';
      document.body.appendChild(b);
    }
    return b;
  };
  const start = () => {
    const b = ensure();
    b.style.opacity='1';
    b.style.width='6%';
    // simulate progress
    let pct = 6; const t = setInterval(()=>{ pct += Math.random()*12; if (pct<90) b.style.width = pct + '%'; else { b.style.width = '90%'; clearInterval(t); } }, 450);
    b.dataset._timer = 'running';
  };
  const done = () => {
    const b = ensure();
    b.style.width='100%';
    setTimeout(()=>{ b.style.opacity='0'; b.style.width='0%'; }, 500);
    delete b.dataset._timer;
  };
  window.EACIS = window.EACIS || {};
  window.EACIS.TopProgress = { start, done };
  document.addEventListener('DOMContentLoaded', ()=>{ /* no-op */ });
})();
