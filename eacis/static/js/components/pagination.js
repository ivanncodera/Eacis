// Simple pagination controller for product grids
(function(){
  // single instance manager stored on window to allow destroy/recreate
  let INSTANCE = null;

  function init(opts){
    // destroy previous
    if(INSTANCE && typeof INSTANCE.destroy === 'function') INSTANCE.destroy();

    const { data = window.PRODUCTS || [], gridSelector, prevId, nextId, pageIndicatorId, pageSize = 12 } = opts;
    let page = 1; const perPage = pageSize;
    const totalPages = ()=> Math.max(1, Math.ceil(data.length / perPage));

    function render(){
      const start = (page - 1) * perPage; const end = start + perPage;
      const slice = data.slice(start, end);
      if(window.renderProducts) window.renderProducts(gridSelector, slice);
      const pi = document.getElementById(pageIndicatorId);
      if(pi) pi.textContent = `Page ${page} of ${totalPages()}`;
      const prev = document.getElementById(prevId); const next = document.getElementById(nextId);
      if(prev) prev.disabled = page <=1;
      if(next) next.disabled = page >= totalPages();
      const countEl = document.getElementById('products-count'); if(countEl) countEl.textContent = data.length;
    }

    function onPrev(e){ e.preventDefault(); if(page>1) page--; render(); }
    function onNext(e){ e.preventDefault(); if(page < totalPages()) page++; render(); }

    const prevBtn = document.getElementById(prevId);
    const nextBtn = document.getElementById(nextId);
    if(prevBtn) prevBtn.addEventListener('click', onPrev);
    if(nextBtn) nextBtn.addEventListener('click', onNext);

    render();

    INSTANCE = {
      next: ()=>{ if(page<totalPages()) page++; render(); },
      prev: ()=>{ if(page>1) page--; render(); },
      destroy: ()=>{
        if(prevBtn) prevBtn.removeEventListener('click', onPrev);
        if(nextBtn) nextBtn.removeEventListener('click', onNext);
        INSTANCE = null;
      }
    };

    return INSTANCE;
  }

  window.Pagination = { init };
})();
