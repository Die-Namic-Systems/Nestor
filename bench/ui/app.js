/** Bench results dashboard — loads bench/results/*.json from the same origin. */

const state = {
  bench: "accuracy",
  data: { accuracy: null, margin: null },
  runIndex: { accuracy: -1, margin: -1 },
  measureIndex: { accuracy: 0, margin: 0 },
};

const COLORS = {
  falseSeal: "#f07178",
  recallPara: "#3dd68c",
  recallSurf: "#6eb5ff",
  shipped: "#e6c07b",
};

async function loadBench(name) {
  const res = await fetch(`../results/${name}.json`);
  if (!res.ok) {
    throw new Error(`${name}.json — ${res.status} ${res.statusText}`);
  }
  return res.json();
}

function pct(n, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function defaultRunIndex(doc) {
  const runs = doc?.runs ?? [];
  for (let i = runs.length - 1; i >= 0; i--) {
    if (runs[i].complete) return i;
  }
  return runs.length ? runs.length - 1 : -1;
}

function runLabel(run, i) {
  const id = run.run_id || `run ${i + 1}`;
  const rev = run.environment?.git_rev ?? "?";
  const when = run.recorded_at?.slice(0, 10) ?? "";
  const flag = run.complete ? "" : " · incomplete";
  return `${id} · ${rev} · ${when}${flag}`;
}

function shippedThreshold(run) {
  return (
    run.params?.shipped_seal_threshold ??
    run.params?.shipped_SEAL_THRESHOLD ??
    0.92
  );
}

function sweepAt(sweep, t) {
  return sweep.find((row) => Math.abs(row.threshold - t) < 1e-6);
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "style") node.setAttribute("style", v);
    else if (k.startsWith("on") && typeof v === "function")
      node.addEventListener(k.slice(2).toLowerCase(), v);
    else node.setAttribute(k, v);
  }
  // A single child, not wrapped in an array, is the natural thing to write and
  // several call sites here do — el("li", {}, el("button", ...)). Iterating a
  // DOM node throws "children is not iterable" and takes the whole tab down
  // with it, which is what the Accuracy tab did before this line existed: the
  // page defaulted to a different tab, so nobody saw it.
  for (const c of Array.isArray(children) ? children : [children]) {
    if (c == null) continue;
    node.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function lineChart({ width, height, padding, series, vline }) {
  const w = width;
  const h = height;
  const pad = padding;
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;

  const xs = series[0]?.points.map((p) => p.x) ?? [];
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMax = 1;

  const xScale = (x) => pad.l + ((x - xMin) / (xMax - xMin || 1)) * innerW;
  const yScale = (y) => pad.t + innerH - (y / yMax) * innerH;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Threshold sweep chart");

  const gridY = [0, 0.25, 0.5, 0.75, 1];
  for (const gy of gridY) {
    const y = yScale(gy);
    svg.append(
      elNS("line", {
        x1: pad.l,
        y1: y,
        x2: w - pad.r,
        y2: y,
        stroke: "#2a3344",
        "stroke-width": 1,
      }),
      elNS("text", {
        x: pad.l - 8,
        y: y + 4,
        fill: "#8b96a8",
        "font-size": 10,
        "text-anchor": "end",
      }, pct(gy, 0))
    );
  }

  for (const x of xs) {
    const px = xScale(x);
    svg.append(
      elNS("line", {
        x1: px,
        y1: pad.t,
        x2: px,
        y2: h - pad.b,
        stroke: "#1e2430",
        "stroke-width": 1,
      }),
      elNS("text", {
        x: px,
        y: h - 6,
        fill: "#8b96a8",
        "font-size": 10,
        "text-anchor": "middle",
      }, String(x))
    );
  }

  if (vline != null) {
    const vx = xScale(vline);
    svg.append(
      elNS("line", {
        x1: vx,
        y1: pad.t,
        x2: vx,
        y2: h - pad.b,
        stroke: COLORS.shipped,
        "stroke-width": 2,
        "stroke-dasharray": "6 4",
      })
    );
  }

  for (const s of series) {
    const d = s.points
      .map((p, i) => `${i ? "L" : "M"} ${xScale(p.x)} ${yScale(p.y)}`)
      .join(" ");
    svg.append(
      elNS("path", {
        d,
        fill: "none",
        stroke: s.color,
        "stroke-width": 2.5,
        "stroke-linejoin": "round",
      })
    );
  }

  return svg;
}

function elNS(tag, attrs, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

function renderAccuracy(main, run) {
  const measurements = run.measurements ?? [];
  const idx = Math.min(state.measureIndex.accuracy, measurements.length - 1);
  const m = measurements[idx];
  if (!m) {
    main.textContent = "No measurements in this run.";
    return;
  }

  const ship = shippedThreshold(run);
  const atShip = sweepAt(m.sweep, ship);

  const layout = el("div", { className: "grid-two" });
  const sidebar = el("div", { className: "panel" }, [
    el("h2", { text: "Corpus × size" }),
    el(
      "ul",
      { className: "measure-list" },
      measurements.map((row, i) => {
        const rowAt = sweepAt(row.sweep, ship);
        return el(
          "li",
          {},
          el(
            "button",
            {
              type: "button",
              className: i === idx ? "active" : "",
              onClick: () => {
                state.measureIndex.accuracy = i;
                render();
              },
            },
            [
              `${row.corpus} · ${row.size.toLocaleString()} pairs`,
              el("span", {
                className: "sub",
                text: rowAt
                  ? `@ ${ship} false-seal ${pct(rowAt.false_seal_rate)} · para ${pct(rowAt.recall_paraphrase)}`
                  : "",
              }),
            ]
          )
        );
      })
    ),
  ]);

  const chartPanel = el("div", { className: "panel" });
  chartPanel.append(el("h2", { text: "Threshold sweep" }));

  const series = [
    {
      name: "False-seal rate",
      color: COLORS.falseSeal,
      points: m.sweep.map((r) => ({ x: r.threshold, y: r.false_seal_rate })),
    },
    {
      name: "Recall (paraphrase)",
      color: COLORS.recallPara,
      points: m.sweep.map((r) => ({ x: r.threshold, y: r.recall_paraphrase })),
    },
    {
      name: "Recall (surface)",
      color: COLORS.recallSurf,
      points: m.sweep.map((r) => ({ x: r.threshold, y: r.recall_surface })),
    },
  ];

  const chartWrap = el("div", { className: "chart-wrap" });
  chartWrap.append(
    lineChart({
      width: 720,
      height: 300,
      padding: { l: 44, r: 16, t: 16, b: 28 },
      series,
      vline: ship,
    })
  );
  chartPanel.append(chartWrap);

  chartPanel.append(
    el("div", { className: "legend" }, [
      ...series.map((s) =>
        el("span", {}, [
          el("span", { className: "swatch", style: `background:${s.color}` }),
          s.name,
        ])
      ),
      el("span", {}, [
        el("span", {
          className: "swatch",
          style: `background:${COLORS.shipped}`,
        }),
        `Shipped threshold (${ship})`,
      ]),
    ])
  );

  const stats = el("div", { className: "stats" });
  if (atShip) {
    const fs = atShip.false_seal_rate;
    stats.append(
      stat("False-seal @ shipped", pct(fs), fs > 0.05 ? "bad" : "ok"),
      stat("Recall paraphrase", pct(atShip.recall_paraphrase), ""),
      stat("Recall surface", pct(atShip.recall_surface), ""),
      stat("Misrouted", pct(atShip.misroute_rate), "")
    );
  }
  chartPanel.append(stats);

  const tablePanel = el("div", { className: "panel", style: "margin-top:1rem" });
  tablePanel.append(el("h2", { text: "Full sweep" }));
  const tbl = el("table", { className: "data" });
  tbl.append(
    el("thead", {}, el("tr", {}, [
      "Threshold",
      "False-seal",
      "Para recall",
      "Surface recall",
      "Misroute",
    ].map((h) => el("th", { text: h }))))
  );
  const tbody = el("tbody");
  for (const row of m.sweep) {
    const hi = Math.abs(row.threshold - ship) < 1e-6;
    tbody.append(
      el("tr", {}, [
        el("td", { text: row.threshold.toFixed(2) + (hi ? " ★" : "") }),
        el("td", { className: "num", text: pct(row.false_seal_rate) }),
        el("td", { className: "num", text: pct(row.recall_paraphrase) }),
        el("td", { className: "num", text: pct(row.recall_surface) }),
        el("td", { className: "num", text: pct(row.misroute_rate) }),
      ])
    );
  }
  tbl.append(tbody);
  tablePanel.append(tbl);

  const examples = m.worst_false_seals ?? [];
  if (examples.length) {
    const ex = el("div", { className: "examples" });
    const det = el("details", {}, [
      el("summary", { text: `Worst false-seal probes (${examples.length} shown)` }),
      ...examples.map((e) =>
        el("div", { className: "example-row" }, [
          el("div", { className: "sim", text: `similarity ${e.similarity}` }),
          el("blockquote", { text: `Asked: ${e.asked}` }),
          el("blockquote", {
            text: `Would serve: ${e.would_serve_source} → ${e.would_serve_target}`,
          }),
        ])
      ),
    ]);
    ex.append(det);
    chartPanel.append(ex);
  }

  layout.append(sidebar, el("div", {}, [chartPanel, tablePanel]));
  main.replaceChildren(layout);
}

function stat(label, value, tone) {
  return el("div", { className: "stat" }, [
    el("div", { className: "label", text: label }),
    el("div", { className: `value ${tone}`, text: value }),
  ]);
}

function renderMargin(main, run) {
  const measurements = run.measurements ?? [];
  const idx = Math.min(state.measureIndex.margin, measurements.length - 1);
  const m = measurements[idx];
  if (!m) {
    main.textContent = "No measurements in this run.";
    return;
  }

  const thresholds = [...new Set(m.grid.map((g) => g.threshold))].sort(
    (a, b) => a - b
  );
  const margins = [...new Set(m.grid.map((g) => g.margin))].sort(
    (a, b) => a - b
  );
  const ship = shippedThreshold(run);

  const layout = el("div", { className: "grid-two" });
  layout.append(
    el("div", { className: "panel" }, [
      el("h2", { text: "Corpus × size" }),
      el(
        "ul",
        { className: "measure-list" },
        measurements.map((row, i) =>
          el("li", {}, el("button", {
            type: "button",
            className: i === idx ? "active" : "",
            onClick: () => {
              state.measureIndex.margin = i;
              render();
            },
            text: `${row.corpus} · ${row.size.toLocaleString()} pairs`,
          }))
        )
      ),
    ])
  );

  const panel = el("div", { className: "panel" });
  panel.append(
    el("h2", { text: "False-seal rate (threshold × margin)" }),
    el("p", {
      style: "color:var(--muted);font-size:0.85rem;margin:0 0 0.75rem",
      text: run.notes?.slice(0, 200) ?? "",
    })
  );

  const lookup = new Map();
  let maxFs = 0;
  for (const cell of m.grid) {
    lookup.set(`${cell.threshold}:${cell.margin}`, cell);
    maxFs = Math.max(maxFs, cell.false_seal_rate);
  }

  const heat = el("div", { className: "heatmap" });
  const tbl = el("table", { className: "data" });
  const head = el("tr", {}, [
    el("th", { text: "t \\ margin" }),
    ...margins.map((mg) => el("th", { text: String(mg) })),
  ]);
  tbl.append(el("thead", {}, head));
  const tbody = el("tbody");
  for (const t of thresholds) {
    const row = el("tr", {}, [
      el("td", {
        text: t.toFixed(2) + (Math.abs(t - ship) < 1e-6 ? " ★" : ""),
      }),
    ]);
    for (const mg of margins) {
      const cell = lookup.get(`${t}:${mg}`);
      const fs = cell?.false_seal_rate ?? 0;
      const intensity = maxFs > 0 ? fs / maxFs : 0;
      const cls = fs === 0 ? "lo" : intensity > 0.5 ? "hi" : "";
      row.append(
        el("td", {
          className: `num ${cls}`,
          title: cell ? `recall ${pct(cell.recall)}` : "",
          text: cell ? pct(fs) : "—",
        })
      );
    }
    tbody.append(row);
  }
  tbl.append(tbody);
  heat.append(tbl);
  panel.append(heat);
  layout.append(el("div", {}, [panel]));
  main.replaceChildren(layout);
}

function renderGlobalControls() {
  const host = document.getElementById("global-controls");
  const doc = state.data[state.bench];
  const runs = doc?.runs ?? [];
  const ri = state.runIndex[state.bench];
  host.replaceChildren(
    el("label", {}, [
      "Run",
      el("select", {
        id: "run-select",
        onChange: (e) => {
          state.runIndex[state.bench] = Number(e.target.value);
          state.measureIndex[state.bench] = 0;
          render();
        },
      }, runs.map((run, i) =>
        el("option", { value: String(i), text: runLabel(run, i) })
      )),
    ])
  );
  const sel = host.querySelector("select");
  if (sel && ri >= 0) sel.value = String(ri);

  const run = runs[ri];
  const meta = document.getElementById("run-meta");
  if (run) {
    meta.textContent = [
      run.run_id,
      run.environment?.git_rev,
      run.complete ? "complete" : "INCOMPLETE",
      `${run.measurements?.length ?? 0} rows`,
    ].join(" · ");
  } else {
    meta.textContent = "";
  }
}

function render() {
  const main = document.getElementById("app");
  const doc = state.data[state.bench];
  const runs = doc?.runs ?? [];
  let ri = state.runIndex[state.bench];
  if (ri < 0 || ri >= runs.length) ri = defaultRunIndex(doc);
  state.runIndex[state.bench] = ri;
  const run = runs[ri];

  renderGlobalControls();

  if (!run) {
    main.replaceChildren(
      el("p", {
        className: "error",
        text: `No runs in results/${state.bench}.json — run bench_${state.bench}.py first.`,
      })
    );
    return;
  }

  const frag = [];
  if (!run.complete) {
    frag.push(
      el("div", {
        className: "banner",
        text: "This run is marked incomplete — numbers may be a prefix of the planned sweep. Check complete in the JSON before citing.",
      })
    );
  }
  main.replaceChildren(...frag);

  const slot = el("div");
  main.append(slot);

  if (state.bench === "accuracy") renderAccuracy(slot, run);
  else renderMargin(slot, run);
}

function bindTabs() {
  document.querySelectorAll("nav.tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.bench = btn.dataset.bench;
      document.querySelectorAll("nav.tabs .tab").forEach((t) => {
        const on = t === btn;
        t.classList.toggle("active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      render();
    });
  });
}

async function init() {
  bindTabs();
  const main = document.getElementById("app");
  try {
    const [accuracy, margin] = await Promise.all([
      loadBench("accuracy").catch(() => ({ bench: "accuracy", runs: [] })),
      loadBench("margin").catch(() => ({ bench: "margin", runs: [] })),
    ]);
    state.data.accuracy = accuracy;
    state.data.margin = margin;
    state.runIndex.accuracy = defaultRunIndex(accuracy);
    state.runIndex.margin = defaultRunIndex(margin);
    render();
  } catch (err) {
    main.replaceChildren(
      el("p", { className: "error", text: String(err.message || err) })
    );
  }
}

init();
