package webapp

func miniAppHTML() string {
	return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>iModel</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:var(--tg-theme-bg-color,#18222d);
  --bg2:var(--tg-theme-secondary-bg-color,#232e3c);
  --text:var(--tg-theme-text-color,#fff);
  --hint:var(--tg-theme-hint-color,#8e99a4);
  --btn:var(--tg-theme-button-color,#2481cc);
  --btn-text:var(--tg-theme-button-text-color,#fff);
  --accent:#2481cc;
  --danger:#e53935;
  --radius:12px;
}
body{background:var(--bg);color:var(--text);font:15px/1.4 system-ui,-apple-system,sans-serif;min-height:100vh;padding-bottom:env(safe-area-inset-bottom)}

/* Header */
.header{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px;background:var(--bg2);border-bottom:1px solid rgba(255,255,255,.06)}
.header-left{display:flex;align-items:center;gap:10px}
.avatar{width:36px;height:36px;border-radius:50%;background:var(--accent);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700}
.username{font-weight:600;font-size:15px}
.credits-badge{background:var(--accent);color:#fff;border-radius:20px;padding:3px 10px;font-size:13px;font-weight:600}
.plan-badge{border-radius:20px;padding:3px 10px;font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}
.plan-badge.basic{background:#ff9800;color:#fff}
.plan-badge.pro{background:#9c27b0;color:#fff}
.plan-badge.unlimited{background:linear-gradient(135deg,#e040fb,#2196f3);color:#fff}

/* Tabs */
.tabs{display:flex;background:var(--bg2);border-bottom:1px solid rgba(255,255,255,.06)}
.tab{flex:1;padding:10px;text-align:center;font-size:14px;font-weight:500;color:var(--hint);cursor:pointer;border-bottom:2px solid transparent;transition:all .2s}
.tab.active{color:var(--text);border-bottom-color:var(--accent)}

/* Sections */
.section{padding:16px}
.section-title{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--hint);margin-bottom:10px}

/* Presets */
.presets-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.preset-btn{background:var(--bg2);border:2px solid transparent;border-radius:var(--radius);padding:12px 10px;text-align:left;cursor:pointer;transition:all .2s;color:var(--text)}
.preset-btn:active{transform:scale(.97)}
.preset-btn.selected{border-color:var(--accent);background:rgba(36,129,204,.15)}
.preset-emoji{font-size:22px;display:block;margin-bottom:4px}
.preset-name{font-size:13px;font-weight:600}

/* Upload area */
.upload-area{background:var(--bg2);border:2px dashed rgba(255,255,255,.15);border-radius:var(--radius);padding:32px 16px;text-align:center;cursor:pointer;transition:all .2s;position:relative}
.upload-area:active,.upload-area.dragover{border-color:var(--accent);background:rgba(36,129,204,.1)}
.upload-area.has-photo{border-style:solid;border-color:var(--accent);padding:0;overflow:hidden}
.upload-area img{width:100%;max-height:240px;object-fit:cover;border-radius:calc(var(--radius) - 2px);display:block}
.upload-icon{font-size:40px;margin-bottom:8px}
.upload-text{color:var(--hint);font-size:14px}
.upload-hint{color:var(--hint);font-size:12px;margin-top:4px}
#fileInput{display:none}
.photo-clear{position:absolute;top:8px;right:8px;background:rgba(0,0,0,.5);color:#fff;border:none;border-radius:50%;width:28px;height:28px;font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center}

/* Prompt input */
.prompt-input{width:100%;background:var(--bg2);border:1px solid rgba(255,255,255,.1);border-radius:var(--radius);padding:12px;color:var(--text);font:inherit;resize:none;outline:none;transition:border .2s}
.prompt-input:focus{border-color:var(--accent)}
.prompt-input::placeholder{color:var(--hint)}

/* Generate button */
.gen-btn{width:100%;background:var(--btn);color:var(--btn-text);border:none;border-radius:var(--radius);padding:14px;font:600 16px/1 inherit;cursor:pointer;transition:opacity .2s;display:flex;align-items:center;justify-content:center;gap:8px}
.gen-btn:disabled{opacity:.5;cursor:not-allowed}
.gen-btn:active:not(:disabled){opacity:.8}
.spinner{width:18px;height:18px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* Toast */
.toast{position:fixed;bottom:calc(20px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);background:#323232;color:#fff;padding:10px 20px;border-radius:24px;font-size:14px;z-index:999;opacity:0;transition:opacity .3s;pointer-events:none;white-space:nowrap;max-width:90vw;text-align:center}
.toast.show{opacity:1}

/* Gallery */
.gallery-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px}
.gallery-item{aspect-ratio:1;background:var(--bg2);border-radius:8px;overflow:hidden;cursor:pointer}
.gallery-item img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .2s}
.gallery-item:active img{transform:scale(.95)}
.gallery-empty{text-align:center;color:var(--hint);padding:40px 16px}
.gallery-empty-icon{font-size:48px;margin-bottom:12px}
.load-more{width:100%;background:var(--bg2);border:none;color:var(--text);border-radius:var(--radius);padding:12px;font:inherit;cursor:pointer;margin-top:12px}
.load-more:disabled{opacity:.4}

/* Status message */
.status-msg{background:rgba(36,129,204,.15);border:1px solid rgba(36,129,204,.3);border-radius:var(--radius);padding:12px;font-size:13px;color:var(--accent);text-align:center;margin-top:8px}

/* Tab panels */
.tab-panel{display:none}
.tab-panel.active{display:block}
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <div class="avatar" id="avatarEl">?</div>
    <div>
      <div class="username" id="nameEl">Loading…</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:6px">
    <span class="plan-badge" id="planBadge" style="display:none"></span>
    <span class="credits-badge" id="creditsEl">…</span>
  </div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="generate" onclick="switchTab('generate')">✨ Generate</div>
  <div class="tab" data-tab="gallery" onclick="switchTab('gallery')">🖼 Gallery</div>
</div>

<!-- Generate tab -->
<div class="tab-panel active" id="tab-generate">
  <div class="section">
    <div class="section-title">Choose a style</div>
    <div class="presets-grid" id="presetsGrid">
      <div style="color:var(--hint);font-size:13px">Loading presets…</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Your selfie</div>
    <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
      <div class="upload-icon">📸</div>
      <div class="upload-text">Tap to upload a photo</div>
      <div class="upload-hint">or take one with your camera</div>
    </div>
    <input type="file" id="fileInput" accept="image/*" capture="user"/>
  </div>

  <div class="section">
    <div class="section-title">Custom prompt <span style="color:var(--hint);text-transform:none;font-weight:400">(optional)</span></div>
    <textarea class="prompt-input" id="promptInput" rows="3" placeholder="Describe the style, lighting, mood…"></textarea>
  </div>

  <div class="section">
    <button class="gen-btn" id="genBtn" onclick="generate()">
      <span>✨ Generate</span>
    </button>
    <div class="status-msg" id="statusMsg" style="display:none"></div>
  </div>
</div>

<!-- Gallery tab -->
<div class="tab-panel" id="tab-gallery">
  <div class="section">
    <div class="section-title">Your generations</div>
    <div class="gallery-grid" id="galleryGrid"></div>
    <div class="gallery-empty" id="galleryEmpty" style="display:none">
      <div class="gallery-empty-icon">🎨</div>
      <div>No generations yet.<br/>Create your first one!</div>
    </div>
    <button class="load-more" id="loadMoreBtn" onclick="loadMoreGallery()" style="display:none">Load more</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData || '';
const headers = { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData };

let selectedPreset = null;
let selfieB64 = null;
let galleryPage = 0;
let galleryTotal = 0;
const pageSize = 9;

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  await Promise.all([loadMe(), loadPresets()]);
}

async function loadMe() {
  try {
    const r = await fetch('/app/api/me', { headers });
    if (!r.ok) return;
    const u = await r.json();
    document.getElementById('nameEl').textContent = u.name || u.username || 'User';
    document.getElementById('avatarEl').textContent = (u.name || 'U')[0].toUpperCase();
    document.getElementById('creditsEl').textContent = u.sub_tier === 'unlimited' ? '∞' : u.credits + ' cr';
    if (u.sub_tier) {
      const b = document.getElementById('planBadge');
      b.textContent = u.sub_tier.toUpperCase();
      b.className = 'plan-badge ' + u.sub_tier;
      b.style.display = '';
    }
  } catch(e) {}
}

async function loadPresets() {
  try {
    const r = await fetch('/app/api/presets', { headers });
    const presets = await r.json();
    const grid = document.getElementById('presetsGrid');
    grid.innerHTML = '';
    presets.forEach(p => {
      const parts = p.label.match(/^(\S+)\s+(.+)$/);
      const emoji = parts ? parts[1] : '✨';
      const name  = parts ? parts[2] : p.label;
      const btn = document.createElement('button');
      btn.className = 'preset-btn';
      btn.dataset.key = p.key;
      btn.innerHTML = '<span class="preset-emoji">' + emoji + '</span><span class="preset-name">' + name + '</span>';
      btn.onclick = () => selectPreset(p.key, btn);
      grid.appendChild(btn);
    });
  } catch(e) {}
}

// ── Preset selection ──────────────────────────────────────────────────────────
function selectPreset(key, el) {
  selectedPreset = key;
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  tg.HapticFeedback.selectionChanged();
}

// ── Photo upload ──────────────────────────────────────────────────────────────
document.getElementById('fileInput').addEventListener('change', function() {
  const file = this.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const dataURL = e.target.result;
    selfieB64 = dataURL.split(',')[1];
    const area = document.getElementById('uploadArea');
    area.classList.add('has-photo');
    area.innerHTML = '<img src="' + dataURL + '" alt="selfie"/>' +
      '<button class="photo-clear" onclick="clearPhoto(event)">×</button>';
  };
  reader.readAsDataURL(file);
});

function clearPhoto(e) {
  e.stopPropagation();
  selfieB64 = null;
  const area = document.getElementById('uploadArea');
  area.classList.remove('has-photo');
  area.innerHTML = '<div class="upload-icon">📸</div>' +
    '<div class="upload-text">Tap to upload a photo</div>' +
    '<div class="upload-hint">or take one with your camera</div>';
  area.onclick = () => document.getElementById('fileInput').click();
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function generate() {
  const prompt = document.getElementById('promptInput').value.trim();
  if (!selectedPreset && !prompt) {
    showToast('Please select a style or enter a prompt');
    return;
  }
  const btn = document.getElementById('genBtn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div><span>Generating…</span>';
  const statusMsg = document.getElementById('statusMsg');
  statusMsg.style.display = 'none';

  try {
    const body = { preset_key: selectedPreset || '', selfie_b64: selfieB64 || '', prompt };
    const r = await fetch('/app/api/generate', { method: 'POST', headers, body: JSON.stringify(body) });
    const data = await r.json();
    if (data.ok) {
      tg.HapticFeedback.notificationOccurred('success');
      statusMsg.textContent = '✅ ' + data.message;
      statusMsg.style.display = '';
      clearPhoto({ stopPropagation: () => {} });
    } else {
      tg.HapticFeedback.notificationOccurred('error');
      showToast(data.error || 'Something went wrong');
    }
  } catch(e) {
    showToast('Network error. Please try again.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>✨ Generate</span>';
    loadMe();
  }
}

// ── Gallery ───────────────────────────────────────────────────────────────────
async function loadGallery(reset) {
  if (reset) { galleryPage = 0; galleryTotal = 0; document.getElementById('galleryGrid').innerHTML = ''; }
  try {
    const r = await fetch('/app/api/gallery?page=' + galleryPage, { headers });
    const data = await r.json();
    galleryTotal = data.total;
    const grid = document.getElementById('galleryGrid');
    const empty = document.getElementById('galleryEmpty');
    if (data.total === 0 && galleryPage === 0) {
      empty.style.display = '';
    } else {
      empty.style.display = 'none';
      (data.items || []).forEach(url => {
        const item = document.createElement('div');
        item.className = 'gallery-item';
        item.innerHTML = '<img src="' + url + '" loading="lazy" alt="generation"/>';
        item.onclick = () => tg.openLink(url);
        grid.appendChild(item);
      });
    }
    const loadBtn = document.getElementById('loadMoreBtn');
    const loaded = (galleryPage + 1) * pageSize;
    loadBtn.style.display = loaded < galleryTotal ? '' : 'none';
  } catch(e) {}
}

function loadMoreGallery() { galleryPage++; loadGallery(false); }

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  if (name === 'gallery') loadGallery(true);
}

// ── Toast ─────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

init();
</script>
</body>
</html>`
}
