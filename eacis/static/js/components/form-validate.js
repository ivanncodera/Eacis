// Basic client-side form validation enhancer for accessibility
(function(){
  function showError(input, message){
    input.setAttribute('aria-invalid','true');
    let id = input.id;
    if(!id){ id = 'f-' + Math.random().toString(36).slice(2,8); input.id = id; }
    let err = input.closest('form').querySelector('#error-for-' + id);
    if(!err){ err = document.createElement('div'); err.id = 'error-for-' + id; err.className = 'form-error'; err.setAttribute('role','alert'); input.closest('form').appendChild(err); }
    err.textContent = message;
    input.setAttribute('aria-describedby', err.id);
  }

  function clearError(input){
    input.removeAttribute('aria-invalid');
    const described = input.getAttribute('aria-describedby');
    if(described){ const el = document.getElementById(described); if(el && el.classList.contains('form-error')) el.remove(); input.removeAttribute('aria-describedby'); }
  }

  function validateForm(form){
    let valid = true;
    form.querySelectorAll('[required]').forEach(inp => {
      clearError(inp);
      if(!inp.value || inp.value.trim() === ''){ valid = false; const label = form.querySelector(`label[for="${inp.id}"]`) || inp.placeholder || inp.name; showError(inp, `${label || 'This field'} is required.`); }
      // type-specific
      if(inp.type === 'email' && inp.value){ const re = /\S+@\S+\.\S+/; if(!re.test(inp.value)){ valid = false; showError(inp, 'Please enter a valid email address.'); } }
    });
    return valid;
  }

  function init(){
    document.querySelectorAll('form[data-enhance="validate"]').forEach(form => {
      if(form.__validated) return; form.__validated = true;
      form.addEventListener('submit', (e)=>{
        if(!validateForm(form)) { e.preventDefault(); const firstErr = form.querySelector('.form-error'); firstErr && firstErr.focus && firstErr.focus(); }
      });
      form.addEventListener('input', (e)=> { if(e.target && e.target.matches('[required]')) clearError(e.target); });
    });
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
