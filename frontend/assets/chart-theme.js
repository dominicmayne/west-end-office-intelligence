/*
 * Chart.js defaults read from the CSS tokens in assets/site.css, so charts
 * follow the light or dark theme. Load after Chart.js. Safe to load when
 * Chart.js was blocked.
 * Shortcut: colours are read once on load; switching the system theme while
 * a page is open needs a reload to recolour the charts.
 */
(function () {
    const css = getComputedStyle(document.documentElement);
    const v = name => css.getPropertyValue(name).trim();
    const T = {
        ink: v('--ink'),
        ink2: v('--ink-2'),
        ink3: v('--ink-3'),
        rule: v('--rule'),
        grid: v('--grid'),
        paper: v('--paper'),
        paper3: v('--paper-3'),
        surface: v('--surface'),
        accent: v('--accent'),
        accentSoft: v('--accent-wash'),
        stone: v('--ink-3'),
        good: v('--good'),
        warn: v('--warn'),
        bad: v('--bad'),
        sans: v('--sans'),
        mono: v('--mono'),
    };
    window.ChartTheme = T;
    if (typeof window.Chart === 'undefined') return;
    const d = Chart.defaults;
    d.font.family = T.sans;
    d.font.size = 12;
    d.color = T.ink3;
    d.borderColor = T.grid;
    d.plugins.legend.align = 'start';
    d.plugins.legend.labels.boxWidth = 8;
    d.plugins.legend.labels.boxHeight = 8;
    d.plugins.legend.labels.usePointStyle = true;
    d.plugins.legend.labels.color = T.ink2;
    d.plugins.legend.labels.padding = 14;
    d.plugins.tooltip.backgroundColor = T.ink;
    d.plugins.tooltip.titleColor = T.paper;
    d.plugins.tooltip.bodyColor = T.paper;
    d.plugins.tooltip.titleFont = { family: T.sans, size: 12, weight: '600' };
    d.plugins.tooltip.bodyFont = { family: T.sans, size: 12 };
    d.plugins.tooltip.cornerRadius = 10;
    d.plugins.tooltip.padding = 10;
    d.plugins.tooltip.boxPadding = 4;
    d.elements.line.borderWidth = 2;
    d.elements.line.tension = 0.3;
    d.elements.point.radius = 0;
    d.elements.point.hoverRadius = 4;
    d.elements.bar.borderRadius = 4;
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
