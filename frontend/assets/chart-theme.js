/*
 * Chart.js defaults matching assets/site.css (paper, ink, brick accent).
 * Load after Chart.js. Safe to load when Chart.js was blocked.
 */
(function () {
    const T = {
        ink: '#1c1b18',
        ink2: '#45413a',
        ink3: '#6f695d',
        rule: '#d3cbb8',
        grid: 'rgba(28,27,24,0.08)',
        paper: '#f4f0e6',
        accent: '#b0482a',
        accentSoft: 'rgba(176,72,42,0.10)',
        stone: '#a89f8a',
        good: '#4c7148',
        warn: '#b98222',
        bad: '#b0482a',
        sans: "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif",
        mono: "'IBM Plex Mono', ui-monospace, Menlo, monospace",
    };
    window.ChartTheme = T;
    if (typeof window.Chart === 'undefined') return;
    const d = Chart.defaults;
    d.font.family = T.sans;
    d.font.size = 12;
    d.color = T.ink3;
    d.borderColor = T.grid;
    d.plugins.legend.align = 'start';
    d.plugins.legend.labels.boxWidth = 10;
    d.plugins.legend.labels.boxHeight = 10;
    d.plugins.legend.labels.color = T.ink2;
    d.plugins.legend.labels.padding = 14;
    d.plugins.tooltip.backgroundColor = T.ink;
    d.plugins.tooltip.titleColor = T.paper;
    d.plugins.tooltip.bodyColor = T.paper;
    d.plugins.tooltip.titleFont = { family: T.mono, size: 11, weight: '500' };
    d.plugins.tooltip.bodyFont = { family: T.sans, size: 12 };
    d.plugins.tooltip.cornerRadius = 2;
    d.plugins.tooltip.padding = 10;
    d.plugins.tooltip.boxPadding = 4;
    d.elements.line.borderWidth = 2;
    d.elements.point.radius = 0;
    d.elements.point.hoverRadius = 4;
    d.elements.bar.borderRadius = 0;
    // Taller charts on phones so axis labels stay readable.
    if (window.matchMedia && window.matchMedia('(max-width: 640px)').matches) d.aspectRatio = 1.25;

    /** Axis config used across pages: quiet grid, no axis border. */
    T.axis = function (extra) {
        return Object.assign({
            ticks: { color: T.ink3, maxRotation: 0, autoSkip: true },
            grid: { color: T.grid, drawTicks: false },
            border: { display: false },
        }, extra || {});
    };
})();
