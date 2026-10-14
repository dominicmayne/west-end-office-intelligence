/*
 * The West End as an isometric model, built from the platform's own data.
 * Each submarket is a plot of four towers: tower height follows prime rent,
 * colour follows vacancy (same thresholds as the dashboard). Faces use four
 * tones (top, left, right, edge) and are drawn back to front (painter's order).
 *
 * Usage: <figure data-iso-westend> with an <svg>, a .iso-card and a .iso-chips
 * inside it. Reads /data/predictions.json and /data/forecast.json.
 */
(function () {
    const fig = document.querySelector('[data-iso-westend]');
    if (!fig) return;
    const svg = fig.querySelector('svg');
    const card = fig.querySelector('.iso-card');
    const chips = fig.querySelector('.iso-chips');
    const NS = 'http://www.w3.org/2000/svg';
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

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

    // Critically damped spring (damping 1.0, response 0.4s), sampled per frame.
    const OMEGA = (2 * Math.PI) / 0.4;
    const spring = t => 1 - (1 + OMEGA * t) * Math.exp(-OMEGA * t);

    let towers = [];   // { faces: [top, left, right], floors, x, y, h, delay }
    let selected = null;
    let plots = {};

    function drawTower(t, k) {
        const { x, y } = t, w = TOWER, h = Math.max(0.01, t.h * k);
        t.faces[0].setAttribute('points', pts([[x, y, h], [x + w, y, h], [x + w, y + w, h], [x, y + w, h]]));
        t.faces[1].setAttribute('points', pts([[x, y + w, 0], [x + w, y + w, 0], [x + w, y + w, h], [x, y + w, h]]));
        t.faces[2].setAttribute('points', pts([[x + w, y, 0], [x + w, y + w, 0], [x + w, y + w, h], [x + w, y, h]]));
        // Floor lines: invisible at 1x as texture, legible as storeys when zoomed.
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

        // Painter's order: plots, then towers, sorted by depth (x + y) from the back.
        const order = areas.slice().sort((a, b) => (LAYOUT[a][0] + LAYOUT[a][1]) - (LAYOUT[b][0] + LAYOUT[b][1]) || LAYOUT[a][0] - LAYOUT[b][0]);

        const ground = el('g', { class: 'iso-ground' });
        // The Thames runs under St James's and Victoria, then bends north into the
        // empty corner by the Embankment.
        const U = PLOT + GAP, ry = 3 * U + 6;
        ground.appendChild(el('path', { class: 'iso-river', d: `M${iso(-30, ry, 0)}L${iso(2 * U - 4, ry, 0)}Q${iso(2 * U + 30, ry, 0)} ${iso(2 * U + 40, 2 * U + 50, 0)}L${iso(3 * U + 30, 2 * U + 30, 0)}` }));
        svg.appendChild(ground);

        order.forEach((area, i) => {
            const [cx, cy] = LAYOUT[area];
            const ox = cx * (PLOT + GAP), oy = cy * (PLOT + GAP);
            const row = latest[area];
            const next = forecast && forecast.areas && forecast.areas[area] && forecast.areas[area][0];
            const g = el('g', { class: 'iso-plot', 'data-band': band(row.vacancy), tabindex: '0', role: 'button', 'aria-label': `${area}: prime rent £${row.rent_psf} per sq ft, vacancy ${row.vacancy}%` });
            g.appendChild(el('polygon', { class: 'iso-lot', points: pts([[ox, oy, 0], [ox + PLOT, oy, 0], [ox + PLOT, oy + PLOT, 0], [ox, oy + PLOT, 0]]) }));
            const shape = SHAPES[i % SHAPES.length];
            const spots = [[0, 0], [1, 0], [0, 1], [1, 1]];
            spots.forEach(([sx, sy], j) => {
                const t = {
                    x: ox + PAD + sx * (PLOT - 2 * PAD - TOWER),
                    y: oy + PAD + sy * (PLOT - 2 * PAD - TOWER),
                    h: height(row.rent_psf) * shape[j],
                    delay: i * 0.06 + j * 0.03,
                    faces: [el('polygon', { class: 'f-top' }), el('polygon', { class: 'f-left' }), el('polygon', { class: 'f-right' })],
                    floors: el('path', { class: 'f-floors' }),
                };
                t.faces.forEach(f => g.appendChild(f));
                g.appendChild(t.floors);
                towers.push(t);
            });
            plots[area] = { g, row, next };
            svg.appendChild(g);

            g.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') select(area); });
            g.addEventListener('pointerdown', () => select(area));
            g.addEventListener('click', e => { if (e.pointerType === 'mouse' || e.detail === 0) location.href = '/dashboard#' + encodeURIComponent(area); });
            g.addEventListener('focus', () => select(area));
            g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); location.href = '/dashboard#' + encodeURIComponent(area); } });

        });

        // Chips follow the map, north-west to south-east, not drawing order.
        areas.forEach(area => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'iso-chip';
            chip.dataset.area = area;
            chip.dataset.band = band(latest[area].vacancy);
            chip.textContent = area;
            chip.addEventListener('pointerdown', () => select(area));
            chip.addEventListener('click', () => select(area));
            chips.appendChild(chip);
        });

        // Fit the viewBox to what was drawn.
        towers.forEach(t => drawTower(t, 1));
        const box = svg.getBBox();
        svg.setAttribute('viewBox', `${(box.x - 8).toFixed(0)} ${(box.y - 8).toFixed(0)} ${(box.width + 16).toFixed(0)} ${(box.height + 16).toFixed(0)}`);

        if (reduce) return;
        towers.forEach(t => drawTower(t, 0));
        const start = performance.now();
        (function frame(now) {
            const s = (now - start) / 1000;
            let moving = false;
            towers.forEach(t => {
                const local = Math.max(0, s - t.delay);
                const k = spring(local);
                if (k < 0.999) moving = true;
                drawTower(t, k);
            });
            if (moving) requestAnimationFrame(frame);
            else towers.forEach(t => drawTower(t, 1));
        })(start);
    }

    function select(area) {
        const p = plots[area];
        if (!p || selected === area) return;
        selected = area;
        fig.classList.add('has-selection');
        Object.entries(plots).forEach(([a, q]) => q.g.classList.toggle('is-selected', a === area));
        chips.querySelectorAll('.iso-chip').forEach(c => c.setAttribute('aria-pressed', c.dataset.area === area));
        const esc = window.SiteData ? SiteData.esc : String;
        const next = p.next ? `<div><dt>Forecast ${esc(p.next.year)} ${esc(p.next.quarter)}</dt><dd>${p.next.vacancy.toFixed(1)}%</dd></div>` : '';
        card.innerHTML = `
            <div class="iso-card-top"><span class="iso-dot" data-band="${band(p.row.vacancy)}"></span><strong>${esc(area)}</strong><span class="iso-when">${esc(p.row.year)} ${esc(p.row.quarter)}</span></div>
            <dl>
                <div><dt>Prime rent</dt><dd>£${esc(p.row.rent_psf)}<small> psf</small></dd></div>
                <div><dt>Vacancy</dt><dd>${p.row.vacancy.toFixed(1)}%</dd></div>
                ${next}
            </dl>
            <a class="link" href="/dashboard#${encodeURIComponent(area)}">Open ${esc(area)} in the platform</a>`;
    }

    Promise.all([
        fetch('/data/predictions.json').then(r => r.json()),
        fetch('/data/forecast.json').then(r => r.json()).catch(() => null),
    ]).then(([rows, forecast]) => {
        build(rows, forecast);
        const top = Object.values(plots).sort((a, b) => b.row.rent_psf - a.row.rent_psf)[0];
        if (top) select(top.row.area);
    }).catch(() => fig.classList.add('is-empty'));
})();
