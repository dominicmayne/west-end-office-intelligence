/*
 * The West End as an isometric model, built from the platform's own data.
 * Each submarket is a plot of four towers: tower height follows prime rent,
 * colour follows vacancy (same thresholds as the dashboard). Faces use four
 * tones (top, left, right, edge) and are drawn back to front (painter's order).
 *
 * Markup: <figure data-iso-westend> holding an <svg> and an optional .iso-card.
 * Inside a [data-scene] (see motion.js) the model is driven by scroll:
 *   0.00–0.18  empty lots
 *   0.18–0.55  towers rise, lowest rent first
 *   0.50–0.72  vacancy colour floods in
 *   0.78+      a submarket card appears and the blocks become clickable
 * Captions inside the scene with data-from/data-to fade in over that range.
 * Reads /data/predictions.json and /data/forecast.json.
 */
(function () {
    const fig = document.querySelector('[data-iso-westend]');
    if (!fig) return;
    const svg = fig.querySelector('svg');
    const card = fig.querySelector('.iso-card');
    const scene = fig.closest('[data-scene]');
    const NS = 'http://www.w3.org/2000/svg';
    const range = (p, a, b) => Math.min(1, Math.max(0, (p - a) / (b - a)));

    // Same arrangement as the dashboard's schematic: north is up-right.
    const LAYOUT = {
        'Marylebone': [0, 0], 'Fitzrovia': [1, 0], 'Midtown': [2, 0],
        'Mayfair': [0, 1], 'Soho': [1, 1], 'Covent Garden': [2, 1],
        "St James's": [0, 2], 'Victoria': [1, 2],
    };
    const PLOT = 100, GAP = 16, PAD = 10, TOWER = 36;
    const COS = Math.cos(Math.PI / 6), SIN = 0.5;
    // Tower heights within a plot, back tower first, so each block reads as a skyline not a slab.
    const SHAPES = [[1, 0.78, 0.66, 0.5], [0.84, 1, 0.58, 0.7], [1, 0.62, 0.8, 0.52]];

    const iso = (x, y, z) => [(x - y) * COS, (x + y) * SIN - z];
    const pts = list => list.map(p => iso(...p).map(n => n.toFixed(1)).join(',')).join(' ');
    const band = v => (v < 5 ? 'good' : v < 7 ? 'warn' : 'bad');
    const el = (name, attrs) => {
        const n = document.createElementNS(NS, name);
        for (const k in attrs) n.setAttribute(k, attrs[k]);
        return n;
    };

    const towers = [];   // { faces, floors, x, y, h, start }
    const plots = {};
    let selected = null, interactive = !scene;

    function drawTower(t, k) {
        const { x, y } = t, w = TOWER, h = Math.max(0.01, t.h * k);
        t.faces[0].setAttribute('points', pts([[x, y, h], [x + w, y, h], [x + w, y + w, h], [x, y + w, h]]));
        t.faces[1].setAttribute('points', pts([[x, y + w, 0], [x + w, y + w, 0], [x + w, y + w, h], [x, y + w, h]]));
        t.faces[2].setAttribute('points', pts([[x + w, y, 0], [x + w, y + w, 0], [x + w, y + w, h], [x + w, y, h]]));
        // Floor lines: texture at 1x, legible storeys when zoomed in.
        let d = '';
        for (let z = 7; z < h - 3; z += 7) {
            const a = iso(x, y + w, z), b = iso(x + w, y + w, z), c = iso(x + w, y, z);
            d += `M${a[0].toFixed(1)},${a[1].toFixed(1)}L${b[0].toFixed(1)},${b[1].toFixed(1)}L${c[0].toFixed(1)},${c[1].toFixed(1)}`;
        }
        t.floors.setAttribute('d', d);
    }

    function build(rows, forecast) {
        const latest = {};
        rows.forEach(r => { latest[r.area] = r; }); // rows are in time order per area
        const areas = Object.keys(LAYOUT).filter(a => latest[a]);
        const rents = areas.map(a => latest[a].rent_psf);
        const lo = Math.min(...rents), hi = Math.max(...rents);
        const height = r => 46 + ((r - lo) / (hi - lo || 1)) * 128;
        const byRent = areas.slice().sort((a, b) => latest[a].rent_psf - latest[b].rent_psf);

        // Painter's order: sorted by depth (x + y) from the back.
        const order = areas.slice().sort((a, b) => (LAYOUT[a][0] + LAYOUT[a][1]) - (LAYOUT[b][0] + LAYOUT[b][1]) || LAYOUT[a][0] - LAYOUT[b][0]);

        // The Thames runs under St James's and Victoria, then bends north into
        // the empty corner by the Embankment.
        const U = PLOT + GAP, ry = 3 * U + 6;
        svg.appendChild(el('path', { class: 'iso-river', d: `M${iso(-30, ry, 0)}L${iso(2 * U - 4, ry, 0)}Q${iso(2 * U + 30, ry, 0)} ${iso(2 * U + 40, 2 * U + 50, 0)}L${iso(3 * U + 30, 2 * U + 30, 0)}` }));

        order.forEach((area, i) => {
            const [cx, cy] = LAYOUT[area];
            const ox = cx * U, oy = cy * U;
            const row = latest[area];
            const next = forecast && forecast.areas && forecast.areas[area] && forecast.areas[area][0];
            const g = el('g', { class: 'iso-plot', 'data-band': band(row.vacancy), tabindex: '0', role: 'link', 'aria-label': `${area}: prime rent £${row.rent_psf} per sq ft, vacancy ${row.vacancy}%. Open in the platform.` });
            g.appendChild(el('polygon', { class: 'iso-lot', points: pts([[ox, oy, 0], [ox + PLOT, oy, 0], [ox + PLOT, oy + PLOT, 0], [ox, oy + PLOT, 0]]) }));
            const shape = SHAPES[i % SHAPES.length];
            [[0, 0], [1, 0], [0, 1], [1, 1]].forEach(([sx, sy], j) => {
                const t = {
                    x: ox + PAD + sx * (PLOT - 2 * PAD - TOWER),
                    y: oy + PAD + sy * (PLOT - 2 * PAD - TOWER),
                    h: height(row.rent_psf) * shape[j],
                    // Cheapest submarket rises first, so the climb ends on Mayfair.
                    start: byRent.indexOf(area) * 0.04 + j * 0.012,
                    faces: [el('polygon', { class: 'f-top' }), el('polygon', { class: 'f-left' }), el('polygon', { class: 'f-right' })],
                    floors: el('path', { class: 'f-floors' }),
                };
                t.faces.forEach(f => g.appendChild(f));
                g.appendChild(t.floors);
                towers.push(t);
            });
            plots[area] = { g, row, next };
            svg.appendChild(g);

            const open = () => { location.href = '/west-end#' + encodeURIComponent(area); };
            g.addEventListener('pointerenter', e => { if (interactive && e.pointerType === 'mouse') select(area); });
            g.addEventListener('pointerdown', () => { if (interactive) select(area); });
            g.addEventListener('click', e => { if (interactive && (e.pointerType === 'mouse' || e.detail === 0 || selected === area)) open(); });
            g.addEventListener('focus', () => select(area));
            g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
        });

        // Fit the viewBox to the finished model, so nothing shifts as it grows.
        towers.forEach(t => drawTower(t, 1));
        const box = svg.getBBox();
        svg.setAttribute('viewBox', `${(box.x - 8).toFixed(0)} ${(box.y - 8).toFixed(0)} ${(box.width + 16).toFixed(0)} ${(box.height + 16).toFixed(0)}`);

        const top = byRent[byRent.length - 1], weakest = areas.slice().sort((a, b) => latest[b].vacancy - latest[a].vacancy)[0];
        fig.dispatchEvent(new CustomEvent('iso:ready', { detail: { top: latest[top], weakest: latest[weakest] } }));

        if (scene && window.Motion) {
            Motion.onScene(scene, p => render(p, top));
        } else {
            render(1, top);
        }
    }

    function render(p, top) {
        const rise = range(p, 0.18, 0.55);
        towers.forEach(t => drawTower(t, easeOut(range(rise, t.start, t.start + 0.55))));
        fig.style.setProperty('--sat', (range(p, 0.5, 0.72) * 100).toFixed(1) + '%');
        const ready = p > 0.78;
        if (ready !== interactive) {
            interactive = ready;
            fig.classList.toggle('is-live', ready);
            if (ready && !selected) select(top);
            if (!ready) clearSelection();
        }
    }
    // Ease the per-tower climb so each one lands softly; the scroll spring handles the rest.
    const easeOut = k => 1 - Math.pow(1 - k, 3);

    function clearSelection() {
        selected = null;
        fig.classList.remove('has-selection');
        Object.values(plots).forEach(q => q.g.classList.remove('is-selected'));
    }

    function select(area) {
        const p = plots[area];
        if (!p || selected === area) return;
        selected = area;
        fig.classList.add('has-selection');
        Object.entries(plots).forEach(([a, q]) => q.g.classList.toggle('is-selected', a === area));
        if (!card) return;
        const esc = window.SiteData ? SiteData.esc : String;
        const next = p.next ? `<div><dt>Forecast ${esc(p.next.year)} ${esc(p.next.quarter)}</dt><dd>${p.next.vacancy.toFixed(1)}%</dd></div>` : '';
        card.innerHTML = `
            <div class="iso-card-top"><span class="iso-dot" data-band="${band(p.row.vacancy)}"></span><strong>${esc(area)}</strong><span class="iso-when">${esc(p.row.year)} ${esc(p.row.quarter)}</span></div>
            <dl>
                <div><dt>Prime rent</dt><dd>£${esc(p.row.rent_psf)}<small> psf</small></dd></div>
                <div><dt>Vacancy</dt><dd>${p.row.vacancy.toFixed(1)}%</dd></div>
                ${next}
            </dl>
            <a class="link" href="/west-end#${encodeURIComponent(area)}">Open ${esc(area)} in the platform</a>`;
    }

    Promise.all([
        fetch('/data/predictions.json').then(r => r.json()),
        fetch('/data/forecast.json').then(r => r.json()).catch(() => null),
    ]).then(([rows, forecast]) => build(rows, forecast))
      .catch(() => fig.classList.add('is-empty'));
})();
