// Fade sections in as they scroll into view
const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add('in'), io.unobserve(e.target))), { threshold: 0.12 });
document.querySelectorAll('.rv').forEach((el) => io.observe(el));

// Hero: a real QR code for this site whose squares lift into a little 3D world and fold back down
const stage = document.getElementById('qr3d');
if (stage && window.qrcode) {
  const q = qrcode(0, 'M'); q.addData('HTTPS://WWW.QRWORLDS.CO.UK', 'Alphanumeric'); q.make();
  const n = q.getModuleCount(), pad = 2, cell = 100 / (n + pad * 2);
  const cols = ['#ff3b30', '#ffd60a', '#34c759', '#0a84ff', '#ff9f0a', '#bf5af2', '#ff2d92'];
  const frag = document.createDocumentFragment();
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
    if (!q.isDark(r, c)) continue;
    const i = document.createElement('i');
    const d = Math.hypot(r - n / 2, c - n / 2) / (n / 2);
    i.style.cssText = `left:${(c + pad) * cell}%;top:${(r + pad) * cell}%;width:${cell}%;height:${cell}%;` +
      `--z:${Math.round(8 + (1 - d) * 46 + Math.random() * 18)}px;--c:${cols[(r * 7 + c * 3) % cols.length]};transition-delay:${(d * 0.5).toFixed(2)}s`;
    frag.appendChild(i);
  }
  stage.appendChild(frag);
  const cap = document.getElementById('qrcap');
  let up = false;
  const flip = () => { up = !up; stage.classList.toggle('up', up); if (cap) cap.textContent = up ? 'Unfolded into a world' : 'A normal QR code'; };
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) { setTimeout(flip, 900); setInterval(flip, 3600); }
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
