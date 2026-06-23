(function () {
  "use strict";
  var GRID = document.getElementById("dashboard-grid");
  var STATE_MSG = document.getElementById("state-message");
  var STATE_TEXT = document.getElementById("state-text");
  var SEARCH = document.getElementById("search");
  var TABS = document.querySelectorAll(".tab");
  var TOKEN_INPUT = document.getElementById("token-input");
  var TOKEN_SAVE = document.getElementById("token-save");
  var LOGOUT_BTN = document.getElementById("logout-btn");
  var TIER_LABEL = document.getElementById("tier-label");

  var API = "/intel/api/intel_stream";
  var token = localStorage.getItem("alphaintel.token") || "";
  var tier = localStorage.getItem("alphaintel.tier") || "";
  var MAX_RETRIES = 3;
  var allItems = [];
  var activeCategory = "all";
  var activeQuery = "";
  var userTelegramChatId = localStorage.getItem("alphaintel.telegram_chat_id") || "";

  function setState(kind, message) {
    STATE_MSG.hidden = false;
    STATE_MSG.className = "state-message " + kind;
    STATE_TEXT.textContent = message;
  }

  function setDiagnostics(state, message) {
    var el = document.getElementById("diagnostics");
    if (!el) return;
    el.hidden = false;
    el.textContent = "Diagnostics: " + state + " - " + message;
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
    window.__lastItem = item;
    var article = document.createElement("article");
    article.className = "card";
    article.tabIndex = 0;
    article.setAttribute("role", "article");
    article.style.animationDelay = "0ms";

    var header = document.createElement("div");
    header.className = "card-header";
    var tags = document.createElement("div");
    tags.className = "tags";
    var cat = document.createElement("span");
    cat.className = "tag " + (item.category || "trends");
    cat.textContent = item.category || "trends";
    tags.appendChild(cat);
    header.appendChild(tags);
    var ts = document.createElement("span");
    ts.className = "timestamp";
    ts.textContent = item.timestamp || "";
    header.appendChild(ts);
    article.appendChild(header);

    var tickers = item.tickers && item.tickers.length ? item.tickers.slice(0, 6) : [];
    if (tickers.length && tier !== "free") {
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

    var footer = document.createElement("div");
    footer.className = "card-footer";
    var src = document.createElement("span");
    if (item.url) {
      var a = document.createElement("a");
      a.className = "source-link";
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = "Source: " + (item.source || "Unknown");
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

  function isAuthorized() {
    return !!token;
  }

  function render() {
    if (!isAuthorized()) {
      GRID.innerHTML = "";
      setState("error", "Sign in to view intelligence.");
      return;
    }
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
        var headers = {};
        if (token) headers["Authorization"] = "Bearer " + token;
        var res = await fetch(url + "?t=" + Date.now(), {
          headers: headers,
          cache: "no-store"
        });
        if (res.status === 401) {
          localStorage.removeItem("alphaintel.token");
          localStorage.removeItem("alphaintel.tier");
          token = "";
          tier = "";
          TOKEN_INPUT.style.display = "";
          TOKEN_SAVE.style.display = "";
          LOGOUT_BTN.style.display = "none";
          TIER_LABEL.style.display = "none";
          setState("error", "Session expired. Sign in again.");
          throw new Error("Unauthorized");
        }
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
      var data = await fetchWithRetry(API, MAX_RETRIES);
      var stream = Array.isArray(data && data.intel_stream) ? data.intel_stream : [];
      allItems = stream;
      render();
      var counts = {};
      allItems.forEach(function (i) { counts[i.category] = (counts[i.category] || 0) + 1; });
      setDiagnostics("ok", Object.keys(counts).map(function (k) { return k + ":" + counts[k]; }).join(", ") + " (" + allItems.length + " total)");
    } catch (err) {
      console.error("Dashboard load failed:", err);
      setState("error", "Signal feed unreachable. Retrying…");
      setDiagnostics("error", err && err.message ? err.message : String(err));
      setTimeout(init, 8000);
    }
  }

  if (TOKEN_SAVE) {
    TOKEN_SAVE.addEventListener("click", function () {
      var t = (TOKEN_INPUT.value || "").trim();
      if (!t) return;
      token = t;
      tier = "";
      localStorage.setItem("alphaintel.token", token);
      localStorage.setItem("alphaintel.tier", "");
      localStorage.removeItem("alphaintel.telegram_chat_id");
      TOKEN_INPUT.style.display = "none";
      TOKEN_SAVE.style.display = "none";
      LOGOUT_BTN.style.display = "";
      TIER_LABEL.style.display = "";
      TIER_LABEL.textContent = tier ? "Tier: " + tier : "";
      init();
    });
  }

  if (LOGOUT_BTN) {
    LOGOUT_BTN.addEventListener("click", function () {
      token = "";
      tier = "";
      userTelegramChatId = "";
      localStorage.removeItem("alphaintel.token");
      localStorage.removeItem("alphaintel.tier");
      localStorage.removeItem("alphaintel.telegram_chat_id");
      TOKEN_INPUT.style.display = "";
      TOKEN_SAVE.style.display = "";
      LOGOUT_BTN.style.display = "none";
      TIER_LABEL.style.display = "none";
      render();
    });
  }

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

  if (GRID && isAuthorized()) init();
})();
