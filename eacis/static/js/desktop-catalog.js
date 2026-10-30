/**
 * E-ACIS Electronic Home Appliance Catalog Controller
 * Architecture: Modular, Duplication-Safe, Accessible Desktop Controller
 * Features: Hardware-Accelerated Quick Spec Slide-Over, ARIA Sync, Keyboard Navigation (ESC)
 */

(function () {
  'use strict';

  function initApplianceCatalog() {
    const rootContainer = document.querySelector('.appliance-catalog-container');
    if (!rootContainer) return;

    // Idempotent Guard: Prevent multiple bindings across dynamic re-renders or HTMX swaps
    if (rootContainer.dataset.initialized === 'true') {
      return;
    }
    rootContainer.dataset.initialized = 'true';

    // DOM Elements
    const mobileFilterBtn = document.getElementById('mobile-filter-toggle');
    const filterSidebar = document.getElementById('spec-filter-sidebar');
    const quickSpecDrawer = document.getElementById('quick-spec-drawer');
    const quickSpecBackdrop = document.getElementById('quick-spec-backdrop');
    const quickSpecCloseBtn = document.getElementById('quick-spec-close-btn');

    // Drawer Dynamic Fill Elements
    const drawerTitle = document.getElementById('quick-spec-title');
    const drawerImg = document.getElementById('quick-spec-img');
    const drawerCategory = document.getElementById('quick-spec-category');
    const drawerTbody = document.getElementById('quick-spec-tbody');
    const drawerPrice = document.getElementById('quick-spec-price');
    const drawerDetailLink = document.getElementById('quick-spec-detail-link');

    let lastFocusedElement = null;

    /* ------------------------------------------------------------------------
       1. Mobile Filter Sidebar Toggle
       ------------------------------------------------------------------------ */
    if (mobileFilterBtn && filterSidebar) {
      mobileFilterBtn.addEventListener('click', function () {
        const isExpanded = mobileFilterBtn.getAttribute('aria-expanded') === 'true';
        mobileFilterBtn.setAttribute('aria-expanded', String(!isExpanded));
        filterSidebar.classList.toggle('is-open', !isExpanded);
      });
    }

    /* ------------------------------------------------------------------------
       2. Quick Spec Drawer Open / Close Logic
       ------------------------------------------------------------------------ */
    function openQuickSpec(triggerBtn) {
      if (!quickSpecDrawer || !quickSpecBackdrop) return;

      lastFocusedElement = triggerBtn;

      // Extract Data Attributes
      const name = triggerBtn.getAttribute('data-product-name') || 'Home Appliance';
      const category = triggerBtn.getAttribute('data-product-category') || 'Appliance';
      const price = triggerBtn.getAttribute('data-product-price') || '₱0.00';
      const img = triggerBtn.getAttribute('data-product-img') || '/static/assets/Featured.png';
      const warranty = triggerBtn.getAttribute('data-product-warranty') || '12 Months';
      const stock = triggerBtn.getAttribute('data-product-stock') || 'Available';
      const installment = triggerBtn.getAttribute('data-product-installment') || 'Standard';
      const detailUrl = triggerBtn.getAttribute('data-product-url') || '#';

      // Parse JSON Technical Specifications
      let specs = {};
      try {
        const rawSpecs = triggerBtn.getAttribute('data-product-specs');
        if (rawSpecs) {
          specs = JSON.parse(rawSpecs);
        }
      } catch (err) {
        specs = {};
      }

      // Populate Drawer Header & Media
      if (drawerTitle) drawerTitle.textContent = name;
      if (drawerCategory) drawerCategory.textContent = category;
      if (drawerPrice) drawerPrice.textContent = price;
      if (drawerDetailLink) drawerDetailLink.setAttribute('href', detailUrl);
      if (drawerImg) {
        drawerImg.src = img;
        drawerImg.alt = name;
      }

      // Populate Technical Spec Table
      if (drawerTbody) {
        drawerTbody.innerHTML = '';

        const specRows = [
          { label: 'Category', value: category },
          { label: 'Warranty', value: warranty },
          { label: 'Availability', value: parseInt(stock, 10) > 0 ? 'In Stock (' + stock + ' units)' : 'Pre-Order / Out of Stock' },
          { label: 'Payment Terms', value: installment },
        ];

        // Merge Specific Technical Specs (Wattage, Capacity, Inverter, etc.)
        if (specs && typeof specs === 'object') {
          if (specs.brand) specRows.push({ label: 'Brand', value: specs.brand });
          if (specs.model) specRows.push({ label: 'Model No.', value: specs.model });
          if (specs.wattage) specRows.push({ label: 'Wattage / Power', value: specs.wattage });
          if (specs.voltage) specRows.push({ label: 'Rated Voltage', value: specs.voltage });
          if (specs.capacity) specRows.push({ label: 'Net Capacity', value: specs.capacity });
          if (specs.energy_rating) specRows.push({ label: 'Energy Star Rating', value: specs.energy_rating });
          if (specs.inverter) specRows.push({ label: 'Inverter Technology', value: specs.inverter });
          if (specs.refrigerant) specRows.push({ label: 'Refrigerant Type', value: specs.refrigerant });
          if (specs.dimensions) specRows.push({ label: 'Dimensions (WxDxH)', value: specs.dimensions });
          if (specs.weight) specRows.push({ label: 'Unit Weight', value: specs.weight });
          if (specs.noise_level) specRows.push({ label: 'Operating Noise', value: specs.noise_level });

          // Any other remaining custom keys
          Object.keys(specs).forEach(function (key) {
            const standardKeys = [
              'brand', 'model', 'wattage', 'voltage', 'capacity',
              'energy_rating', 'inverter', 'refrigerant', 'dimensions', 'weight', 'noise_level'
            ];
            if (!standardKeys.includes(key)) {
              const formattedLabel = key.replace(/_/g, ' ').replace(/\b\w/g, function (l) { return l.toUpperCase(); });
              specRows.push({ label: formattedLabel, value: specs[key] });
            }
          });
        }

        // Render Table Rows
        specRows.forEach(function (row) {
          if (!row.value) return;
          const tr = document.createElement('tr');
          const th = document.createElement('th');
          th.setAttribute('scope', 'row');
          th.textContent = row.label;
          const td = document.createElement('td');
          td.textContent = row.value;
          tr.appendChild(th);
          tr.appendChild(td);
          drawerTbody.appendChild(tr);
        });
      }

      // Animate Drawer & Backdrop In
      triggerBtn.setAttribute('aria-expanded', 'true');
      quickSpecDrawer.setAttribute('aria-hidden', 'false');
      quickSpecBackdrop.classList.add('is-active');
      quickSpecDrawer.classList.add('is-active');

      // Accessibility: Focus Close Button
      if (quickSpecCloseBtn) {
        setTimeout(function () {
          quickSpecCloseBtn.focus();
        }, 50);
      }
    }

    function closeQuickSpec() {
      if (!quickSpecDrawer || !quickSpecBackdrop) return;

      quickSpecDrawer.classList.remove('is-active');
      quickSpecBackdrop.classList.remove('is-active');
      quickSpecDrawer.setAttribute('aria-hidden', 'true');

      if (lastFocusedElement) {
        lastFocusedElement.setAttribute('aria-expanded', 'false');
        lastFocusedElement.focus();
        lastFocusedElement = null;
      }
    }

    // Bind Quick Spec Triggers
    const triggerButtons = rootContainer.querySelectorAll('[data-quick-spec-btn]');
    triggerButtons.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        openQuickSpec(btn);
      });
    });

    // Close Handlers
    if (quickSpecCloseBtn) {
      quickSpecCloseBtn.addEventListener('click', function () {
        closeQuickSpec();
      });
    }

    if (quickSpecBackdrop) {
      quickSpecBackdrop.addEventListener('click', function () {
        closeQuickSpec();
      });
    }

    /* ------------------------------------------------------------------------
       3. Keyboard Ergonomics: ESC Key Listener
       ------------------------------------------------------------------------ */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' || e.keyCode === 27) {
        if (quickSpecDrawer && quickSpecDrawer.classList.contains('is-active')) {
          closeQuickSpec();
        } else if (filterSidebar && filterSidebar.classList.contains('is-open')) {
          filterSidebar.classList.remove('is-open');
          if (mobileFilterBtn) {
            mobileFilterBtn.setAttribute('aria-expanded', 'false');
            mobileFilterBtn.focus();
          }
        }
      }
    });
  }

  // Auto-initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApplianceCatalog);
  } else {
    initApplianceCatalog();
  }

  // Expose global init function for Turbo / HTMX / PJAX if used
  window.initApplianceCatalog = initApplianceCatalog;
})();
