// Lightweight filters controller for product lists
(function(global){
  const qs = (sel, root=document) => root.querySelector(sel);
  const qsa = (sel, root=document) => Array.from(root.querySelectorAll(sel));

  function readFilters(container=document){
    const cats = qsa('input[name="cat"]:checked', container).map(i=>i.value);
    const warranty = qsa('input[name="warranty"]:checked', container).map(i=>parseInt(i.value,10));
    const min = parseFloat((qs('#price-min', container) && qs('#price-min', container).value) || 0);
    const maxRaw = (qs('#price-max', container) && qs('#price-max', container).value) || '';
    const max = maxRaw === '' ? Infinity : parseFloat(maxRaw);
    const installment = !!(qs('#installment-toggle', container) && qs('#installment-toggle', container).checked);
    const rating = parseInt((qs('#rating-filter', container) && qs('#rating-filter', container).value) || 0,10) || 0;
    return {cats,warranty,min,max,installment,rating};
  }

  function applyFilters(products, filters){
    return products.filter(p=>{
      if(filters.cats.length && !filters.cats.includes(p.category)) return false;
      if(filters.min && p.price < filters.min) return false;
      if(filters.max !== Infinity && p.price > filters.max) return false;
      if(filters.warranty.length && !filters.warranty.includes(p.warranty_months)) return false;
      if(filters.installment && !p.installment_eligible) return false;
      if(filters.rating && (p.rating || 0) < filters.rating) return false;
      return true;
    });
  }

  // Expose a simple API: init({root,products,onUpdate}) -> returns {destroy,run}
  function init(opts){
    const root = opts.root || document;
    const panel = qs('[aria-label="Filter panel"]', root);
    if(!panel) throw new Error('Filter panel not found');
    const applyBtn = qs('#apply-filters', panel);
    const clearBtn = qs('#clear-filters', panel);
    const onUpdate = opts.onUpdate;
    const products = opts.products || [];

    function run(){
      const f = readFilters(panel);
      const results = applyFilters(products, f);
      if(typeof onUpdate==='function') onUpdate(results, f);
    }

    function clear(){
      qsa('input[type="checkbox"]', panel).forEach(i=>i.checked=false);
      qsa('input[type="number"]', panel).forEach(i=>i.value='');
      const sel = qs('#rating-filter', panel); if(sel) sel.value='0';
      const inst = qs('#installment-toggle', panel); if(inst) inst.checked=false;
      run();
    }

    applyBtn.addEventListener('click', run);
    clearBtn.addEventListener('click', clear);

    // allow outside to request a run
    return {
      destroy(){
        applyBtn.removeEventListener('click', run);
        clearBtn.removeEventListener('click', clear);
      },
      run
    };
  }

  global.EacisFilters = {init,applyFilters};
})(window);
