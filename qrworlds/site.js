// Fade sections in as they scroll into view
const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add('in'), io.unobserve(e.target))), { threshold: 0.12 });
document.querySelectorAll('.rv').forEach((el) => io.observe(el));

// Hero: a real QR code for this site whose squares lift into little 3D blocks and settle back.
// Drawn on one 2D canvas, only while it is on screen, so it costs almost nothing.
const qc = document.getElementById('qrc');
if (qc && window.qrcode) {
  const q = qrcode(0, 'M'); q.addData('HTTPS://WWW.QRWORLDS.CO.UK', 'Alphanumeric'); q.make();
  const n = q.getModuleCount(), pad = 2, N = n + pad * 2;
  const cols = ['#ff3b30', '#ffd60a', '#34c759', '#0a84ff', '#ff9f0a', '#bf5af2', '#ff2d92'];
  const shade = (hex, k) => { const v = parseInt(hex.slice(1), 16); return `rgb(${((v >> 16) & 255) * k | 0},${((v >> 8) & 255) * k | 0},${(v & 255) * k | 0})`; };
  const blocks = [];
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
    if (!q.isDark(r, c)) continue;
    const d = Math.hypot(r - n / 2 + 0.5, c - n / 2 + 0.5) / (n / 2);
    const col = cols[(r * 7 + c * 3) % cols.length];
    blocks.push({ x: c + pad - N / 2, y: r + pad - N / 2, h: 0.35 + (1 - d) * 2.2 + Math.random() * 0.9, delay: d * 0.35, top: col, s1: shade(col, 0.72), s2: shade(col, 0.52) });
  }
  const g = qc.getContext('2d'), cap = document.getElementById('qrcap');
  let W = 0, scale = 1;
  const size = () => { const dpr = Math.min(devicePixelRatio || 1, 2); W = qc.clientWidth * dpr; qc.width = qc.height = W; scale = W / (N * 1.25); };
  size(); addEventListener('resize', size);
  const ease = (x) => (x = Math.min(Math.max(x, 0), 1), x * x * (3 - 2 * x));
  const back = (x) => { x = Math.min(Math.max(x, 0), 1); const c1 = 1.5; return 1 + (c1 + 1) * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  const LOOP = 7.2; // flat 1.2s, rise 1.6s, hold 2.2s, settle 1.4s, flat 0.8s
  function draw(t) {
    const k = t % LOOP;
    const p = k < 1.2 ? 0 : k < 2.8 ? ease((k - 1.2) / 1.6) : k < 5 ? 1 : k < 6.4 ? 1 - ease((k - 5) / 1.4) : 0;
    const rising = k < 5;
    const th = -0.63 * p, ph = 0.95 * p, ct = Math.cos(th), st = Math.sin(th), cp = Math.cos(ph), sp = Math.sin(ph);
    const zs = 0.9 * p; // block height scale grows with the tilt
    const proj = (x, y, z) => { const rx = x * ct - y * st, ry = x * st + y * ct; return [W / 2 + rx * scale, W / 2 + (ry * cp - z * sp) * scale + p * W * 0.06]; };
    g.clearRect(0, 0, W, W);
    // the white card
    const h0 = N / 2;
    const card = (dy, grow) => { g.beginPath(); [[-h0, -h0], [h0, -h0], [h0, h0], [-h0, h0]].forEach(([x, y], i) => { const [a, b] = proj(x * grow, y * grow, 0); i ? g.lineTo(a, b + dy) : g.moveTo(a, b + dy); }); g.closePath(); };
    // soft shadow from two offset fills (canvas blur is slow on phones), then the card and its edge
    g.fillStyle = 'rgba(0,0,0,0.18)'; card(W * 0.035, 1.04); g.fill(); card(W * 0.02, 1.01); g.fill();
    g.fillStyle = '#d9d9e3'; card(W * 0.012 * p, 1); g.fill();
    g.fillStyle = '#fff'; card(0, 1); g.fill();
    // side faces that point at the viewer, from the four outward normals
    const sides = [[0, 1, 0, 1, 1, 1], [1, 0, 1, 0, 1, 1], [0, -1, 0, 0, 1, 0], [-1, 0, 0, 0, 0, 1]].filter(([nx, ny]) => nx * st + ny * ct > 0.001);
    const depth = (b) => (b.x + 0.5) * st + (b.y + 0.5) * ct;
    blocks.sort((a, b) => depth(a) - depth(b));
    for (const b of blocks) {
      const lift = rising ? back((p * 1.25) - b.delay) : p;
      const z = Math.max(0, b.h * zs * lift);
      const c = (x, y, zz) => proj(b.x + x, b.y + y, zz);
      const quad = (pts, fill) => { g.beginPath(); pts.forEach(([a, bb], i) => (i ? g.lineTo(a, bb) : g.moveTo(a, bb))); g.closePath(); g.fillStyle = fill; g.fill(); };
      if (z > 0.01) for (const [nx, ny, x1, y1, x2, y2] of sides) {
        quad([c(x1, y1, 0), c(x2, y2, 0), c(x2, y2, z), c(x1, y1, z)], nx ? b.s2 : b.s1);
      }
      const mix = Math.min(1, p * 1.6);
      quad([c(0, 0, z), c(1, 0, z), c(1, 1, z), c(0, 1, z)], mix < 0.5 ? '#12101f' : b.top);
      if (mix > 0 && mix < 0.5) { g.globalAlpha = mix * 2; quad([c(0, 0, z), c(1, 0, z), c(1, 1, z), c(0, 1, z)], b.top); g.globalAlpha = 1; }
    }
    if (cap) { const txt = p > 0.5 ? 'Unfolded into a world' : 'A normal QR code'; if (cap.textContent !== txt) cap.textContent = txt; }
  }
  let on = false, raf = 0, t0 = performance.now();
  const loop = (now) => { draw((now - t0) / 1000); raf = on ? requestAnimationFrame(loop) : 0; };
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  draw(still ? 0 : 0.01);
  if (!still) new IntersectionObserver(([e]) => { on = e.isIntersecting && !document.hidden; if (on && !raf) raf = requestAnimationFrame(loop); }).observe(qc);
  document.addEventListener('visibilitychange', () => { on = !document.hidden && qc.getBoundingClientRect().bottom > 0; if (on && !raf) raf = requestAnimationFrame(loop); });
}

// Product pages: the live demo runs inside the phone on wide screens; on phones it opens full screen
const phone = document.querySelector('.phone[data-demo]');
if (phone) {
  const screen = phone.querySelector('.screen'), demo = phone.dataset.demo;
  if (matchMedia('(min-width: 861px)').matches) {
    phone.querySelector('.play').addEventListener('click', () => {
      screen.innerHTML = `<iframe src="${demo}" title="Live demo" allow="autoplay; xr-spatial-tracking"></iframe>`;
    });
  } else {
    phone.querySelector('.play').addEventListener('click', () => { location.href = demo; });
  }
}
