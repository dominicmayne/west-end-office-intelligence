// RideWorld pilot connection. Leave both blank and every page stays in demo mode.
// Fill them from Supabase > Project Settings > API. The anon key is meant to be public:
// row-level security in supabase/schema.sql decides what it can do.
const QRW = {
  url: '',
  key: '',
  get on() { return !!(this.url && this.key); },
  token() { try { const s = JSON.parse(localStorage.getItem('qrw-session') || 'null'); return s && s.exp > Date.now() / 1000 ? s.token : null; } catch (e) { return null; } },
  async api(path, opts = {}) {
    const r = await fetch(this.url + path, { ...opts, headers: { apikey: this.key, Authorization: 'Bearer ' + (this.token() || this.key), 'Content-Type': 'application/json', ...opts.headers } });
    const text = await r.text();
    if (!r.ok) throw new Error(text || r.status);
    return text ? JSON.parse(text) : null;
  },
  ride(id) { return this.api('/rest/v1/rides?select=*&id=eq.' + encodeURIComponent(id)).then((rows) => rows[0] || null); },
  report(ride_id, issue) { return this.api('/rest/v1/faults', { method: 'POST', headers: { Prefer: 'return=minimal' }, body: JSON.stringify({ ride_id, issue }) }); },
  scan(ride_id) { return this.api('/rest/v1/scans', { method: 'POST', headers: { Prefer: 'return=minimal' }, body: JSON.stringify({ ride_id }) }); },
};
