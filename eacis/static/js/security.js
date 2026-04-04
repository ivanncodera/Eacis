/* ============================================
   E-ACIS SESSION & SECURITY SYSTEM
   ============================================ */

(function(){
    let idleTimer;
    let warningTimer;
    const IDLE_TIME = 9 * 60 * 1000; // 9 minutes for warning
    const LOGOUT_TIME = 10 * 60 * 1000; // 10 minutes total for logout

    function resetTimers() {
        clearTimeout(idleTimer);
        clearTimeout(warningTimer);
        
        // Only track for authenticated users
        if (!window.EACIS || !window.EACIS.is_authenticated) return;

        idleTimer = setTimeout(showIdleWarning, IDLE_TIME);
        warningTimer = setTimeout(autoLogout, LOGOUT_TIME);
    }

    function showIdleWarning() {
        if (!window.ModalManager) return;

        const content = document.createElement('div');
        content.className = 'modal modal--sm';
        content.innerHTML = `
            <div class="modal__header" style="background: var(--color-warning-subtle); border-bottom: 0; padding: var(--sp-8) var(--sp-6) var(--sp-4);">
                <div class="modal__title" style="display:flex; align-items:center; gap:var(--sp-2);">
                   <svg width="20" height="20" fill="none" stroke="var(--color-warning)" stroke-width="2" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                   <span>Session Security</span>
                </div>
            </div>
            <div class="modal__body" style="padding: var(--sp-6); background: white;">
                <p class="type-body-sm mb-6" style="color: var(--grey-600);">You've been inactive for 9 minutes. For your safety, we'll log you out soon.</p>
                
                <!-- Visual Countdown -->
                <div style="margin-bottom: var(--sp-6); background: var(--surface-sunken); height: 8px; border-radius: 4px; overflow: hidden; position: relative;">
                    <div id="idle-progress" style="position: absolute; top: 0; left: 0; height: 100%; width: 100%; background: var(--color-warning); transition: width 1s linear;"></div>
                </div>
                <div class="type-label-xs mb-8" style="text-align: center; color: var(--color-warning); font-weight: 800;">
                    AUTO-LOGOUT IN <span id="idle-countdown">60</span>s
                </div>

                <div style="display:flex; flex-direction:column; gap:var(--sp-3);">
                    <button class="btn btn--primary btn--lg" style="width:100%;" id="idle-stay">Keep My Session Active</button>
                    <button class="btn btn--ghost btn--sm" style="width:100%;" id="idle-logout">Sign Out Now</button>
                </div>
            </div>
        `;

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.appendChild(content);
        document.body.appendChild(overlay);

        ModalManager.open(content);

        let secondsLeft = 60;
        const interval = setInterval(() => {
            secondsLeft--;
            const countEl = content.querySelector('#idle-countdown');
            const progEl = content.querySelector('#idle-progress');
            if(countEl) countEl.textContent = secondsLeft;
            if(progEl) progEl.style.width = (secondsLeft / 60 * 100) + '%';
            
            if(secondsLeft <= 0) {
                clearInterval(interval);
                autoLogout();
            }
        }, 1000);

        content.querySelector('#idle-stay').onclick = () => {
            clearInterval(interval);
            ModalManager.close(content);
            resetTimers();
        };
        content.querySelector('#idle-logout').onclick = () => {
            clearInterval(interval);
            autoLogout();
        };
    }

    function autoLogout() {
        console.warn('Session expired - Logging out...');
        window.location.href = '/auth/logout?reason=expired';
    }

    // List of events to reset idle timer
    ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(evt => {
        document.addEventListener(evt, resetTimers, { passive: true });
    });

    // Start timers initially
    resetTimers();

})();
