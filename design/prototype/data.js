/* ============================================================================
   Bulletin Studio prototype — mock data (no backend)
   - GEO_TREE  : geomanager Category → Dataset → Layer tree
   - mapSVG()  : renders a fake "Burkina Faso" choropleth for a given layer
   - SAMPLE_TEMPLATE / SAMPLE_ISSUE : seed content matching the agromet bulletin
   ========================================================================= */
(function (global) {
  "use strict";

  const uid = (p) => (p || "el") + "-" + Math.random().toString(36).slice(2, 9);
  const clone = (o) => JSON.parse(JSON.stringify(o));

  // rough Burkina Faso outline on a 0..240 x 0..180 board
  const BF =
    "M22,68 C26,50 42,38 62,31 C84,23 112,18 134,22 C156,26 176,31 188,45 " +
    "C198,56 205,69 199,83 C193,95 181,99 174,111 C167,123 157,125 143,127 " +
    "C133,139 117,146 103,141 C91,137 81,143 69,138 C55,132 41,124 33,112 " +
    "C24,101 18,86 22,68 Z";

  // internal faint admin curves + city dots, shared
  const ADMIN =
    "M62,31 C70,55 65,80 75,105 M134,22 C125,50 132,82 122,110 " +
    "M188,45 C165,60 150,62 122,68 M33,112 C60,100 85,108 103,118 " +
    "M103,141 C110,118 118,110 122,90";
  const CITIES = [
    [118, 74, "OUAGA"], [62, 112, "BOBO"], [172, 52, "DORI"],
    [96, 50, "OUAHIGOUYA"], [150, 110, "GAOUA"],
  ];

  // colour palettes + legends
  const PALETTES = {
    pluvio: {
      stops: ["#eef4f8", "#cfe5f2", "#9cc9e3", "#5d9ec6", "#2f6f9e", "#1d4f78"],
      labels: ["0", "5", "25", "50", "80", "140"], unit: "Pluviométrie (mm)",
    },
    anomaly: {
      stops: ["#9a1f2b", "#d6604d", "#f4a582", "#d1e5f0", "#67a9cf", "#2166ac"],
      labels: ["très déf.", "déf.", "norm.", "exc.", "fort exc.", ""], unit: "Anomalie (%)",
    },
    temp: {
      stops: ["#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15"],
      labels: ["< -1", "-0.5", "0", "+0.5", "> +1"], unit: "Écart température (°C)",
    },
    ndvi: {
      stops: ["#f7fcf5", "#c7e9c0", "#74c476", "#31a354", "#006d2c"],
      labels: ["baisse", "", "normal", "", "hausse"], unit: "Anomalie NDVI",
    },
  };

  // distinct blob layouts so different layers look different
  const SHAPES = {
    south: [[78, 118, 56, 34, 5], [66, 126, 30, 18, 5], [150, 112, 44, 24, 4],
            [160, 60, 50, 28, 2], [80, 55, 46, 24, 1], [120, 84, 36, 19, 3]],
    north: [[150, 55, 56, 30, 5], [120, 45, 40, 20, 4], [170, 62, 34, 18, 5],
            [70, 110, 44, 26, 1], [110, 120, 40, 22, 2]],
    spread:[[60, 60, 40, 24, 4], [150, 65, 44, 26, 1], [100, 115, 50, 28, 3],
            [175, 110, 30, 18, 4], [40, 100, 26, 16, 2]],
    east:  [[160, 70, 50, 30, 4], [180, 100, 34, 20, 5], [120, 90, 40, 22, 2],
            [70, 70, 36, 22, 1], [80, 120, 30, 18, 3]],
  };

  function mapSVG(layer, opts) {
    opts = opts || {};
    const pal = PALETTES[layer.palette] || PALETTES.pluvio;
    const shape = SHAPES[layer.shape] || SHAPES.south;
    const cid = "clip-" + Math.random().toString(36).slice(2, 8);
    const showLegend = opts.legend !== false;
    const showBound = opts.boundaries !== false;
    const h = showLegend ? 182 : 158;

    let blobs = "";
    shape.forEach((b) => {
      blobs += `<ellipse cx="${b[0]}" cy="${b[1]}" rx="${b[2]}" ry="${b[3]}" fill="${pal.stops[b[4]]}"/>`;
    });

    let cities = "";
    if (opts.cities !== false) {
      CITIES.forEach((c) => {
        cities += `<circle cx="${c[0]}" cy="${c[1]}" r="1.4" fill="#222"/>` +
          `<text x="${c[0] + 3}" y="${c[1] + 2}" font-family="Arial" font-size="5.6" fill="#333">${c[2]}</text>`;
      });
    }

    let legend = "";
    if (showLegend) {
      const n = pal.stops.length, w = 132, sw = w / n;
      let cells = "", labels = "";
      pal.stops.forEach((s, i) => {
        cells += `<rect x="${i * sw}" width="${sw}" height="6" fill="${s}" stroke="#999" stroke-width=".3"/>`;
        if (pal.labels[i]) labels += `<text x="${i * sw}" y="13" font-family="Arial" font-size="5" fill="#333">${pal.labels[i]}</text>`;
      });
      legend = `<g transform="translate(${(240 - w) / 2},162)">${cells}${labels}` +
        `<text x="${w / 2}" y="-3" text-anchor="middle" font-family="Arial" font-size="5.6" fill="#333">${pal.unit}</text></g>`;
    }

    return `<svg class="map" viewBox="0 0 240 ${h}" xmlns="http://www.w3.org/2000/svg">` +
      `<rect width="240" height="${h}" fill="#fdfdfc"/>` +
      `<defs><clipPath id="${cid}"><path d="${BF}"/></clipPath></defs>` +
      `<g clip-path="url(#${cid})"><rect width="240" height="180" fill="#eaf3fa"/>${blobs}</g>` +
      (showBound ? `<path d="${BF}" fill="none" stroke="#444" stroke-width="1.4"/>` +
        `<path d="${ADMIN}" fill="none" stroke="#777" stroke-width=".5" opacity=".7"/>` : "") +
      `<text x="9" y="13" font-family="Arial" font-size="7" fill="#888">N ↑</text>` +
      cities + legend + `</svg>`;
  }

  // ── geomanager tree (raster layers only, with timestamps) ──────────────
  const GEO_TREE = [
    { id: 1, title: "Pluviométrie", datasets: [
      { id: "d1", title: "Cumul pluviométrique décadaire", layers: [
        { id: "lyr-cumul", title: "Cumul 10 jours — stations interpolées", palette: "pluvio",
          shape: "south", timestamps: ["2026-05-28", "2026-05-18", "2026-05-08", "2026-04-28"] },
      ]},
      { id: "d2", title: "Anomalie pluviométrique", layers: [
        { id: "lyr-anom2025", title: "Anomalie / année passée (2025)", palette: "anomaly",
          shape: "north", timestamps: ["2026-06-05", "2026-06-10"] }, /* only AFTER period → unresolved demo */
        { id: "lyr-anomMoy", title: "Anomalie / moyenne 2016-2025", palette: "anomaly",
          shape: "spread", timestamps: ["2026-05-28", "2026-05-18"] },
      ]},
    ]},
    { id: 2, title: "Températures", datasets: [
      { id: "d3", title: "Température moyenne", layers: [
        { id: "lyr-temp", title: "Anomalie température / décade préc.", palette: "temp",
          shape: "spread", timestamps: ["2026-05-31", "2026-05-21", "2026-05-11"] },
      ]},
    ]},
    { id: 3, title: "Humidité", datasets: [
      { id: "d4", title: "Humidité relative moyenne", layers: [
        { id: "lyr-hum", title: "Anomalie humidité / décade préc.", palette: "anomaly",
          shape: "east", timestamps: ["2026-05-31", "2026-05-21"] },
      ]},
    ]},
    { id: 4, title: "Végétation", datasets: [
      { id: "d5", title: "Indice NDVI", layers: [
        { id: "lyr-ndvi", title: "Anomalie NDVI décade", palette: "ndvi",
          shape: "south", timestamps: ["2026-05-25", "2026-05-15"] },
      ]},
    ]},
  ];

  const LAYER_INDEX = {};
  GEO_TREE.forEach((c) => c.datasets.forEach((d) => d.layers.forEach((l) => {
    LAYER_INDEX[l.id] = Object.assign({ category: c.title, dataset: d.title, datasetId: d.id, categoryId: c.id }, l);
  })));

  // ── sample agrometeorological template (2 pages) ───────────────────────
  function sampleTemplate() {
    return {
      version: 1, name: "Bulletin Agrométéorologique Décadaire", language: "fr",
      page_size: "A4", orientation: "portrait", margins_mm: [30, 12, 22, 12],
      header: { rows: [{ id: uid("row"), kind: "header-table" }] },
      footer: { rows: [{ id: uid("row"), kind: "footer-band" }] },
      pages: [
        { id: uid("pg"), sections: [{ id: uid("sec"), rows: [
          { id: uid("row"), columns: [{ width: 12, elements: [
            { id: uid("el"), type: "field", field: "issue_line",
              text: "N° {issue_number} période du {period_start} au {period_end}" },
          ]}]},
          { id: uid("row"), columns: [
            { width: 4, elements: [{ id: uid("el"), type: "box", variant: "toc", title: "Dans ce numéro :",
              items: [["Situation pluviométrique", "1"], ["Situation agrométéorologique", "2"],
                      ["Perspectives", "2"], ["Avis et conseils", "2"]] }] },
            { width: 8, elements: [{ id: uid("el"), type: "box", variant: "highlights", editable: true,
              title: "Sommaire :",
              html: "" }] },
          ]},
          { id: uid("row"), columns: [
            { width: 6, elements: [
              { id: uid("el"), type: "title", level: 2, text: "Situation pluviométrique" },
              { id: uid("el"), type: "text", editable: true, html: "" },
              { id: uid("el"), type: "text", editable: true, html: "" },
            ]},
            { width: 6, elements: [
              { id: uid("el"), type: "map", layer_id: "lyr-cumul",
                time_strategy: { mode: "latest_at_period_end" }, use_layer_style: true,
                show_legend: true, show_boundaries: true,
                caption: "Cumul pluviométrique du {period_start} au {period_end}" },
              { id: uid("el"), type: "map", layer_id: "lyr-anom2025",
                time_strategy: { mode: "latest_at_period_end" }, use_layer_style: true,
                show_legend: true, show_boundaries: true,
                caption: "Anomalie cumul pluviométrique par rapport à 2025" },
            ]},
          ]},
        ]}]},
        { id: uid("pg"), sections: [{ id: uid("sec"), page_break_before: true, rows: [
          { id: uid("row"), columns: [
            { width: 6, elements: [
              { id: uid("el"), type: "title", level: 2, text: "Situation agrométéorologique" },
              { id: uid("el"), type: "title", level: 3, text: "Évolution de la température moyenne" },
              { id: uid("el"), type: "text", editable: true, html: "" },
            ]},
            { width: 6, elements: [
              { id: uid("el"), type: "map", layer_id: "lyr-temp",
                time_strategy: { mode: "latest_at_period_end" }, use_layer_style: true,
                show_legend: true, show_boundaries: true,
                caption: "Anomalie des températures moyennes par rapport à la décade précédente" },
            ]},
          ]},
          { id: uid("row"), columns: [
            { width: 6, elements: [
              { id: uid("el"), type: "title", level: 3, text: "Évolution de l'humidité relative" },
              { id: uid("el"), type: "text", editable: true, html: "" },
            ]},
            { width: 6, elements: [
              { id: uid("el"), type: "map", layer_id: "lyr-hum",
                time_strategy: { mode: "latest_at_period_end" }, use_layer_style: true,
                show_legend: true, show_boundaries: true,
                caption: "Anomalie des humidités moyennes par rapport à la décade précédente" },
            ]},
          ]},
        ]}]},
      ],
    };
  }

  // sample issue meta + prefilled content (used by issue-fill)
  const SAMPLE_ISSUE = {
    issue_number: "15", issue_date: "2026-06-03",
    period_start: "2026-05-21", period_end: "2026-05-31",
    // element_id keyed overrides are filled at runtime against the template ids
    prefill: {
      highlights: "- Manifestations pluvieuses et orageuses dans plusieurs localités du pays<br>" +
        "- Pluviométrie globalement déficitaire à normale par rapport à la décade de l'année passée<br>" +
        "- <b>Température moyenne en baisse importante</b>",
      pluvio1: "Les hauteurs de pluie décadaires enregistrées ont varié de 0 mm dans certaines localités du " +
        "pays à 136,8 mm en sept (7) jours de pluie à Loropéni (Poni). Les cumuls les plus importants ont " +
        "concerné les régions du Guiriko, du Djôro et des Tannounyan (figure 1).",
      // pluvio2 left empty on purpose to demo the "empty zone" state
    },
  };

  global.STUDIO_DATA = {
    uid, clone, GEO_TREE, LAYER_INDEX, PALETTES, mapSVG, sampleTemplate, SAMPLE_ISSUE,
    // month names for fr date formatting
    frDate(iso) {
      if (!iso) return "";
      const M = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"];
      const d = new Date(iso + "T00:00:00");
      return d.getDate() + " " + M[d.getMonth()] + " " + d.getFullYear();
    },
    frDateShort(iso) {
      if (!iso) return "";
      const d = new Date(iso + "T00:00:00");
      return String(d.getDate()).padStart(2, "0") + "/" + String(d.getMonth() + 1).padStart(2, "0") +
        "/" + d.getFullYear();
    },
  };
})(window);
