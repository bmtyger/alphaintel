/* AlphaIntel app.js — production build */
/* Handles data ingestion, rendering, error states, and retry */

(function () {
  'use strict';

  const GRID = document.getElementById('dashboard-grid');
  const STATE_MSG = document.getElementById('state-message');
  const STATE_TEXT = document.getElementById('state-text');
  const STATUS_DOT = document.getElementById('status-dot');
  const STATUS_TEXT = document.getElementById('status-text');
  const DATA_URL = './data.json';
  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = 1000;

  function setState(kind, message) {
    STATE_MSG.hidden = false;
    STATE_MSG.className = 'state-message ' + kind;
    STATE_TEXT.textContent = message;
  }

  function clearState() {
    STATE_MSG.hidden = true;
    STATE_MSG.className = 'state-message';
  }

  function setStatus(ok, text) {
    STATUS_DOT.classList.toggle('error', !ok);
    STATUS_TEXT.textContent = text;
  }

  function validateItem(item, index) {
    if (!item || typeof item !== 'object') throw new Error(`Item ${index} is not an object`);
    const required = ['category', 'timestamp', 'headline', 'bullet_points', 'source', 'confidence'];
    for (const key of required) {
      if (!(key in item)) throw new Error(`Item ${index} missing field: ${key}`);
    }
    if (!['finance', 'security', 'trends'].includes(item.category)) {
      throw new Error(`Item ${index} invalid category: ${item.category}`);
    }
    if (typeof item.confidence !== 'number' || item.confidence < 0 || item.confidence > 100) {
      throw new Error(`Item ${index} confidence out of range`);
    }
    if (!Array.isArray(item.bullet_points)) {
      throw new Error(`Item ${index} bullet_points must be array`);
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function confidenceClass(score) {
    if (score >= 90) return 'high';
    if (score >= 80) return 'medium';
    return 'low';
  }

  function renderCard(item) {
    const article = document.createElement('article');
    article.className = 'card';
    article.style.animationDelay = '0ms';

    const tag = document.createElement('span');
    tag.className = 'tag ' + escapeHtml(item.category);
    tag.textContent = item.category;

    const ts = document.createElement('span');
    ts.className = 'timestamp';
    ts.textContent = item.timestamp;

    const header = document.createElement('div');
    header.className = 'card-header';
    header.append(tag, ts);

    const body = document.createElement('div');
    body.className = 'card-body';

    const h3 = document.createElement('h3');
    h3.textContent = item.headline || 'Untitled';
    body.appendChild(h3);

    const ul = document.createElement('ul');
    const points = Array.isArray(item.bullet_points) ? item.bullet_points : [];
    for (const pt of points.slice(0, 5)) {
      const li = document.createElement('li');
      li.textContent = pt;
      ul.appendChild(li);
    }
    body.appendChild(ul);

    const footer = document.createElement('div');
    footer.className = 'card-footer';

    const src = document.createElement('span');
    src.textContent = 'Source: ' + (item.source || 'Unknown');
    footer.appendChild(src);

    const conf = document.createElement('span');
    conf.className = 'confidence ' + confidenceClass(item.confidence || 0);
    conf.textContent = (item.confidence || 0) + '% Confidence';
    footer.appendChild(conf);

    article.append(header, body, footer);
    return article;
  }

  function render(stream) {
    GRID.innerHTML = '';
    const items = Array.isArray(stream?.intel_stream) ? stream.intel_stream : [];
    if (items.length === 0) {
      setState('error', 'No intelligence data available.');
      setStatus(false, 'No data');
      return;
    }
    const frag = document.createDocumentFragment();
    for (const item of items) {
      try {
        frag.appendChild(renderCard(item));
      } catch (e) {
        console.warn('Skipping malformed item:', item, e);
      }
    }
    GRID.appendChild(frag);
    clearState();
    setStatus(true, 'System Active — ' + items.length + ' items');
  }

  async function fetchWithRetry(url, retries) {
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const res = await fetch(url + '?t=' + Date.now(), { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return await res.json();
      } catch (err) {
        if (attempt === retries) throw err;
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS * attempt));
      }
    }
  }

  async function init() {
    setState('', 'Loading intelligence…');
    setStatus(true, 'Loading…');
    try {
      const data = await fetchWithRetry(DATA_URL, MAX_RETRIES);
      render(data);
    } catch (err) {
      console.error('Dashboard load failed:', err);
      setState('error', 'Unable to load intelligence feed. Retrying…');
      setStatus(false, 'Load failed');
      // retry once after 5s
      setTimeout(init, 5000);
    }
  }

  if (GRID) init();
})();

/* Waitlist form handler (static fallback) */
(function () {
  const form = document.getElementById('waitlist-form');
  const note = document.getElementById('form-note');
  if (!form) return;
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const email = form.email.value.trim();
    const role = form.role.value;
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      if (note) { note.textContent = 'Please enter a valid email.'; note.className = 'form-note error'; note.hidden = false; }
      return;
    }
    // In production replace this with Formspree / Netlify Forms / backend endpoint
    const subject = encodeURIComponent('AlphaIntel waitlist signup');
    const body = encodeURIComponent(`Email: ${email}\nRole: ${role}`);
    window.location.href = `mailto:bodea.mircea@gmail.com?subject=${subject}&body=${body}`;
    if (note) { note.textContent = 'Opening your mail client…'; note.className = 'form-note success'; note.hidden = false; }
  });
})();
