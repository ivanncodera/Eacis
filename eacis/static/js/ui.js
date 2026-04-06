/* ============================================
   E-ACIS UI ENHANCEMENTS & MICRO-INTERACTIONS
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

    // Ensure no stale dropdown open state survives partial reloads.
    document.querySelectorAll('.dropdown.dropdown--open').forEach(d => {
        d.classList.remove('dropdown--open');
    });
    
    // ── TOPBAR SCROLL EFFECT ──
    const topbar = document.querySelector('.topbar');
    if (topbar) {
        const handleScroll = () => {
            if (window.scrollY > 15) {
                topbar.classList.add('topbar--scrolled');
            } else {
                topbar.classList.remove('topbar--scrolled');
            }
        };
        window.addEventListener('scroll', handleScroll, { passive: true });
        handleScroll();
    }

    // ── SIDEBAR TOGGLE LOGIC ──
    const sidebarToggle = document.getElementById('base-sidebar-toggle');
    const body = document.body;
    
    // Initial state from localStorage
    const isCollapsed = localStorage.getItem('eacis_sidebar_collapsed') === 'true';
    if (isCollapsed) body.classList.add('sidebar-collapsed');

    // Portal layout setup
    // Initializing state directly from dataset for resilience
    const isAuthenticated = body.dataset.isAuthenticated === 'true' || (window.EACIS && window.EACIS.isAuthenticated);
    const userRole        = body.dataset.userRole        || (window.EACIS && window.EACIS.userRole);

    if (isAuthenticated && (userRole === 'customer' || userRole === 'seller' || userRole === 'admin')) {
        body.classList.add('has-sidebar');
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            const nowCollapsed = body.classList.toggle('sidebar-collapsed');
            localStorage.setItem('eacis_sidebar_collapsed', nowCollapsed);
        });
    }

    // ── LOGOUT CONFIRMATION ──
    const logoutBtn = document.getElementById('sidebar-logout-trigger');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            const confirmed = confirm('Are you sure you want to sign out of your E-ACIS account?');
            if (!confirmed) {
                e.preventDefault();
            }
        });
    }

    // ── UNIVERSAL DROPDOWN SYSTEM ──
    // Uses data-dropdown-toggle on the trigger and .dropdown as parent
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('[data-dropdown-toggle]');
        
        if (toggle) {
            e.preventDefault();
            const dropdown = toggle.closest('.dropdown');
            if (!dropdown) return;
            const isOpen = dropdown.classList.contains('dropdown--open');
            
            // Close all dropdowns first
            document.querySelectorAll('.dropdown').forEach(d => {
                d.classList.remove('dropdown--open');
            });

            // Toggle current if it wasn't open
            if (!isOpen) {
                dropdown.classList.add('dropdown--open');
            }
        } else if (!e.target.closest('.dropdown-menu')) {
            // Clicked outside - close all
            document.querySelectorAll('.dropdown').forEach(d => {
                d.classList.remove('dropdown--open');
            });
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.dropdown').forEach(d => {
                d.classList.remove('dropdown--open');
            });
        }
    });

    // ── PAGE ENTRANCE ANIMATIONS ──
    // Simple stagger for elements with .stagger-children
    document.querySelectorAll('.stagger-children').forEach(parent => {
        const children = parent.children;
        Array.from(children).forEach((child, index) => {
            child.style.animationDelay = `${index * 60}ms`;
            child.classList.add('page-enter');
        });
    });

    // ── RIPPLE EFFECT ──
    // Standard tactile feedback for all buttons
    document.addEventListener('mousedown', (e) => {
        const btn = e.target.closest('.btn, .nav-link, .topbar__avatar');
        if (!btn) return;

        const ripple = document.createElement('span');
        const rect = btn.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;

        ripple.style.width = ripple.style.height = `${size}px`;
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        ripple.classList.add('ripple');

        btn.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
    });

    // ── PREDICTIVE SEARCH LOGIC ──
    const searchInput = document.getElementById('topbar-search');
    const searchResults = document.getElementById('topbar-search-results');
    
    if (searchInput && searchResults) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim().toLowerCase();
            if (query.length < 2) {
                searchResults.style.display = 'none';
                return;
            }

            const products = window.PRODUCTS_DATA || [];
            const matches = products.filter(p => 
                p.name.toLowerCase().includes(query) || 
                p.category.toLowerCase().includes(query) ||
                p.ref.toLowerCase().includes(query)
            ).slice(0, 5);

            if (matches.length > 0) {
                searchResults.innerHTML = matches.map(p => `
                    <a href="/products/${p.ref}" class="search-result-item">
                        <img src="${p.image}" alt="${p.name}">
                        <div class="search-result-info">
                            <span class="search-result-name">${p.name}</span>
                            <span class="search-result-meta">${p.category} • ${p.ref}</span>
                        </div>
                        <div class="search-result-price">₱${Number(p.price).toLocaleString()}</div>
                    </a>
                `).join('');
                searchResults.style.display = 'block';
            } else {
                searchResults.innerHTML = `
                    <div style="padding:var(--sp-8) var(--sp-4); text-align:center; color:var(--grey-400);">
                        <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="margin-bottom:var(--sp-3); opacity:0.3;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                        <div class="type-body-sm fw-semibold">No matches found</div>
                        <div class="type-body-xs">Try searching for "RTX", "Smart", or "Fridge"</div>
                    </div>
                `;
                searchResults.style.display = 'block';
            }
        });

        // Close search results when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.topbar__search')) {
                searchResults.style.display = 'none';
            }
        });
    }

});
