/* AlphaIntel B2B Signal Dashboard */

(function () {
  'use strict';

  const GRID = document.getElementById('dashboard-grid');
  const STATE_MSG = document.getElementById('state-message');
  const STATE_TEXT = document.getElementById('state-text');
  const SEARCH = document.getElementById('search');
  const TABS = document.querySelectorAll('.tab');
  const DATA_URL = './data.json';
  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = 800;

  let allItems = [];
  let activeCategory = 'all';
  let activeQuery = '';

  function setState(kind, message) {
    STATE_MSG.hidden = false;
    STATE_MSG.className = 'state-message ' + kind;
    STATE_TEXT.textContent = message;
  }

  function clearState() { STATE_MSG.hidden = true; STATE_MSG.className = 'state-message'; }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function impactClass(score) {
    if (score >= 75) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  }

  function renderCard(item) {
    const article = document.createElement('article');
    article.className = 'card';
    article.style.animationDelay = '0ms';

    const header = document.createElement('div');
    header.className = 'card-header';

    const tags = document.createElement('div');
    tags.className = 'tags';
    const cat = document.createElement('span');
    cat.className = 'tag ' + escapeHtml(item.category || 'trends');
    cat.textContent = item.category || 'trends';
    tags.appendChild(cat);
    if (item.event_type) {
      const ev = document.createElement('span');
      ev.className = 'tag event';
      ev.textContent = item.event_type;
      tags.appendChild(ev);
    }
    header.appendChild(tags);

    const ts = document.createElement('span');
    ts.className = 'timestamp';
    ts.textContent = item.timestamp || '';
    header.appendChild(ts);

    article.appendChild(header);

    const tickers = item.tickers && item.tickers.length ? item.tickers.slice(0, 6) : [];
    if (tickers.length) {
      const row = document.createElement('div');
      row.className = 'ticker-row';
      for (const t of tickers) {
        const span = document.createElement('span');
        span.className = 'ticker';
        span.textContent = t;
        row.appendChild(span);
      }
      article.appendChild(row);
    }

    const body = document.createElement('div');
    body.className = 'card-body';
    const h3 = document.createElement('h3');
    h3.textContent = item.headline || 'Untitled signal';
    body.appendChild(h3);

    const ul = document.createElement('ul');
    const pts = Array.isArray(item.bullet_points) ? item.bullet_points.slice(0, 4) : [];
    for (const p of pts) {
      const li = document.createElement('li');
      li.textContent = p;
      ul.appendChild(li);
    }
    body.appendChild(ul);
    article.appendChild(body);

    const footer = document.createElement('div');
    footer.className = 'card-footer';

    const src = document.createElement('span');
    if (item.url) {
      const a = document.createElement('a');
      a.className = 'source-link';
      a.href = escapeHtml(item.url);
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = 'Source: ' + (item.source || 'Unknown');
      src.appendChild(a);
    } else {
      src.textContent = 'Source: ' + (item.source || 'Unknown');
    }
    footer.appendChild(src);

    const impact = item.market_impact || {};
    const imp = document.createElement('span');
    imp.className = 'impact ' + impactClass(impact.score || 0);
    imp.textContent = (impact.tier || 'low').toUpperCase() + ' IMPACT';
    footer.appendChild(imp);

    const conf = document.createElement('span');
    conf.textContent = (item.confidence || 0) + '% confidence';
    footer.appendChild(conf);

    article.appendChild(footer);
    return article;
  }

  function matchesQuery(item, query) {
    if (!query) return true;
    const q = query.toLowerCase();
    const haystack = [
      item.headline, item.source, item.category, item.event_type,
      ...(item.tickers || []), ...(item.bullet_points || [])
    ].join(' ').toLowerCase();
    return haystack.includes(q);
  }

  function render() {
    GRID.innerHTML = '';
    let filtered = allItems;

    if (activeCategory !== 'all') {
      filtered = filtered.filter(i => i.category === activeCategory);
    }
    if (activeQuery) {
      filtered = filtered.filter(i => matchesQuery(i, activeQuery));
    }

    if (!filtered.length) {
      setState('error', 'No signals match your filter.');
      return;
    }

    const frag = document.createDocumentFragment();
    for (const item of filtered) {
      try { frag.appendChild(renderCard(item)); } catch (e) { console.warn(e, item); }
    }
    GRID.appendChild(frag);
    clearState();
  }

  async function fetchWithRetry(url, retries) {
    for (let i = 1; i <= retries; i++) {
      try {
        const res = await fetch(url + '?t=' + Date.now(), { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return await res.json();
      } catch (err) {
        if (i === retries) throw err;
        await new Promise(r => setTimeout(r, RETRY_DELAY_MS * i));
      }
    }
  }

  async function init() {
    setState('', 'Loading intelligence…');
    try {
      const data = await fetchWithRetry(DATA_URL, MAX_RETRIES);
      allItems = Array.isArray(data?.intel_stream) ? data.intel_stream : [];
      if (!allItems.length) {
        setState('error', 'Signal feed empty. Retrying in 10s…');
        setTimeout(init, 10000);
        return;
      }
      render();
    } catch (err) {
      console.error('Dashboard load failed:', err);
      setState('error', 'Signal feed unreachable. Retrying…');
      setTimeout(init, 8000);
    }
  }

  TABS.forEach(tab => {
    tab.addEventListener('click', () => {
      TABS.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      activeCategory = tab.dataset.cat || 'all';
      render();
    });
  });

  let searchTimer = null;
  if (SEARCH) {
    SEARCH.addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        activeQuery = e.target.value.trim();
        render();
      }, 240);
    });
  }

  if (GRID) init();
})();
