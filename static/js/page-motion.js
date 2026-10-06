/* Additive, page-aware presentation. Never changes content or application state. */
(() => {
    const root = document.getElementById('main-content');
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!root || preference.matches || !window.IntersectionObserver || !Element.prototype.animate) return;

    const path = window.location.pathname;
    const profiles = {
        landing: { selector: 'section > .grid > article, section > .grid > div.reveal, #playground, section > .grid > .surface', distance: 20, duration: 560, stagger: 65 },
        docs: { selector: ':scope > div > h1, #authentication, #base-url, #endpoints > .mb-10, #examples > .space-y-8 > div, #plan-limits .glass', distance: 12, duration: 430, stagger: 50 },
        auth: { selector: '.auth-grid, .auth-card, .account-form-panel, .mfa-option', distance: 10, duration: 400, stagger: 40 },
        workspace: { selector: 'h1, .dashboard-card, .stat-card, .metric-card, .panel, .surface, .welcome-panel, table', distance: 10, duration: 380, stagger: 45 },
        billing: { selector: 'h1, .glass, .glass-panel, .surface, .migrated-plan, #main-content form', distance: 16, duration: 460, stagger: 70 },
        support: { selector: 'h1, .glass-panel, .glass, .faq-item, #ai-support, #faq-section, .content-panel', distance: 8, duration: 350, stagger: 35 },
        company: { selector: 'h1, section, .content-panel', distance: 18, duration: 520, stagger: 65 },
        reading: { selector: 'h1, h2, .content-panel, .template-archive-item', distance: 0, duration: 400, stagger: 25 },
        general: { selector: 'h1, article, section, .surface, .glass, .glass-panel, .panel, .content-panel', distance: 12, duration: 440, stagger: 45 },
    };
    let name = 'general';
    if (root.querySelector('.ticker-track')) name = 'landing';
    else if (root.querySelector('#authentication') && root.querySelector('#examples')) name = 'docs';
    else if (root.querySelector('.auth-grid') || /^\/(accounts|account\/email|socialaccount)/.test(path)) name = 'auth';
    else if (/^\/(billing|pricing)/.test(path)) name = 'billing';
    else if (/^\/(faq|support)/.test(path)) name = 'support';
    else if (/^\/about/.test(path)) name = 'company';
    else if (/^\/(privacy|terms|template-reference)/.test(path)) name = 'reading';
    else if (/^\/(dashboard|profile|account|analytics|usage-logs|audit|teams|webhooks|playground)/.test(path)) name = 'workspace';
    root.dataset.pageMotion = name;
    const profile = profiles[name];
    const seen = new WeakSet();
    const running = new Set();
    const excluded = '.reveal, .float-card, [role="dialog"], [aria-live], .faq-answer, #swagger-ui';
    const play = (element, delay = 0, distance = profile.distance) => {
        if (preference.matches || document.hidden || !element.isConnected) return;
        const animation = element.animate([
            { opacity: 0, transform: `translateY(${distance}px)` },
            { opacity: 1, transform: 'translateY(0)' },
        ], { duration: profile.duration, delay, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'backwards' });
        running.add(animation);
        animation.finished.then(() => running.delete(animation), () => running.delete(animation));
    };
    const observer = new IntersectionObserver(entries => {
        let position = 0;
        for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            observer.unobserve(entry.target);
            play(entry.target, Math.min(position++ * profile.stagger, 240));
        }
    }, { threshold: 0, rootMargin: '0px 0px -24px 0px' });

    const register = () => {
        const candidates = Array.from(root.querySelectorAll(profile.selector))
            .filter(element => !element.closest(excluded) && !seen.has(element));
        const selected = new Set(candidates);
        for (const element of candidates) {
            let parent = element.parentElement;
            let nested = false;
            while (parent && parent !== root) {
                if (selected.has(parent)) { nested = true; break; }
                parent = parent.parentElement;
            }
            seen.add(element);
            if (!nested) observer.observe(element);
        }
    };
    register();

    // New API-key cards and similar UI may appear after an existing action.
    let queued = false;
    const changes = new MutationObserver(records => {
        if (!records.some(record => record.addedNodes.length) || queued) return;
        queued = true;
        requestAnimationFrame(() => { queued = false; register(); });
    });
    changes.observe(root, { childList: true, subtree: true });

    preference.addEventListener('change', event => {
        if (!event.matches) return;
        observer.disconnect();
        changes.disconnect();
        for (const animation of running) animation.cancel();
        running.clear();
    });
})();
