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
    const searchRole = body?.dataset?.userRole || 'guest';
    const searchMaxLength = 80;

    const portalShortcuts = {
        guest: [
            { title: 'Shop Catalog', hint: 'Browse all appliances', href: '/shop' },
            { title: 'Support Center', hint: 'Get help and inquiries', href: '/support' }
        ],
        customer: [
            { title: 'My Orders', hint: 'Track order references', href: '/customer/orders' },
            { title: 'Rewards', hint: 'View loyalty points', href: '/customer/loyalty' },
            { title: 'Returns', hint: 'Manage return requests', href: '/customer/returns' }
        ],
        seller: [
            { title: 'Seller Dashboard', hint: 'View revenue and KPIs', href: '/seller/dashboard' },
            { title: 'Products', hint: 'Manage product listings', href: '/seller/products' },
            { title: 'Orders', hint: 'Process customer orders', href: '/seller/orders' },
            { title: 'Inventory', hint: 'Monitor stock levels', href: '/seller/inventory' }
        ],
        admin: [
            { title: 'Admin Dashboard', hint: 'System overview and metrics', href: '/admin/dashboard' },
            { title: 'Products', hint: 'Monitor marketplace listings', href: '/admin/products' },
            { title: 'Customers', hint: 'Review customer accounts', href: '/admin/customers' },
            { title: 'Audit Logs', hint: 'Inspect security activity', href: '/admin/audit' }
        ]
    };

    function normalizeText(value) {
        return String(value || '').trim().toLowerCase();
    }

    function collapseWhitespace(value) {
        return String(value || '').replace(/\s+/g, ' ').trim();
    }

    function sanitizeSearchQuery(value) {
        return collapseWhitespace(value)
            .replace(/[^\p{L}\p{N}\s&/.,'()\-+#]/gu, '')
            .replace(/\s{2,}/g, ' ')
            .slice(0, searchMaxLength);
    }

    function isCodeLikeQuery(value) {
        return /^[\p{L}\p{N}][\p{L}\p{N}\-#/]{3,}$/u.test(value) || /^[0-9]{4,}$/.test(value);
    }

    function validateSearchQuery(value, role) {
        const normalized = collapseWhitespace(value);
        const cleaned = sanitizeSearchQuery(value);
        if (!cleaned) {
            return { valid: false, cleaned: '', message: 'Type a product, category, or order reference.' };
        }
        if (cleaned.length < 2) {
            return { valid: false, cleaned, message: 'Search needs at least 2 characters.' };
        }
        if (cleaned !== normalized) {
            return { valid: true, cleaned, message: 'Unsupported characters were removed from your search.' };
        }
        if (role === 'admin' && /^\d+$/.test(cleaned)) {
            return { valid: true, cleaned, message: 'Numeric searches on admin views are treated as reference lookups.' };
        }
        if (isCodeLikeQuery(cleaned)) {
            return { valid: true, cleaned, message: 'Structured code search enabled.' };
        }
        return { valid: true, cleaned, message: '' };
    }

    function productHrefByRole(ref, role) {
        if (!ref) return '/shop';
        if (role === 'seller') return `/seller/products/${encodeURIComponent(ref)}`;
        return `/products/${encodeURIComponent(ref)}`;
    }

    function fallbackSearchHref(query, role) {
        const encoded = encodeURIComponent(query || '');
        if (role === 'seller') return `/seller/products?q=${encoded}`;
        if (role === 'admin') return `/admin/products?q=${encoded}`;
        if (role === 'customer' || role === 'guest') return `/shop?q=${encoded}`;
        return `/shop?q=${encoded}`;
    }

    function renderNoResults(query, role, message = '') {
        const shortcuts = (portalShortcuts[role] || portalShortcuts.guest).slice(0, 3);
        const quickLinks = shortcuts.map(item => `
            <a href="${item.href}" class="search-result-item">
                <div class="search-result-info">
                    <span class="search-result-name">${item.title}</span>
                    <span class="search-result-meta">${item.hint}</span>
                </div>
            </a>
        `).join('');

        return `
            <div style="padding:var(--sp-6) var(--sp-4); border-bottom:1px solid var(--border-subtle); text-align:center; color:var(--grey-500);">
                <div class="type-body-sm fw-semibold">${message || `No direct match for \"${query}\"`}</div>
                <div class="type-body-xs mt-1">Try quick navigation below</div>
            </div>
            ${quickLinks}
        `;
    }

    function renderNotice(message, role) {
        const shortcuts = (portalShortcuts[role] || portalShortcuts.guest).slice(0, 3);
        return `
            <div style="padding:var(--sp-6) var(--sp-4); border-bottom:1px solid var(--border-subtle); color:var(--grey-500);">
                <div class="type-body-sm fw-semibold">${message}</div>
                <div class="type-body-xs mt-1">Suggested areas for this portal appear below.</div>
            </div>
            ${shortcuts.map(item => `
                <a href="${item.href}" class="search-result-item">
                    <div class="search-result-info">
                        <span class="search-result-name">${item.title}</span>
                        <span class="search-result-meta">${item.hint}</span>
                    </div>
                </a>
            `).join('')}
        `;
    }

    if (searchInput && searchResults) {
        // Move predictive results to body so topbar/container overflow never clips it.
        if (searchResults.parentElement !== document.body) {
            document.body.appendChild(searchResults);
        }

        searchInput.setAttribute('maxlength', String(searchMaxLength));
        searchInput.setAttribute('aria-autocomplete', 'list');
        searchInput.setAttribute('spellcheck', 'false');

        function positionSearchResults() {
            const rect = searchInput.getBoundingClientRect();
            const top = rect.bottom + 8;
            const minWidth = 280;
            const maxWidth = Math.max(minWidth, rect.width);
            const maxLeft = Math.max(8, window.innerWidth - maxWidth - 8);
            const left = Math.min(Math.max(8, rect.left), maxLeft);
            const maxHeight = Math.max(180, window.innerHeight - top - 12);

            Object.assign(searchResults.style, {
                position: 'fixed',
                top: `${top}px`,
                left: `${left}px`,
                width: `${maxWidth}px`,
                right: 'auto',
                maxHeight: `${maxHeight}px`,
                zIndex: '9999'
            });
        }

        function openSearchResults() {
            positionSearchResults();
            searchResults.style.display = 'block';
        }

        function closeSearchResults() {
            searchResults.style.display = 'none';
        }

        function updateSearchResults(rawValue, source = 'input') {
            const validation = validateSearchQuery(rawValue, searchRole);
            const cleaned = validation.cleaned;

            if (searchInput.value !== cleaned) {
                searchInput.value = cleaned;
            }

            if (!cleaned) {
                searchResults.innerHTML = renderNotice(validation.message, searchRole);
                openSearchResults();
                return;
            }

            if (cleaned.length < 2) {
                searchResults.innerHTML = renderNotice(validation.message, searchRole);
                openSearchResults();
                return;
            }

            const query = normalizeText(cleaned);
            const shortcuts = (portalShortcuts[searchRole] || portalShortcuts.guest).filter(item => {
                const title = normalizeText(item.title);
                const hint = normalizeText(item.hint);
                return title.includes(query) || hint.includes(query);
            });

            const canUseCatalogData = searchRole !== 'admin';
            const products = canUseCatalogData ? (window.PRODUCTS_DATA || []) : [];
            const productMatches = products.filter(p => {
                const name = normalizeText(p.name);
                const category = normalizeText(p.category);
                const ref = normalizeText(p.ref);
                const productRef = normalizeText(p.product_ref);
                const exactRef = ref === query || productRef === query;
                const startsLikeCode = isCodeLikeQuery(cleaned) && (ref.startsWith(query) || productRef.startsWith(query));
                return exactRef || name.includes(query) || category.includes(query) || ref.includes(query) || productRef.includes(query) || startsLikeCode;
            }).slice(0, 5);

            const structuredHint = isCodeLikeQuery(cleaned) ? '<div class="type-body-xs mt-1" style="color: var(--brand-primary);">Structured search detected: reference lookup prioritized.</div>' : '';
            const shortcutHtml = shortcuts.slice(0, 3).map(item => `
                <a href="${item.href}" class="search-result-item">
                    <div class="search-result-info">
                        <span class="search-result-name">${item.title}</span>
                        <span class="search-result-meta">${item.hint}</span>
                    </div>
                </a>
            `).join('');

            const productsHtml = productMatches.map(p => {
                const meta = (p.category || 'Catalog') + (p.show_sku ? ' • ' + (p.ref || p.product_ref || 'Item') : '');
                return `
                <a href="${productHrefByRole(p.ref || p.product_ref, searchRole)}" class="search-result-item">
                    <img src="${p.image || p.image_url || '/static/assets/Featured.png'}" alt="${p.name}">
                    <div class="search-result-info">
                        <span class="search-result-name">${p.name}</span>
                        <span class="search-result-meta">${meta}</span>
                    </div>
                    <div class="search-result-price">₱${Number(p.price || 0).toLocaleString()}</div>
                </a>
            `}).join('');

            const hasAny = !!shortcutHtml || !!productsHtml;
            if (hasAny) {
                searchResults.innerHTML = `
                    <div style="padding:var(--sp-5) var(--sp-4); border-bottom:1px solid var(--border-subtle); color:var(--grey-500);">
                        <div class="type-body-sm fw-semibold">Search results for "${cleaned}"</div>
                        <div class="type-body-xs mt-1">${source === 'enter' ? 'Enter opened the best match.' : 'Results are prioritized by ecommerce relevance.'}</div>
                        ${validation.message ? `<div class="type-body-xs mt-1" style="color: var(--brand-primary);">${validation.message}</div>` : ''}
                        ${structuredHint}
                    </div>
                    ${shortcutHtml}${productsHtml}
                `;
            } else {
                searchResults.innerHTML = renderNoResults(cleaned, searchRole, validation.message || `No match for \"${cleaned}\"`);
            }

            openSearchResults();
        }

        searchInput.addEventListener('focus', () => {
            const query = normalizeText(searchInput.value);
            if (query.length >= 2) {
                updateSearchResults(searchInput.value, 'focus');
                return;
            }

            const shortcuts = (portalShortcuts[searchRole] || portalShortcuts.guest).slice(0, 4);
            searchResults.innerHTML = shortcuts.map(item => `
                <a href="${item.href}" class="search-result-item">
                    <div class="search-result-info">
                        <span class="search-result-name">${item.title}</span>
                        <span class="search-result-meta">${item.hint}</span>
                    </div>
                </a>
            `).join('');
            openSearchResults();
        });

        searchInput.addEventListener('input', (e) => {
            updateSearchResults(e.target.value, 'input');
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            const cleaned = sanitizeSearchQuery(searchInput.value);
            const firstResult = searchResults.querySelector('a.search-result-item');

            if (!cleaned || cleaned.length < 2) {
                searchResults.innerHTML = renderNotice('Search requires at least 2 characters.', searchRole);
                openSearchResults();
                return;
            }

            if (firstResult) {
                window.location.href = firstResult.getAttribute('href') || '/shop';
                return;
            }

            window.location.href = fallbackSearchHref(cleaned, searchRole);
        });

        // Close search results when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.topbar__search') && !e.target.closest('#topbar-search-results')) {
                closeSearchResults();
            }
        });

        window.addEventListener('resize', () => {
            if (searchResults.style.display === 'block') {
                positionSearchResults();
            }
        });

        window.addEventListener('scroll', () => {
            if (searchResults.style.display === 'block') {
                positionSearchResults();
            }
        }, { passive: true });
    }

});
