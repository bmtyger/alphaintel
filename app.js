(function () {
  "use strict";
  var GRID = document.getElementById("dashboard-grid");
  var STATE_MSG = document.getElementById("state-message");
  var STATE_TEXT = document.getElementById("state-text");
  var SEARCH = document.getElementById("search");
  var TABS = document.querySelectorAll(".tab");
  var DATA_URL = "./data.json";
  var MAX_RETRIES = 3;

  var allItems = [];
  var activeCategory = "all";
  var activeQuery = "";

  function setState(kind, message) {
    STATE_MSG.hidden = false;
    STATE_MSG.className = "state-message " + kind;
    STATE_TEXT.textContent = message;
  }

  function setDiagnostics(state, message) {
    var el = document.getElementById("diagnostics");
    if (!el) return;
    el.hidden = false;
    el.textContent = "Diagnostics: " + state + " — " + message;
    el.className = "diagnostics " + state;
  }

  function clearState() {
    STATE_MSG.hidden = true;
    STATE_MSG.className = "state-message";
  }

  function impactClass(score) {
    if (score >= 75) return "high";
    if (score >= 40) return "medium";
    return "low";
  }

  function renderCard(item) {
    var article = document.createElement("article");
    article.className = "card";
    article.tabIndex = 0;
    article.setAttribute("role", "article");
    article.style.animationDelay = "0ms";

    // Header: tags + timestamp
    var header = document.createElement("div");
    header.className = "card-header";

    var tags = document.createElement("div");
    tags.className = "tags";
    var cat = document.createElement("span");
    cat.className = "tag " + escapeHtml(item.category || "trends");
    cat.textContent = item.category || "trends";
    tags.appendChild(cat);

    if (item.event_type) {
      var ev = document.createElement("span");
      ev.className = "tag event";
      ev.textContent = item.event_type;
      tags.appendChild(ev);
    }
    header.appendChild(tags);

    var ts = document.createElement("span");
    ts.className = "timestamp";
    ts.textContent = item.timestamp || "";
    header.appendChild(ts);
    article.appendChild(header);

    // Ticker row
    var tickers = item.tickers && item.tickers.length ? item.tickers.slice(0, 6) : [];
    if (tickers.length) {
      var tickerRow = document.createElement("div");
      tickerRow.className = "ticker-row";
      for (var k = 0; k < tickers.length; k++) {
        (function (t) {
          var span = document.createElement("span");
          span.className = "ticker";
          span.textContent = t;
          span.title = "Ticker: " + t;
          span.addEventListener("click", function (e) {
            e.stopPropagation();
            window.open("https://finance.yahoo.com/quote/" + encodeURIComponent(t), "_blank", "noopener");
          });
          tickerRow.appendChild(span);
        })(tickers[k]);
      }
      article.appendChild(tickerRow);
    }

    // Body: headline + bullets
    var body = document.createElement("div");
    body.className = "card-body";
    var h3 = document.createElement("h3");
    h3.textContent = item.headline || "Untitled signal";
    body.appendChild(h3);

    var ul = document.createElement("ul");
    var pts = Array.isArray(item.bullet_points) ? item.bullet_points.slice(0, 4) : [];
    for (var i = 0; i < pts.length; i++) {
      var li = document.createElement("li");
      li.textContent = pts[i];
      ul.appendChild(li);
    }
    body.appendChild(ul);
    article.appendChild(body);

    // Footer: source link, impact, confidence
    var footer = document.createElement("div");
    footer.className = "card-footer";

    var src = document.createElement("span");
    if (item.url) {
      var a = document.createElement("a");
      a.className = "source-link";
      a.href = escapeHtml(item.url);
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = "Source: " + (item.source || "Unknown");
      a.addEventListener("click", function (e) {
        e.stopPropagation();
      });
      src.appendChild(a);
    } else {
      src.textContent = "Source: " + (item.source || "Unknown");
    }
    footer.appendChild(src);

    var impact = item.market_impact || {};
    var imp = document.createElement("span");
    imp.className = "impact " + impactClass(impact.score || 0);
    imp.textContent = (impact.tier || "low").toUpperCase() + " IMPACT";
    footer.appendChild(imp);

    var conf = document.createElement("span");
    conf.textContent = Math.round(item.confidence || 0) + "% confidence";
    footer.appendChild(conf);

    article.appendChild(footer);

    // Interactive behavior
    article.addEventListener("click", function (e) {
      if (e.target.closest("a") || e.target.closest("button")) return;
      var expanded = article.classList.toggle("expanded");
      var allBullets = Array.isArray(item.bullet_points) ? item.bullet_points : [];
      if (expanded && allBullets.length > 4) {
        var extra = document.createElement("li");
        extra.textContent = "+ " + (allBullets.length - 4) + " more bullets";
        extra.style.color = "var(--accent-blue)";
        ul.appendChild(extra);
      }
    });

    article.addEventListener("dblclick", function (e) {
      if (e.target.closest("a")) return;
      if (item.url) window.open(item.url, "_blank", "noopener");
    });

    return article;
  }

  function matchesQuery(item, query) {
    if (!query) return true;
    var q = query.toLowerCase();
    var haystack = [
      item.headline,
      item.source,
      item.category,
      item.event_type,
      (item.tickers || []).join(" "),
      (item.bullet_points || []).join(" ")
    ].join(" ").toLowerCase();
    return haystack.indexOf(q) !== -1;
  }

  function render() {
    GRID.innerHTML = "";
    var filtered = allItems;

    if (activeCategory !== "all") {
      filtered = filtered.filter(function (i) { return i.category === activeCategory; });
    }
    if (activeQuery) {
      filtered = filtered.filter(function (i) { return matchesQuery(i, activeQuery); });
    }

    if (!filtered.length) {
      setState("error", "No signals match your filter.");
      return;
    }

    var frag = document.createDocumentFragment();
    for (var idx = 0; idx < filtered.length; idx++) {
      try { frag.appendChild(renderCard(filtered[idx])); } catch (e) { console.warn(e, filtered[idx]); }
    }
    GRID.appendChild(frag);
    clearState();
  }

  async function fetchWithRetry(url, retries) {
    for (let i = 1; i <= retries; i++) {
      try {
        var res = await fetch(url + "?t=" + Date.now(), { cache: "no-store" });
        if (!res.ok) throw new Error("HTTP " + res.status);
        return await res.json();
      } catch (err) {
        if (i === retries) throw err;
        await new Promise(function (r) { setTimeout(r, 800 * i); });
      }
    }
  }

  async function init() {
    setState("", "Loading intelligence…");
    try {
      var data = await fetchWithRetry(DATA_URL, MAX_RETRIES);
      allItems = Array.isArray(data && data.intel_stream) ? data.intel_stream : [];
      if (!allItems.length) {
        setState("error", "Signal feed empty. Retrying in 10 s…");
        setTimeout(init, 10000);
        return;
      }
      render();
      setDiagnostics("ok", allItems.length + " signals loaded");
    } catch (err) {
      console.error("Dashboard load failed:", err);
      setState("error", "Signal feed unreachable. Retrying…");
      setDiagnostics("error", err && err.message ? err.message : String(err));
      setTimeout(init, 8000);
    }
  }

  // Tab filters
  TABS.forEach(function (tab) {
    tab.addEventListener("click", function () {
      TABS.forEach(function (t) {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      activeCategory = tab.getAttribute("data-cat") || "all";
      render();
    });
  });

  // Search with debounce
  if (SEARCH) {
    var searchTimer = null;
    SEARCH.addEventListener("input", function (e) {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        activeQuery = SEARCH.value.trim();
        render();
      }, 240);
    });
  }

  if (GRID) init();
})();
