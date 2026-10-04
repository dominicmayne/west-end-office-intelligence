/*
 * Shared data loader for the dashboards.
 *
 * Every page tries the live API first with a short timeout. If the API is
 * down, slow or unreachable it falls back to the snapshot files in /data/
 * (built by scripts/build_snapshot.py), so the stats pages never sit blank.
 */
(function () {
    const API = 'https://west-end-office-intelligence-production.up.railway.app';
    const TIMEOUT_MS = 4000;
    let apiState = 'unknown'; // 'live' | 'offline' | 'unknown'

    async function fetchJSON(url, timeout) {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), timeout || TIMEOUT_MS);
        try {
            const res = await fetch(url, { signal: ctrl.signal });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return await res.json();
        } finally {
            clearTimeout(timer);
        }
    }

    // Snapshot files are fetched once and reused.
    const snapCache = {};
    function snapshot(file) {
        if (!snapCache[file]) {
            snapCache[file] = fetchJSON('/data/' + file, 10000).catch(err => {
                delete snapCache[file];
                throw err;
            });
        }
        return snapCache[file];
    }

    /**
     * Load data, live first, then snapshot.
     *   apiPath:   e.g. '/predictions'
     *   file:      snapshot file name in /data/
     *   pick:      optional function to pull one entry out of the snapshot
     *   validate:  optional function; a live response failing it uses the snapshot
     * Resolves to { data, source: 'live' | 'snapshot' }.
     */
    async function load(apiPath, file, pick, validate) {
        if (apiState !== 'offline') {
            try {
                const data = await fetchJSON(API + apiPath);
                if (!validate || validate(data)) {
                    apiState = 'live';
                    return { data, source: 'live' };
                }
            } catch (e) {
                apiState = 'offline';
            }
        }
        const snap = await snapshot(file);
        return { data: pick ? pick(snap) : snap, source: 'snapshot' };
    }

    async function meta() {
        try { return await snapshot('meta.json'); } catch (e) { return null; }
    }

    function esc(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function formatDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d)) return iso;
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    window.SiteData = {
        API,
        load,
        meta,
        esc,
        formatDate,
        fetchJSON,
        isLive: () => apiState === 'live',
        isOffline: () => apiState === 'offline',
        hasCharts: () => typeof window.Chart !== 'undefined',
    };
})();
