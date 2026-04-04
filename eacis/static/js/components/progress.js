// Top progress simple controller
const TopProgress = (function(){
  let el = document.querySelector('.top-progress'); if(!el){ el = document.createElement('div'); el.className='top-progress'; document.body.appendChild(el); }
  return {
    start(){ el.classList.add('active'); },
    finish(){ el.classList.remove('active'); el.style.width='0%'; },
    set(p){ el.style.width = Math.max(0, Math.min(100,p)) + '%'; }
  };
})();
window.TopProgress = TopProgress;
