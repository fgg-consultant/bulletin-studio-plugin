/* ============================================================================
   Bulletin Studio prototype — shared A4 renderer
   Renders the layout state (same JSON shape as the backend BulletinTemplate)
   into stacked A4 sheets. Used by BOTH the template editor and the issue fill,
   so the on-screen canvas == the eventual PDF by construction.

   A4.render(canvasEl, state, ctx) -> { figures, zones, pageCount }
   ========================================================================= */
(function (global) {
  "use strict";
  const D = global.STUDIO_DATA;

  const PH_LABEL = {
    issue_number: "numéro", issue_date: "date_du_numéro", period: "période",
    period_start: "début_période", period_end: "fin_période", product_name: "produit",
  };
  const PH_RE = /\{(issue_number|issue_date|period|period_start|period_end|product_name)\}/g;

  function values(state, issue, pageIndex, pageCount) {
    const v = {
      issue_number: issue ? issue.issue_number : "",
      issue_date: issue ? D.frDate(issue.issue_date) : "",
      period_start: issue ? D.frDate(issue.period_start) : "",
      period_end: issue ? D.frDate(issue.period_end) : "",
      product_name: state.name || "",
      page: (pageIndex + 1), pages: pageCount,
    };
    v.period = v.period_start && v.period_end ? v.period_start + " – " + v.period_end : v.period_start;
    return v;
  }

  function subst(text, vals, mode) {
    if (!text) return "";
    if (mode === "chips") {
      return esc(text).replace(PH_RE, (m, k) => `<span class="ph-chip">{${PH_LABEL[k]}}</span>`);
    }
    return esc(text).replace(PH_RE, (m, k) => esc(String(vals[k] != null ? vals[k] : "")));
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── header / footer bands ──────────────────────────────────────────────
  function headerBand(state, vals, mode, hf, pi, pt) {
    const chips = mode === "template";
    const editable = mode === "template" && hf;
    const titleAttr = editable ? `contenteditable="true" data-el="__header_title" data-store="text"` : "";
    const dateCell = chips
      ? `Date : <span class="ph-chip">{date_du_numéro}</span>`
      : `Date : ${esc(vals.issue_date)}`;
    const pageCell = chips
      ? `Page : <span class="ph-chip">{page}/{pages}</span>`
      : `Page : <b>${pi + 1}/${pt}</b>`;
    const lock = (mode === "issue") ? `<span class="lockhint">En-tête — identique sur toutes les pages</span>` : "";
    const cls = "band hdrband" + (mode === "template" && !hf ? " band-locked" : "");
    return `<div class="${cls}" data-band="header">${lock}
      <div class="hdr-tbl">
        <div class="c logo-ph"><div class="img"></div></div>
        <div class="c hdr-mid" ${titleAttr}>BULLETIN<br>AGROMETEOROLOGIQUE<br>DECADAIRE</div>
        <div class="c hdr-ref">
          <div>Réf : ANAM/PAM/PR_10/BN_01</div>
          <div>${dateCell}</div>
          <div>${pageCell}</div>
        </div>
      </div></div>`;
  }

  function footerBand(state, vals, mode) {
    const issueTxt = mode === "template"
      ? `N° <span class="ph-chip">{numéro}</span>`
      : `N° ${esc(vals.issue_number)}`;
    const lock = (mode === "issue") ? `<span class="lockhint">Pied de page — identique sur toutes les pages</span>` : "";
    return `<div class="band footband" data-band="footer">${lock}
      <div class="foot-band">
        <div class="links">🌐 meteoburkina.bf &nbsp; f facebook.com/meteoburkina</div>
        <div>${issueTxt}</div>
        <div class="qr"></div>
      </div></div>`;
  }

  // ── element renderers ───────────────────────────────────────────────────
  function renderElement(el, st) {
    const { mode, vals, selectedId } = st;
    const sel = (mode === "template" && selectedId === el.id) ? " sel" : "";
    let inner = "", tabLabel = "", chip = "";

    if (el.type === "title") {
      const cls = el.level === 1 ? "doc-h1" : (el.level === 3 ? "doc-h h3" : "doc-h");
      const ed = mode === "template" ? `contenteditable="true" data-store="text"` : "";
      const lockCls = mode === "issue" ? "ez locked" : "";
      inner = `<div class="${lockCls}"><div class="${cls}" ${ed}>${esc(el.text || "")}</div>` +
        (mode === "issue" ? `<span class="lockhint">Issu du template</span>` : ``) + `</div>`;
      tabLabel = el.level === 1 ? "TITRE" : (el.level === 3 ? "SOUS-TITRE" : "TITRE DE SECTION");

    } else if (el.type === "text") {
      tabLabel = "TEXTE";
      if (mode === "template") {
        const body = el.html ? el.html : "";
        inner = `<div class="doc-p" contenteditable="true" data-store="html"
                   data-placeholder="${esc(el.placeholder || "Texte par défaut (modifiable à chaque numéro)…")}">${body}</div>`;
      } else {
        const ov = (st.content[el.id] || {}).html;
        const filled = ov && ov.replace(/<[^>]*>/g, "").trim().length > 0;
        st._zones.push({ id: el.id, filled: !!filled });
        if (el.editable) {
          inner = `<div class="ez fillable ${filled ? "filled" : "empty"}"><span class="pencil">✎</span>` +
            `<div class="doc-p" contenteditable="true" data-store="html" data-el="${el.id}"
               data-placeholder="${esc(el.placeholder || "Rédigez l'analyse de cette section…")}">${ov || ""}</div></div>`;
        } else {
          inner = `<div class="ez locked"><div class="doc-p">${el.html || ""}</div>
             <span class="lockhint">Issu du template</span></div>`;
        }
      }

    } else if (el.type === "field") {
      tabLabel = "CHAMP";
      const cls = el.field === "issue_line" ? "issue-line" : "doc-field";
      inner = `<div class="${cls}">${subst(el.text || "", st.vals, mode === "template" ? "chips" : "values")}</div>`;

    } else if (el.type === "box") {
      tabLabel = el.variant === "toc" ? "ENCADRÉ · SOMMAIRE" : "ENCADRÉ";
      if (el.variant === "toc") {
        let rows = (el.items || []).map((it) => `<div class="r"><span>${esc(it[0])}</span><span>${esc(it[1])}</span></div>`).join("");
        inner = `<div class="toc"><div class="t">${esc(el.title || "")}</div>${rows}</div>`;
      } else {
        const ov = mode === "issue" ? (st.content[el.id] || {}).html : el.html;
        const filled = ov && ov.replace(/<[^>]*>/g, "").trim().length > 0;
        if (mode === "issue") st._zones.push({ id: el.id, filled: !!filled });
        if (mode === "template") {
          inner = `<div class="box-hl"><div class="t">${esc(el.title || "")}</div>` +
            `<div contenteditable="true" data-store="html"
                data-placeholder="Points saillants (modifiable à chaque numéro)…">${el.html || ""}</div></div>`;
        } else if (el.editable) {
          inner = `<div class="ez fillable ${filled ? "filled" : "empty"}"><span class="pencil">✎</span>` +
            `<div class="box-hl"><div class="t">${esc(el.title || "")}</div>` +
            `<div contenteditable="true" data-store="html" data-el="${el.id}"
                data-placeholder="Points saillants du numéro…">${ov || ""}</div></div></div>`;
        } else {
          inner = `<div class="ez locked"><div class="box-hl"><div class="t">${esc(el.title || "")}</div>` +
            `<div>${el.html || ""}</div></div><span class="lockhint">Issu du template</span></div>`;
        }
      }

    } else if (el.type === "map") {
      tabLabel = "CARTE · FIGURE " + el._fig;
      const res = st.resolveMap(el);
      const cap = `<p class="cap"><b>Figure ${el._fig} :</b> ${subst(el.caption || "", st.vals, mode === "template" ? "chips" : "values")}</p>`;
      if (res.kind === "skipped") {
        inner = `<div class="fig"><div class="ez locked" style="border:1.4px dashed #c9d2d6;border-radius:5px;
            padding:14px;text-align:center;color:#8496a0;font-family:var(--ui);font-size:11px">
            Figure masquée pour ce numéro
            <div style="margin-top:8px"><button class="btn sec" data-unhide="${el.id}" style="padding:4px 11px">Afficher</button></div>
          </div>${cap}</div>`;
      } else if (res.kind === "unresolved") {
        inner = `<div class="fig"><div class="unres" data-unres="${el.id}">
            <div class="ic">⚠️</div><b>Figure ${el._fig} impossible à résoudre</b>
            <p>${esc(res.message)}</p>
            <div class="acts">
              ${res.lastKnown ? `<button class="f" data-use="${el.id}" data-time="${res.lastKnown}">Utiliser le ${D.frDate(res.lastKnown)}</button>` : ""}
              <button data-pick="${el.id}">Choisir une date…</button>
              <button data-hide="${el.id}">Masquer la figure</button>
            </div></div>${cap}</div>`;
      } else {
        const chipTxt = mode === "template"
          ? `auto · dernier fichier ≤ fin de période`
          : `FICHIER DU ${D.frDate(res.dateLabel).toUpperCase()}`;
        chip = `<div class="mapchip" data-mapchip="${el.id}">${chipTxt}</div>`;
        inner = `<div class="fig"><div class="mapwrap">${chip}${res.svg}</div>${cap}</div>`;
      }

    } else if (el.type === "divider") {
      tabLabel = "SÉPARATEUR"; inner = `<hr class="doc-divider">`;
    } else if (el.type === "spacer") {
      tabLabel = "ESPACE"; inner = `<div style="height:${el.height_mm || 5}mm"></div>`;
    }

    if (mode !== "template") return inner;

    const tools = `<div class="tools">
        <button data-act="up" title="Monter">↑</button>
        <button data-act="down" title="Descendre">↓</button>
        <button data-act="dup" title="Dupliquer">⧉</button>
        <button data-act="del" title="Supprimer">✕</button></div>`;
    const meta = el.type === "map"
      ? `<div class="meta-chip">${stratLabel(el)}</div>` : "";
    return `<div class="elwrap${sel}" data-el="${el.id}"><div class="tab">${tabLabel}</div>${tools}${inner}${meta}</div>`;
  }

  function stratLabel(el) {
    const m = (el.time_strategy || {}).mode;
    if (m === "latest_at_issue_date") return "auto · dernier ≤ date du numéro";
    if (m === "offset_days") return "auto · décalage " + (el.time_strategy.offset_days || 0) + "j";
    return "auto · dernier ≤ fin de période";
  }

  // ── rows / columns / sections / pages ─────────────────────────────────
  function renderRow(row, st) {
    if (row.kind) return ""; // header/footer handled separately
    const cols = (row.columns || []).map((col) => {
      const w = (col.width / 12 * 100).toFixed(3);
      let body;
      if (!col.elements || !col.elements.length) {
        body = st.mode === "template"
          ? `<div class="col-empty" data-addcol="${row.id}:${col._ci}">＋ Ajouter un élément</div>`
          : "";
      } else {
        body = col.elements.map((el) => renderElement(el, st)).join("");
      }
      return `<div class="col" style="width:${w}%">${body}</div>`;
    }).join("");
    return `<div class="row" data-row="${row.id}">${cols}</div>`;
  }

  function ins(token, st) {
    if (st.mode !== "template" || st.hf) return "";
    return `<div class="ins" data-ins="${token}"><div class="ln"></div><button class="plus">＋</button></div>`;
  }

  function render(canvasEl, state, ctx) {
    // assign column indices + figure numbers (document order)
    let figCount = 0;
    state.pages.forEach((pg) => pg.sections.forEach((sec) => (sec.rows || []).forEach((row) => {
      (row.columns || []).forEach((col, ci) => {
        col._ci = ci;
        (col.elements || []).forEach((el) => { if (el.type === "map") el._fig = ++figCount; });
      });
    })));

    const pt = state.pages.length;
    const st = Object.assign({
      vals: null, _zones: [], _figures: [],
      resolveMap: ctx.resolveMap || (() => ({ kind: "resolved", svg: "", dateLabel: "2026-05-28" })),
    }, ctx);

    let html = "";
    state.pages.forEach((pg, pi) => {
      st.vals = values(state, ctx.issue, pi, pt);
      const dimCls = (ctx.mode === "template" && ctx.hf) ? " hf-dim" : "";
      let body = "";
      pg.sections.forEach((sec) => {
        (sec.rows || []).forEach((row) => { body += ins(row.id + ":before", st) + renderRow(row, st); });
        body += ins(sec.id + ":end", st);
      });
      html += `<div class="sheet${dimCls}" data-page="${pi}">
          <div class="pageno">PAGE ${pi + 1} / ${pt}</div>
          ${state.header && state.header.rows.length ? headerBand(state, st.vals, ctx.mode, ctx.hf, pi, pt) : ""}
          <div class="body-zone">${body}</div>
          ${state.footer && state.footer.rows.length ? footerBand(state, st.vals, ctx.mode) : ""}
        </div>`;
    });

    canvasEl.innerHTML = html;

    // collect figure resolution summary for the issue rail
    const figures = [];
    state.pages.forEach((pg) => pg.sections.forEach((sec) => (sec.rows || []).forEach((row) =>
      (row.columns || []).forEach((col) => (col.elements || []).forEach((el) => {
        if (el.type === "map") {
          const r = st.resolveMap(el);
          figures.push({ id: el.id, num: el._fig, caption: el.caption, resolution: r });
        }
      })))));

    return { figures, zones: st._zones, pageCount: pt };
  }

  global.A4 = { render, subst, values, PH_LABEL, layerThumb: (id, o) => D.mapSVG(D.LAYER_INDEX[id], o) };
})(window);
