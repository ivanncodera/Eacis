// Initialize floating label behavior for inputs inside `.form-floating`
(function(){
  function syncValueState(input){
    if (!input) return;
    if (input.value && input.value.trim() !== '') input.classList.add('has-value');
    else input.classList.remove('has-value');
  }

  function init(){
    document.querySelectorAll('.form-floating').forEach(wrapper => {
      const input = wrapper.querySelector('input, textarea');
      const label = wrapper.querySelector('label');
      if (!input || !label) return;

      // ensure placeholder is present to allow :placeholder-shown fallback
      if (!input.getAttribute('placeholder')) input.setAttribute('placeholder', ' ');

      syncValueState(input);

      input.addEventListener('input', ()=> syncValueState(input));
      input.addEventListener('change', ()=> syncValueState(input));
      input.addEventListener('blur', ()=> syncValueState(input));
      input.addEventListener('focus', ()=> input.classList.add('is-focused'));
      input.addEventListener('blur', ()=> input.classList.remove('is-focused'));
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
