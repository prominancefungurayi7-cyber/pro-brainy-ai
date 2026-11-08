(() => {
    const root = document.documentElement;
    const sidebar = document.getElementById('app-sidebar');
    const toggle = document.getElementById('sidebar-toggle');
    const close = document.getElementById('sidebar-close');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar || !toggle || !close || !backdrop) return;

    const mobile = window.matchMedia('(max-width: 900px)');

    function update() {
        const expanded = mobile.matches
            ? root.classList.contains('sidebar-open')
            : !root.classList.contains('sidebar-collapsed');
        toggle.setAttribute('aria-expanded', String(expanded));
        toggle.setAttribute('aria-label', expanded ? 'Close sidebar' : 'Open sidebar');
        sidebar.inert = mobile.matches && !expanded;
        backdrop.tabIndex = mobile.matches && expanded ? 0 : -1;
        document.body.classList.toggle('navigation-open', mobile.matches && expanded);
    }

    function closeMobile() {
        if (!mobile.matches) return;
        root.classList.remove('sidebar-open');
        update();
        toggle.focus();
    }

    toggle.addEventListener('click', () => {
        if (mobile.matches) {
            const opening = !root.classList.contains('sidebar-open');
            root.classList.toggle('sidebar-open', opening);
            update();
            if (opening) sidebar.querySelector('.nav-link')?.focus();
        } else {
            const collapsed = root.classList.toggle('sidebar-collapsed');
            try { localStorage.setItem('pro-brainy-sidebar', collapsed ? 'collapsed' : 'expanded'); } catch (error) {}
            update();
        }
    });
    close.addEventListener('click', closeMobile);
    backdrop.addEventListener('click', closeMobile);
    sidebar.addEventListener('click', (event) => {
        if (event.target.closest('a')) closeMobile();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && root.classList.contains('sidebar-open')) closeMobile();
        if (event.key === 'Tab' && mobile.matches && root.classList.contains('sidebar-open')) {
            const focusable = [...sidebar.querySelectorAll('a, button:not([disabled])')];
            if (!focusable.length) return;
            if (event.shiftKey && document.activeElement === focusable[0]) {
                event.preventDefault();
                focusable[focusable.length - 1].focus();
            } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
                event.preventDefault();
                focusable[0].focus();
            }
        }
    });
    mobile.addEventListener('change', () => {
        root.classList.remove('sidebar-open');
        update();
    });
    update();
})();
