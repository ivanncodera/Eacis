/* Shared form UX helpers for E-ACIS
   - submit-loading: disables submit buttons and shows spinner on submit
   - warn-on-exit: tracks form dirtiness and prompts before navigation
   - phone-normalize: normalizes PH mobile numbers to local 10-digit form
   - image-preview: shows preview for image file inputs
*/
(function(){

  function addGlobalStyles() {
    const css = `@keyframes eacis-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}} .eacis-spinner{display:inline-block;width:16px;height:16px;border:2px solid currentColor;border-top-color:transparent;border-radius:50%;animation:eacis-spin .8s linear infinite;margin-left:8px}`;
    const s = document.createElement('style');
    s.setAttribute('data-eacis','form-ux');
    s.appendChild(document.createTextNode(css));
    document.head.appendChild(s);
  }

  function normalizePHMobileValue(raw) {
    if (!raw) return '';
    const d = raw.replace(/\D/g,'');
    if (d.length === 11 && d.charAt(0) === '0') return d.slice(1);
    if (d.length === 12 && d.indexOf('63') === 0) return d.slice(2);
    if (d.length === 10) return d;
    // Best-effort: if longer than 10, take the last 10 digits
    if (d.length > 10) return d.slice(-10);
    return d;
  }

  function attachSubmitLoading(form) {
    form.addEventListener('submit', function(){
      // Normalize phone fields before submit
      const phones = form.querySelectorAll('input[type="tel"], input[name="phone"]');
      phones.forEach(ph => {
        try { const norm = normalizePHMobileValue(ph.value || ''); if (norm) ph.value = norm; } catch (e) {}
      });

      Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]')).forEach(btn => {
        if (btn.disabled) return;
        btn.disabled = true;
        try { btn.dataset.eacisOrig = btn.innerHTML; } catch (e) {}
        const span = document.createElement('span'); span.className = 'eacis-spinner'; span.setAttribute('aria-hidden','true');
        btn.appendChild(span);
      });
    }, {capture:false});
  }

  function attachUnsavedGuard(form) {
    const selectors = 'input[type="text"],input[type="tel"],input[type="email"],input[type="number"],input[type="password"],textarea,select,input[type="checkbox"],input[type="radio"],input[type="file"]';
    const inputs = Array.from(form.querySelectorAll(selectors));
    let dirty = false;
    const setDirty = () => { dirty = true; form.dataset.eacisDirty = '1'; };
    inputs.forEach(inp => {
      inp.addEventListener('change', setDirty);
      inp.addEventListener('input', setDirty);
    });

    window.addEventListener('beforeunload', (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    });

    document.addEventListener('click', (evt) => {
      const a = evt.target.closest('a');
      if (!a) return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
      if (dirty) {
        evt.preventDefault();
        const prompt = 'You have unsaved changes. Leave without saving?';
        if (window.confirmModal) {
          confirmModal(prompt).then(ok => { if (ok) window.location = href; });
        } else {
          if (confirm(prompt)) window.location = href;
        }
      }
    });

    form.addEventListener('submit', () => { dirty = false; form.dataset.eacisDirty = '0'; });
  }

  function attachImagePreview(form) {
    const inputs = Array.from(form.querySelectorAll('input[type="file"]'));
    inputs.forEach(inp => {
      if (!inp.accept || inp.accept.indexOf('image') === -1) return;
      const wrapper = inp.closest('div') || inp.parentElement;
      if (!wrapper) return;
      wrapper.style.position = wrapper.style.position || 'relative';
      let preview = wrapper.querySelector('.eacis-image-preview');
      inp.addEventListener('change', (ev) => {
        const file = inp.files && inp.files[0];
        if (!file) { if (preview) preview.remove(); return; }
        if (!file.type.startsWith('image/')) return;
        const reader = new FileReader();
        reader.onload = function(e){
          if (!preview) {
              // Create preview container so we can add controls (remove)
              const previewContainer = document.createElement('div');
              previewContainer.className = 'eacis-image-preview-container';
              previewContainer.style.cssText = 'position:absolute; inset:0; z-index:1; border-radius:6px; overflow:hidden;';

              preview = document.createElement('img');
              preview.className = 'eacis-image-preview';
              preview.style.cssText = 'width:100%; height:100%; object-fit:cover; display:block;';
              previewContainer.appendChild(preview);

              const removeBtn = document.createElement('button');
              removeBtn.type = 'button';
              removeBtn.className = 'eacis-image-remove';
              removeBtn.setAttribute('aria-label', 'Remove selected image');
              removeBtn.innerHTML = '×';
              removeBtn.addEventListener('click', (ev) => {
                ev.preventDefault();
                try { inp.value = ''; } catch (e) {}
                if (previewContainer && previewContainer.parentNode) previewContainer.parentNode.removeChild(previewContainer);
                // Restore any overlay text (e.g., 'Choose file')
                Array.from(wrapper.querySelectorAll('div')).forEach(div => {
                  if (div.textContent && div.textContent.trim().toLowerCase().includes('choose file')) div.style.display = '';
                });
              });
              previewContainer.appendChild(removeBtn);

              wrapper.insertBefore(previewContainer, wrapper.firstChild);
              // remember reference to container so we can remove later
              wrapper._eacisPreviewContainer = previewContainer;
            }
            // Update preview image
            preview.src = e.target.result;
            Array.from(wrapper.querySelectorAll('div')).forEach(div => {
              if (div.textContent && div.textContent.trim().toLowerCase().includes('choose file')) div.style.display = 'none';
            });
        };
        reader.readAsDataURL(file);
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    addGlobalStyles();
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
      const enh = (form.getAttribute('data-enhance') || '').toLowerCase();
      const id = form.id || '';
      const shouldAttachSubmit = enh.includes('submit-loading') || ['product-form','profile-settings-form'].includes(id) || form.classList.contains('checkout-layout');
      if (shouldAttachSubmit) attachSubmitLoading(form);
      const shouldGuard = enh.includes('warn-on-exit') || ['product-form','profile-settings-form','checkout-layout'].includes(id);
      if (shouldGuard) attachUnsavedGuard(form);
      const shouldImage = enh.includes('image-preview') || (form.querySelector('input[type="file"][accept]') !== null);
      if (shouldImage) attachImagePreview(form);
      Array.from(form.querySelectorAll('input[type="tel"]')).forEach(ph => {
        ph.addEventListener('blur', () => { const norm = normalizePHMobileValue(ph.value || ''); if (norm) ph.value = norm; });
      });
    });
  });

})();
