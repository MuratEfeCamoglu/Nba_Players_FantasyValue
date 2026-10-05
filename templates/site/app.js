/* Fantezi NBA 9-Cat — sıralama, ilk 10 kartları, tema ve etki hesaplayıcısı.
   Ağ isteği yok, harici kütüphane yok; renkler CSS değişkenlerinden gelir. */
(function () {
  "use strict";

  var DASH = "—";
  var Z_CAP = 3; // |z| bu değerde en koyu ton / en uzun çubuk
  var THEME_KEY = "fantasy9cat-tema";
  var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- Türkçe sayı biçimi (formatting.fmt_num ile aynı kurallar) --- */
  function fmtNum(value, decimals, signed) {
    if (value === null || value === undefined || Number.isNaN(value)) return DASH;
    var text = Number(value).toFixed(decimals);
    if (/^-?0(\.0+)?$/.test(text)) text = text.replace("-", "");
    else if (signed && text.charAt(0) !== "-") text = "+" + text;
    return text.replace(".", ",");
  }

  function fmtPct(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return DASH;
    return "%" + fmtNum(value * 100, decimals);
  }

  /* --- Aksan ve büyük/küçük harf duyarsız arama: "sengun" → Şengün, İ/ı/i eşit --- */
  var SPECIAL = { ı: "i", İ: "i", ł: "l", Ł: "l", ø: "o", Ø: "o", đ: "d", Đ: "d", ß: "ss", æ: "ae" };
  function normalize(text) {
    return String(text)
      .replace(/[ıİłŁøØđĐßæ]/g, function (c) {
        return SPECIAL[c];
      })
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function intensity(z) {
    return Math.min(Math.abs(z) / Z_CAP, 1);
  }

  /* ================= Tema (açık/koyu) ================= */
  function initTheme() {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    var root = document.documentElement;
    var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

    function current() {
      var set = root.getAttribute("data-theme");
      if (set === "light" || set === "dark") return set;
      return media && media.matches ? "light" : "dark";
    }

    function label() {
      var next = current() === "dark" ? "Açık" : "Koyu";
      button.querySelector(".theme-label").textContent = next + " tema";
      button.setAttribute("aria-label", next + " temaya geç");
    }

    button.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch (e) {
        /* depolama kapalı: seçim yalnızca bu sayfada geçerli */
      }
      label();
    });
    if (media && media.addEventListener) media.addEventListener("change", label);
    label();
  }

  /* ================= Sıralama sayfası (F11, F16) ================= */
  function initRanking(data) {
    var minGp = data.minGp;
    var categories = data.categories;
    var modes = {};
    Object.keys(data.players).forEach(function (mode) {
      modes[mode] = data.players[mode].map(function (row) {
        var p = {};
        data.columns.forEach(function (col, i) {
          p[col] = row[i];
        });
        p._search = normalize(p.player_name);
        return p;
      });
    });

    var columns = [
      { key: "rank", label: "Sıra", num: true, decimals: 0, firstDir: 1, cls: "col-rank" },
      { key: "player_name", label: "Oyuncu", text: true, firstDir: 1, cls: "col-name" },
      { key: "team", label: "Takım", text: true, firstDir: 1 },
      { key: "gp", label: "MS", title: "Oynanan maç", num: true, decimals: 0, firstDir: -1 },
    ]
      .concat(
        categories.map(function (c) {
          return { key: c.zcol, label: c.short, title: c.label + " z-skoru", num: true, decimals: 2, z: true, firstDir: -1 };
        })
      )
      .concat([
        { key: "raw_total", label: "Ham", title: "9 z-skorun toplamı", num: true, decimals: 2, firstDir: -1 },
        { key: "value", label: "Değer", title: "1. aday = 100, yedek seviyesi = 0", num: true, decimals: 1, firstDir: -1 },
      ]);

    var state = { mode: "total", query: "", team: "", onlyEnough: false, sortKey: "rank", sortDir: 1, open: null };

    var table = document.getElementById("ranking");
    var wrap = table.parentElement;
    var thead = table.querySelector("thead");
    var tbody = table.querySelector("tbody");
    var search = document.getElementById("search");
    var teamSelect = document.getElementById("team");
    var onlyEnough = document.getElementById("only-enough");
    var onlyEnoughWrap = document.getElementById("only-enough-wrap");
    var count = document.getElementById("count");
    var cards = document.getElementById("top-cards");
    var cardsCaption = document.getElementById("top-caption");
    var controls = document.getElementById("controls");
    var filtersToggle = document.getElementById("filters-toggle");
    var modeButtons = document.querySelectorAll("[data-mode]");

    var teams = {};
    modes.total.forEach(function (p) {
      teams[p.team] = true;
    });
    Object.keys(teams)
      .sort()
      .forEach(function (t) {
        var opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        teamSelect.appendChild(opt);
      });

    function hiddenByGp(p) {
      return state.onlyEnough && state.mode === "per_game" && p.low_sample;
    }

    /* --- İlk 10 kartları --- */
    function miniChart(p) {
      return (
        '<ul class="mini" aria-hidden="true">' +
        categories
          .map(function (c) {
            var z = p[c.zcol];
            var h = (intensity(z) * 50).toFixed(1);
            var cls = z >= 0 ? "pos" : "neg";
            return (
              '<li title="' + escapeHtml(c.label) + " " + fmtNum(z, 2, true) + '"><span class="mini-track">' +
              '<span class="mini-bar ' + cls + '" style="height:' + h + '%"></span></span>' +
              '<span class="mini-label">' + c.short + "</span></li>"
            );
          })
          .join("") +
        "</ul>"
      );
    }

    function renderCards() {
      var top = modes[state.mode]
        .filter(function (p) {
          return !hiddenByGp(p);
        })
        .slice(0, 10);
      cardsCaption.textContent =
        (state.mode === "total" ? "Sezon toplamı" : "Maç başı") + " · karta tıklayınca tablodaki ayrıntı açılır";
      cards.innerHTML = top
        .map(function (p) {
          var zs = categories
            .map(function (c) {
              return c.short + " " + fmtNum(p[c.zcol], 2, true);
            })
            .join(", ");
          return (
            '<li><button type="button" class="card player-card" data-id="' + p.player_id + '" aria-label="' +
            escapeHtml(p.rank + ". " + p.player_name + ", değer " + fmtNum(p.value, 1) + ". " + zs) + '">' +
            '<span class="card-rank">' + p.rank + "</span>" +
            '<span class="card-name">' + escapeHtml(p.player_name) + "</span>" +
            '<span class="card-meta">' + escapeHtml(p.team) + " · " + p.gp + " maç" +
            (state.mode === "per_game" && p.low_sample ? " · az maç" : "") + "</span>" +
            miniChart(p) +
            '<span class="card-value">Değer <strong>' + fmtNum(p.value, 1) + "</strong></span>" +
            "</button></li>"
          );
        })
        .join("");
    }

    /* --- Tablo --- */
    function renderHead() {
      thead.innerHTML =
        "<tr>" +
        columns
          .map(function (c) {
            var sort = c.key === state.sortKey ? (state.sortDir === 1 ? "ascending" : "descending") : "none";
            var cls = [c.cls, c.num ? "num" : ""].filter(Boolean).join(" ");
            return (
              '<th scope="col" tabindex="0" data-key="' + c.key + '" aria-sort="' + sort + '"' +
              (cls ? ' class="' + cls + '"' : "") + (c.title ? ' title="' + escapeHtml(c.title) + '"' : "") + ">" +
              escapeHtml(c.label) + "</th>"
            );
          })
          .join("") +
        "</tr>";
    }

    function zCell(z, decimals) {
      var t = intensity(z).toFixed(3);
      var cls = z > 0 ? " z-pos" : z < 0 ? " z-neg" : "";
      return '<td class="num z' + cls + '" style="--t:' + t + '">' + fmtNum(z, decimals, true) + "</td>";
    }

    function detailHtml(p) {
      var perGame = state.mode === "per_game";
      var d = perGame ? 1 : 0;
      var stats = [
        ["Maç", fmtNum(p.gp, 0)],
        ["Dakika", fmtNum(p.min, perGame ? 1 : 0)],
        ["Sayı", fmtNum(p.pts, d)],
        ["Ribaund", fmtNum(p.reb, d)],
        ["Asist", fmtNum(p.ast, d)],
        ["Üçlük", fmtNum(p.fg3m, d)],
        ["Top çalma", fmtNum(p.stl, d)],
        ["Blok", fmtNum(p.blk, d)],
        ["Top kaybı", fmtNum(p.tov, d)],
        ["Saha içi", fmtNum(p.fgm, d) + "/" + fmtNum(p.fga, d) + " (" + fmtPct(p.fg_pct, 1) + ")"],
        ["Serbest atış", fmtNum(p.ftm, d) + "/" + fmtNum(p.fta, d) + " (" + fmtPct(p.ft_pct, 1) + ")"],
        ["Ham", fmtNum(p.raw_total, 2)],
        ["Değer", fmtNum(p.value, 1)],
      ];
      var statsHtml = stats
        .map(function (s) {
          return "<div><dt>" + s[0] + "</dt><dd>" + s[1] + "</dd></div>";
        })
        .join("");
      var barsHtml = categories
        .map(function (c) {
          var z = p[c.zcol];
          var width = (intensity(z) * 50).toFixed(1);
          var cls = z >= 0 ? "pos" : "neg";
          return (
            '<div class="bar-row" title="' + escapeHtml(c.label) + '"><span>' + c.short + "</span>" +
            '<span class="bar-track"><span class="bar ' + cls + '" style="width:' + width + '%"></span></span>' +
            '<span class="bar-value ' + cls + '">' + fmtNum(z, 2, true) + "</span></div>"
          );
        })
        .join("");
      return (
        '<tr class="detail"><td colspan="' + columns.length + '"><div class="detail-inner">' +
        "<div><h4>" + escapeHtml(p.player_name) + " · " + (perGame ? "maç başı" : "sezon toplamı") +
        '</h4><dl class="stats">' + statsHtml + "</dl></div>" +
        '<div><h4>Kategori katkıları (z): sağa artı, sola eksi</h4><div class="bars">' + barsHtml + "</div></div>" +
        "</div></td></tr>"
      );
    }

    function rowHtml(p) {
      var low = state.mode === "per_game" && p.low_sample;
      var cells = columns.map(function (c) {
        var v = p[c.key];
        if (c.key === "player_name") {
          return (
            '<td class="col-name" title="' + escapeHtml(v) + '">' + escapeHtml(v) +
            (low ? '<span class="badge" title="' + minGp + ' maçtan az oynadı">az maç</span>' : "") + "</td>"
          );
        }
        if (c.z) return zCell(v, c.decimals);
        if (c.text) return "<td>" + escapeHtml(v) + "</td>";
        return '<td class="num' + (c.cls ? " " + c.cls : "") + '">' + fmtNum(v, c.decimals) + "</td>";
      });
      return (
        '<tr class="player" tabindex="0" data-id="' + p.player_id + '" aria-expanded="false">' +
        cells.join("") + "</tr>"
      );
    }

    /* Satırlar her mod için bir kez DOM düğümü olarak üretilir; sıralama/filtre yalnızca var olan
       düğümleri yeniden dizer (her seferinde ~400 KB HTML ayrıştırmak 200 ms bütçesini aşıyordu). */
    var rowCache = {};
    function rowNodes() {
      var cache = rowCache[state.mode];
      if (cache) return cache;
      var holder = document.createElement("tbody");
      holder.innerHTML = modes[state.mode].map(rowHtml).join("");
      cache = {};
      Array.prototype.forEach.call(holder.rows, function (tr) {
        cache[tr.getAttribute("data-id")] = tr;
      });
      rowCache[state.mode] = cache;
      return cache;
    }

    function nodeFromHtml(html) {
      var holder = document.createElement("tbody");
      holder.innerHTML = html;
      return holder.firstElementChild;
    }

    function replacementRow() {
      var rank = data.replacementRank[state.mode];
      return nodeFromHtml(
        '<tr class="replacement-line" aria-label="Yedek seviyesi"><td colspan="' + columns.length + '">' +
          '<span class="replacement-label">Yedek seviyesi · ' + (data.poolSize + 1) + ". aday (sıra " + rank +
          ") · değer 0</span></td></tr>"
      );
    }

    var openRow = null;
    function render() {
      var t0 = performance.now();
      var all = modes[state.mode];
      var q = normalize(state.query.trim());
      var rows = all.filter(function (p) {
        if (q && p._search.indexOf(q) === -1) return false;
        if (state.team && p.team !== state.team) return false;
        return !hiddenByGp(p);
      });
      var col = columns.filter(function (c) {
        return c.key === state.sortKey;
      })[0];
      var dir = state.sortDir;
      rows.sort(function (a, b) {
        var x = a[col.key];
        var y = b[col.key];
        var cmp = col.text ? String(x).localeCompare(String(y), "tr") : x - y;
        return cmp * dir || a.rank - b.rank;
      });

      // Yedek çizgisi yalnızca değer sırasına göre (sıra ↑ / değer ↓ / ham ↓) dizilince anlamlıdır.
      var byValue =
        (state.sortKey === "rank" && dir === 1) ||
        ((state.sortKey === "value" || state.sortKey === "raw_total") && dir === -1);
      var replRank = data.replacementRank[state.mode];
      var cache = rowNodes();
      if (openRow) {
        openRow.classList.remove("open");
        openRow.setAttribute("aria-expanded", "false");
        openRow = null;
      }
      var nodes = [];
      var lineDrawn = false;
      rows.forEach(function (p) {
        if (byValue && !lineDrawn && p.rank >= replRank) {
          nodes.push(replacementRow());
          lineDrawn = true;
        }
        var tr = cache[p.player_id];
        nodes.push(tr);
        if (state.open === p.player_id) {
          tr.classList.add("open");
          tr.setAttribute("aria-expanded", "true");
          openRow = tr;
          nodes.push(nodeFromHtml(detailHtml(p)));
        }
      });
      tbody.replaceChildren.apply(tbody, nodes);
      count.textContent = all.length + " oyuncudan " + rows.length + " gösteriliyor";
      renderHead();
      console.debug("[9cat] sıralama/filtre: " + rows.length + " satır, " + (performance.now() - t0).toFixed(1) + " ms");
    }

    function renderAll() {
      renderCards();
      render();
    }

    function setMode(mode) {
      state.mode = mode;
      state.open = null;
      modeButtons.forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === mode));
      });
      onlyEnoughWrap.hidden = mode !== "per_game";
      renderAll();
    }

    function sortBy(key) {
      if (state.sortKey === key) {
        state.sortDir = -state.sortDir;
      } else {
        state.sortKey = key;
        state.sortDir = columns.filter(function (c) {
          return c.key === key;
        })[0].firstDir;
      }
      render();
    }

    function toggleRow(tr) {
      var id = Number(tr.getAttribute("data-id"));
      state.open = state.open === id ? null : id;
      render();
    }

    function openFromCard(id) {
      // Kart oyuncusu tabloda görünsün: arama ve takım filtresini temizle, sırayı geri al.
      state.query = "";
      state.team = "";
      search.value = "";
      teamSelect.value = "";
      state.sortKey = "rank";
      state.sortDir = 1;
      state.open = id;
      render();
      var row = tbody.querySelector('tr.player[data-id="' + id + '"]');
      if (row) {
        wrap.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
        wrap.scrollTop = Math.max(row.offsetTop - thead.offsetHeight - 8, 0);
        row.focus({ preventScroll: true });
      }
    }

    modeButtons.forEach(function (b) {
      b.addEventListener("click", function () {
        setMode(b.getAttribute("data-mode"));
      });
    });
    search.addEventListener("input", function () {
      state.query = search.value;
      render();
    });
    teamSelect.addEventListener("change", function () {
      state.team = teamSelect.value;
      render();
    });
    onlyEnough.addEventListener("change", function () {
      state.onlyEnough = onlyEnough.checked;
      renderAll();
    });
    filtersToggle.addEventListener("click", function () {
      var expanded = filtersToggle.getAttribute("aria-expanded") === "true";
      filtersToggle.setAttribute("aria-expanded", String(!expanded));
      controls.setAttribute("data-collapsed", String(expanded));
    });
    thead.addEventListener("click", function (e) {
      var th = e.target.closest("th");
      if (th) sortBy(th.getAttribute("data-key"));
    });
    thead.addEventListener("keydown", function (e) {
      var th = e.target.closest("th");
      if (th && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        sortBy(th.getAttribute("data-key"));
      }
    });
    tbody.addEventListener("click", function (e) {
      var tr = e.target.closest("tr.player");
      if (tr) toggleRow(tr);
    });
    tbody.addEventListener("keydown", function (e) {
      var tr = e.target.closest("tr.player");
      if (tr && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        toggleRow(tr);
      }
    });
    cards.addEventListener("click", function (e) {
      var card = e.target.closest("[data-id]");
      if (card) openFromCard(Number(card.getAttribute("data-id")));
    });

    onlyEnough.checked = false;
    setMode("total");
  }

  /* ================= Etki hesaplayıcısı (F14) ================= */
  function initCalculator(params) {
    var category = document.getElementById("calc-category");
    var made = document.getElementById("calc-made");
    var attempts = document.getElementById("calc-attempts");
    var out = {
      league: document.getElementById("calc-league"),
      pct: document.getElementById("calc-pct"),
      impact: document.getElementById("calc-impact"),
      z: document.getElementById("calc-z"),
      formula: document.getElementById("calc-formula"),
      error: document.getElementById("calc-error"),
    };

    function update() {
      var p = params[category.value];
      var m = Number(made.value);
      var a = Number(attempts.value);
      out.league.textContent = fmtPct(p.league_pct, 2);
      var error = "";
      if (made.value === "" || attempts.value === "" || m < 0 || a < 0) error = "İsabet ve deneme 0 veya pozitif olmalı.";
      else if (m > a) error = "İsabet, denemeden büyük olamaz.";
      out.error.hidden = !error;
      out.error.textContent = error;
      if (error) {
        out.pct.textContent = out.impact.textContent = out.z.textContent = DASH;
        out.formula.textContent = "";
        return;
      }
      var impact = a > 0 ? m - p.league_pct * a : 0; // valuation.percent_impact ile aynı
      var z = (impact - p.mu) / p.sigma;
      out.pct.textContent = a > 0 ? fmtPct(m / a, 1) : DASH;
      out.impact.textContent = fmtNum(impact, 2, true);
      out.z.textContent = fmtNum(z, 3, true);
      out.formula.textContent =
        "etki = " + m + " − " + fmtNum(p.league_pct, 4) + " × " + a + " = " + fmtNum(impact, 2, true) +
        "; z = (" + fmtNum(impact, 2, true) + " − " + fmtNum(p.mu, 3) + ") / " + fmtNum(p.sigma, 3) +
        " = " + fmtNum(z, 3, true);
    }

    [category, made, attempts].forEach(function (el) {
      el.addEventListener("input", update);
      el.addEventListener("change", update);
    });
    update();
  }

  initTheme();
  var playersEl = document.getElementById("players-data");
  if (playersEl) initRanking(JSON.parse(playersEl.textContent));
  var calcEl = document.getElementById("calc-params");
  if (calcEl) initCalculator(JSON.parse(calcEl.textContent));
})();
