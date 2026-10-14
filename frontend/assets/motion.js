/*
 * Scroll-linked motion, Apple launch-page style.
 *
 * [data-scene]   A tall section with a sticky stage inside. Its progress (0 at
 *                the top of the section, 1 when its end reaches the bottom of
 *                the viewport) is written to the CSS variable --p and passed to
 *                any handler registered with Motion.onScene(el, fn).
 * [data-reveal]  Anything that should settle into place as it enters the
 *                viewport. Writes --r (0 just below the fold, 1 once a quarter
 *                of the way up) for CSS to use in transforms and opacity.
 *
 * Scroll position is a target, not the value shown: each value chases its
 * target on a critically damped spring (damping 1.0, response 0.35s), so
 * motion is smooth on jumpy wheels and any change mid-flight carries on from
 * where it is on screen. With reduced motion the values snap to the target.
 */
(function () {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const OMEGA = (2 * Math.PI) / 0.35;
    const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
    const items = [];

    function track(el, kind) {
        const item = { el, kind, x: null, v: 0, target: 0, handlers: [] };
        items.push(item);
        return item;
    }

    function measure(item) {
        const r = item.el.getBoundingClientRect();
        const vh = window.innerHeight;
        if (item.kind === 'scene') {
            const run = r.height - vh;
            item.target = run > 0 ? clamp(-r.top / run) : clamp((vh - r.top) / (vh + r.height));
        } else {
            item.target = clamp((vh - r.top) / (vh * 0.35));
        }
    }

    function write(item) {
        const name = item.kind === 'scene' ? '--p' : '--r';
        item.el.style.setProperty(name, item.x.toFixed(4));
        item.handlers.forEach(fn => fn(item.x));
    }

    let last = 0, running = false;
    function frame(now) {
        const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
        last = now;
        let moving = false;
        items.forEach(item => {
            measure(item);
            if (item.x === null || reduce) {
                item.x = item.target;
                item.v = 0;
            } else {
                // Semi-implicit Euler on x'' = ω²(target − x) − 2ωx'.
                item.v += (OMEGA * OMEGA * (item.target - item.x) - 2 * OMEGA * item.v) * dt;
                item.x += item.v * dt;
                if (Math.abs(item.target - item.x) < 0.0005 && Math.abs(item.v) < 0.001) {
                    item.x = item.target;
                    item.v = 0;
                } else {
                    moving = true;
                }
            }
            write(item);
        });
        running = moving;
        if (moving) requestAnimationFrame(frame);
    }

    function kick() {
        if (running) return;
        running = true;
        last = performance.now();
        requestAnimationFrame(frame);
    }

    document.querySelectorAll('[data-scene]').forEach(el => { el._motion = track(el, 'scene'); });
    document.querySelectorAll('[data-reveal]').forEach(el => { el._motion = track(el, 'reveal'); });
    addEventListener('scroll', kick, { passive: true });
    addEventListener('resize', kick);
    kick();

    window.Motion = {
        onScene(el, fn) {
            const item = el._motion || (el._motion = track(el, 'scene'));
            item.handlers.push(fn);
            if (item.x !== null) fn(item.x);
            kick();
        },
        // Maps p from [a, b] to [0, 1], clamped. Handy for staging a scene.
        range: (p, a, b) => clamp((p - a) / (b - a)),
    };
})();
