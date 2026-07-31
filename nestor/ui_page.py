"""The single page :mod:`nestor.ui` serves.

Kept in its own module so the server stays readable — this is markup, not
logic. Everything is inline: no CDN, no fonts, no images fetched, nothing that
reaches the network. The Content-Security-Policy sent with it enforces that,
so the surface that displays the sealed memory cannot ship it anywhere.

All data is written into the DOM through ``textContent`` (see the ``h`` helper)
rather than ``innerHTML``. Sealed text is arbitrary human input and the curator
view exists precisely to look at rows a stranger may have written.
"""
from __future__ import annotations

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nestor</title>
<style>
:root {
  --bg: #fbfaf8; --panel: #ffffff; --ink: #1b1a17; --muted: #6b6862;
  --line: #e4e0d9; --accent: #3b5f4a; --sealed: #2f6f4e; --draft: #9a6b16;
  --pending: #6b6862; --rejected: #a33a2f; --shadow: 0 1px 2px rgba(0,0,0,.05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14150f; --panel: #1c1e17; --ink: #ece9e1; --muted: #9c988e;
    --line: #2e3128; --accent: #8fbc9b; --sealed: #7fc39a; --draft: #d7a94f;
    --pending: #9c988e; --rejected: #e08376; --shadow: none;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .86em; }
header {
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
  padding: 14px 22px; border-bottom: 1px solid var(--line); background: var(--panel);
}
.brand { display: flex; align-items: baseline; gap: 10px; }
.brand b { font-size: 19px; letter-spacing: .02em; }
.brand span { color: var(--muted); font-style: italic; font-size: 13px; }
.spacer { flex: 1; }
.who { display: flex; align-items: center; gap: 8px; }
.who label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }
input, select, textarea, button {
  font: inherit; color: inherit; background: var(--panel);
  border: 1px solid var(--line); border-radius: 7px; padding: 6px 9px;
}
textarea { width: 100%; min-height: 78px; resize: vertical; }
button { cursor: pointer; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .45; cursor: not-allowed; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--panel); font-weight: 600; }
@media (prefers-color-scheme: dark) { button.primary { color: #14150f; } }
button.danger { color: var(--rejected); }
button.small { padding: 3px 8px; font-size: 13px; }
a { color: inherit; text-decoration: none; }
nav { display: flex; gap: 4px; padding: 10px 22px 0; border-bottom: 1px solid var(--line); background: var(--panel); }
nav button {
  border: 1px solid transparent; border-bottom: none; border-radius: 8px 8px 0 0;
  background: none; padding: 8px 16px; color: var(--muted); margin-bottom: -1px;
}
nav button.on { color: var(--ink); background: var(--bg); border-color: var(--line); font-weight: 600; }
main { padding: 22px; max-width: 1180px; margin: 0 auto; }
.badges { display: flex; gap: 6px; flex-wrap: wrap; }
.badge {
  font-size: 12px; padding: 3px 9px; border-radius: 999px;
  border: 1px solid var(--line); color: var(--muted); white-space: nowrap;
}
.badge.warn { color: var(--draft); border-color: var(--draft); }
.badge.bad { color: var(--rejected); border-color: var(--rejected); }
.badge.good { color: var(--sealed); border-color: var(--sealed); }
.card {
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  padding: 16px; margin-bottom: 14px; box-shadow: var(--shadow);
}
.card h2 { margin: 0 0 4px; font-size: 15px; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: 1fr 380px; gap: 16px; align-items: start; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
.mark { font-weight: 700; width: 1.1em; display: inline-block; text-align: center; }
.sealed { color: var(--sealed); } .draft { color: var(--draft); }
.pending { color: var(--pending); } .rejected { color: var(--rejected); }
.muted { color: var(--muted); }
.small { font-size: 13px; }
.pair { border-top: 1px solid var(--line); padding: 11px 2px; cursor: pointer; }
.pair:first-of-type { border-top: none; }
.pair:hover { background: color-mix(in srgb, var(--accent) 7%, transparent); }
.pair .texts { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.pair .src { font-weight: 600; }
.pair .arrow { color: var(--muted); }
.seg { border-top: 1px solid var(--line); padding: 12px 2px; }
.seg:first-of-type { border-top: none; }
.chip {
  display: inline-block; font-size: 12px; padding: 2px 7px; margin: 2px 4px 2px 0;
  border: 1px solid var(--line); border-radius: 6px; color: var(--muted);
}
.bar { height: 5px; border-radius: 3px; background: var(--line); overflow: hidden; width: 120px; }
.bar > i { display: block; height: 100%; background: var(--accent); }
.empty { color: var(--muted); padding: 14px 2px; }
table { width: 100%; border-collapse: collapse; }
td, th { text-align: left; padding: 7px 8px; border-top: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; border-top: none; }
#toast {
  position: fixed; right: 18px; bottom: 18px; max-width: 460px; display: flex;
  flex-direction: column; gap: 8px; z-index: 20;
}
#toast div {
  background: var(--panel); border: 1px solid var(--line); border-left-width: 4px;
  border-radius: 9px; padding: 10px 13px; box-shadow: 0 6px 20px rgba(0,0,0,.14);
}
#toast div.ok { border-left-color: var(--sealed); }
#toast div.err { border-left-color: var(--rejected); }
dialog {
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  color: var(--ink); padding: 18px; min-width: min(420px, 92vw);
}
dialog::backdrop { background: rgba(0,0,0,.35); }
</style>
</head>
<body>
<header>
  <div class="brand"><b>Nestor</b> <span>In medio, fides</span></div>
  <div class="spacer"></div>
  <div class="who">
    <label for="verifier">acting as</label>
    <input id="verifier" placeholder="your name" size="14" autocomplete="off">
  </div>
  <div class="badges" id="badges"></div>
</header>
<nav id="tabs"></nav>
<main id="view"></main>
<div id="toast"></div>
<dialog id="ask-dialog">
  <form method="dialog">
    <p id="ask-title" style="margin:0 0 10px;font-weight:600"></p>
    <input id="ask-input" style="width:100%" autocomplete="off">
    <div class="row" style="justify-content:flex-end;margin-top:14px">
      <button value="">Cancel</button>
      <button class="primary" id="ask-ok" value="ok">OK</button>
    </div>
  </form>
</dialog>

<script>
"use strict";

const TABS = [
  ["queue",  "Queue"],
  ["memory", "Memory"],
  ["ask",    "Ask"],
  ["ledger", "Ledger"],
];

const S = { tab: "queue", state: null, pairs: [], detail: null, queue: null,
            ledger: null, result: null, filters: { status: "", contains: "", verifier: "",
            unverifiable: "" } };

/* ---------- tiny DOM helper: every value lands as text, never as markup ---- */
function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k === "html") throw new Error("no innerHTML in this page");
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return e;
}
const $ = (id) => document.getElementById(id);

function toast(message, kind) {
  const box = h("div", { class: kind === "err" ? "err" : "ok" }, message);
  $("toast").append(box);
  setTimeout(() => box.remove(), kind === "err" ? 9000 : 4000);
}

function verifier() { return $("verifier").value.trim(); }

function askFor(title, placeholder) {
  return new Promise((resolve) => {
    const dlg = $("ask-dialog"), input = $("ask-input");
    $("ask-title").textContent = title;
    input.value = ""; input.placeholder = placeholder || "";
    // Enter must mean OK, not "the first submit button in the form" (Cancel).
    input.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); $("ask-ok").click(); } };
    dlg.onclose = () => resolve(dlg.returnValue === "ok" ? input.value.trim() : null);
    dlg.showModal(); input.focus();
  });
}

/* ---------- API ----------------------------------------------------------- */
async function api(path, body) {
  const opts = { headers: { "X-Nestor-UI": "1" } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ error: res.statusText }));
  if (!res.ok) { const e = new Error(data.error || "request failed"); e.data = data; e.status = res.status; throw e; }
  return data;
}

async function act(path, body, okMessage) {
  try {
    const out = await api(path, body);
    if (okMessage) toast(okMessage, "ok");
    await refresh();
    return out;
  } catch (e) {
    if (e.data && (e.data.code === "conflicting_seal" || e.data.code === "rejected_pair")) throw e;
    toast(e.message, "err");
    return null;
  }
}

/* ---------- shared bits --------------------------------------------------- */
function mark(state) {
  const m = { sealed: "✓", draft: "~", pending: "!", rejected: "✗" }[state] || "?";
  return h("span", { class: "mark " + (state || "pending"), text: m });
}

function servableChip(pair) {
  if (pair.status !== "sealed") return null;
  return pair.servable
    ? h("span", { class: "chip", text: "servable" })
    : h("span", { class: "badge bad", title: "says sealed, but Nestor would refuse to serve it",
                  text: "not servable" });
}

function sim(value) {
  return h("span", { class: "row", style: "gap:6px" },
    h("span", { class: "bar" }, h("i", { style: "width:" + Math.round(value * 100) + "%" })),
    h("span", { class: "small muted mono", text: value.toFixed(3) }));
}

/* ---------- Queue --------------------------------------------------------- */
function viewQueue() {
  const view = $("view");
  if (!S.state.capabilities.queue) {
    view.append(h("div", { class: "card" },
      h("p", { class: "empty", text: "This store cannot list the review queue " +
        "(storage.supports_queue). Sealing and curation still work." })));
    return;
  }
  const q = S.queue || { documents: [], pending: 0 };
  view.append(h("div", { class: "card" },
    h("h2", { text: "Awaiting a human" }),
    h("p", { class: "muted small", text: q.pending
      ? q.pending + " segment(s) the cascade could not serve from the sealed memory. " +
        "Sealing one enters it into tier 1; rejecting one means that candidate is never offered for this text again."
      : "Nothing queued. Every segment the cascade has seen was either served from the sealed memory or already decided." })));

  for (const doc of q.documents) {
    const card = h("div", { class: "card" },
      h("div", { class: "row" },
        h("b", { text: doc.title || "(untitled)" }),
        h("span", { class: "chip", text: (doc.source_lang || "?") + " → " + (doc.target_lang || "?") }),
        h("span", { class: "chip mono", text: (doc.id || "").slice(0, 8) })));
    for (const seg of doc.segments) card.append(segmentRow(doc, seg));
    $("view").append(card);
  }
}

function segmentRow(doc, seg) {
  const ro = S.state.read_only;
  // The candidate is editable: review is usually "nearly", not yes or no. What
  // is sealed is what the reviewer leaves in this box, and the ledger records
  // whether they changed it.
  const box = h("input", { class: "cand", value: seg.candidate || "", disabled: ro,
                           placeholder: "no candidate — type the verified text",
                           style: "flex:1;min-width:260px" });
  return h("div", { class: "seg" },
    h("div", { text: seg.source_text }),
    h("div", { class: "row", style: "margin-top:6px" },
      mark(seg.candidate ? "draft" : "pending"), box,
      seg.jeles_score ? h("span", { class: "chip mono", text: "engine " + Number(seg.jeles_score).toFixed(2) }) : null),
    h("div", { class: "row", style: "margin-top:8px" },
      h("button", { class: "primary small", disabled: ro,
        onclick: () => sealSegment(seg, box.value) }, "Seal"),
      h("button", { class: "small danger", disabled: ro || !seg.candidate,
        onclick: () => rejectSegment(seg) }, "Reject"),
      h("span", { class: "chip mono", text: (seg.id || "").slice(0, 8) })));
}

async function sealSegment(seg, target) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  if (!target.trim()) return toast("Nothing to seal — type the verified text.", "err");
  const body = { segment_id: seg.id, verifier: verifier(), target: target.trim() };
  try {
    const out = await api("/api/queue/seal", body);
    toast(out.edited ? "Sealed your correction. It now serves as tier 1."
                     : "Sealed. It now serves as tier 1.", "ok");
    await refresh();
  } catch (e) {
    if (e.data && (e.data.code === "conflicting_seal" || e.data.code === "rejected_pair")) {
      if (confirm(e.message + "\n\nOverride and seal anyway?")) {
        await act("/api/queue/seal", { ...body, override: true }, "Sealed with an explicit override.");
      }
      return;
    }
    toast(e.message, "err");
  }
}

async function rejectSegment(seg) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const reason = await askFor("Why is this candidate wrong?", "reason (recorded in the ledger)");
  if (reason === null) return;
  await act("/api/queue/reject", { segment_id: seg.id, verifier: verifier(), reason },
            "Rejected. That candidate will not be offered for this text again.");
}

/* ---------- Memory (the curator) ------------------------------------------ */
function viewMemory() {
  const view = $("view");
  if (!S.state.capabilities.curation) {
    view.append(h("div", { class: "card" }, h("p", { class: "empty",
      text: "This store does not implement the curation capability (storage.supports_curation)." })));
    return;
  }
  const f = S.filters;
  const filters = h("div", { class: "card" },
    h("div", { class: "row" },
      h("input", { id: "f-contains", placeholder: "contains…", value: f.contains,
                   onkeydown: (e) => { if (e.key === "Enter") applyFilters(); } }),
      h("select", { id: "f-status" },
        ...[["", "any status"], ["sealed", "sealed"], ["draft", "draft"], ["rejected", "rejected"]]
          .map(([v, t]) => h("option", { value: v, selected: f.status === v }, t))),
      h("input", { id: "f-verifier", placeholder: "verifier", value: f.verifier, size: 12 }),
      h("label", { class: "row small", style: "gap:6px" },
        h("input", { type: "checkbox", id: "f-unverifiable", checked: f.unverifiable === "1" }),
        "unverifiable only"),
      h("button", { class: "primary small", onclick: applyFilters }, "Apply"),
      h("span", { class: "spacer" }),
      h("a", { href: "/api/export", download: "nestor-export.json" },
        h("button", { class: "small" }, "Export JSON"))));
  view.append(filters);

  const list = h("div", { class: "card" });
  if (!S.pairs.length) list.append(h("p", { class: "empty", text: "No pairs match." }));
  for (const p of S.pairs) list.append(pairRow(p));

  view.append(h("div", { class: "grid" }, list, h("div", {}, detailPanel(), sealForm())));
}

function pairRow(p) {
  return h("div", { class: "pair", onclick: () => openPair(p.id) },
    h("div", { class: "texts" },
      mark(p.status),
      h("span", { class: "src", text: p.source_text }),
      h("span", { class: "arrow", text: "→" }),
      h("span", { text: p.target_text })),
    h("div", { class: "row small muted", style: "margin-top:4px" },
      h("span", { class: "chip", text: p.status }),
      servableChip(p),
      p.verifier ? h("span", { class: "chip", text: "by " + p.verifier }) : h("span", { class: "chip", text: "no verifier" }),
      h("span", { class: "chip", text: (p.source_lang || "?") + "→" + (p.target_lang || "?") })));
}

async function openPair(id) {
  try { S.detail = (await api("/api/pair?id=" + encodeURIComponent(id))).pair; render(); }
  catch (e) { toast(e.message, "err"); }
}

function detailPanel() {
  const card = h("div", { class: "card" }, h("h2", { text: "Provenance" }));
  const p = S.detail;
  if (!p) { card.append(h("p", { class: "empty", text: "Select a pair to inspect it." })); return card; }
  const ro = S.state.read_only;
  card.append(
    h("div", { class: "row" }, mark(p.status), h("b", { text: p.source_text })),
    h("div", { style: "margin:2px 0 10px" }, h("span", { class: "muted", text: "→ " }), p.target_text),
    h("div", {},
      h("span", { class: "chip", text: p.status }),
      servableChip(p),
      // Only sealed rows carry a signature at all — reporting "signature
      // invalid" on a draft would read as an accusation about an ordinary row.
      p.status === "sealed"
        ? h("span", { class: "chip", text: p.signature_valid ? "signature valid" : "signature invalid" })
        : null,
      h("span", { class: "chip", text: "by " + (p.verifier || "—") }),
      h("span", { class: "chip", text: p.origin || "no origin" }),
      h("span", { class: "chip mono", text: p.created_at || "" }),
      h("span", { class: "chip mono", text: p.id.slice(0, 8) })),
    h("p", { class: "small muted", style: "margin:10px 0 4px",
             text: (p.rejection_count || 0) + " rejection(s) recorded against this pair" }));
  for (const r of p.rejections || []) {
    card.append(h("div", { class: "small", style: "border-top:1px solid var(--line);padding:6px 0" },
      h("div", { class: "mono", text: r.query_norm }),
      h("div", { class: "muted", text: (r.verifier || "—") + " · " + (r.reason || "no reason given") +
        (r.signature_valid ? "" : " · signature invalid") })));
  }
  card.append(h("div", { class: "row", style: "margin-top:12px" },
    h("button", { class: "small", disabled: ro || p.status !== "sealed",
      title: "return to draft for re-verification", onclick: () => unseal(p) }, "Unseal"),
    h("button", { class: "small danger", disabled: ro || p.status === "rejected",
      title: "the mapping is wrong — retire it everywhere", onclick: () => rejectPair(p) }, "Reject pair"),
    h("button", { class: "small", disabled: ro || p.status !== "rejected",
      title: "undo a rejection — returns to draft, not to sealed", onclick: () => restore(p) }, "Restore")));
  card.append(h("p", { class: "small muted", style: "margin-bottom:0",
    text: "Unsealing is not rejecting: unseal returns a pair to draft for re-verification, " +
          "rejecting retires it as wrong. Both are written to the ledger." }));
  return card;
}

async function unseal(p) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const reason = await askFor("Why unseal this?", "reason (recorded in the ledger)");
  if (reason === null) return;
  const out = await act("/api/unseal", { pair_id: p.id, verifier: verifier(), reason },
                        "Unsealed — back to draft for re-verification.");
  if (out) S.detail = out.pair;
  render();
}

async function rejectPair(p) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const reason = await askFor("Why is this mapping wrong?", "reason (recorded in the ledger)");
  if (reason === null) return;
  const out = await act("/api/reject-pair", { pair_id: p.id, verifier: verifier(), reason },
                        "Rejected — retired everywhere.");
  if (out) S.detail = out.pair;
  render();
}

async function restore(p) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const reason = await askFor("Why restore this?", "reason (recorded in the ledger)");
  if (reason === null) return;
  const out = await act("/api/restore", { pair_id: p.id, verifier: verifier(), reason },
                        "Restored to draft — it must be re-verified, not reinstated.");
  if (out) S.detail = out.pair;
  render();
}

function sealForm() {
  const d = S.state.domain;
  const card = h("div", { class: "card" },
    h("h2", { text: "Seal a pair by hand" }),
    h("input", { id: "seal-source", placeholder: "source text", style: "width:100%;margin-bottom:6px" }),
    h("input", { id: "seal-target", placeholder: "verified target text", style: "width:100%;margin-bottom:6px" }),
    h("div", { class: "row" },
      h("input", { id: "seal-sl", value: d.source_lang, size: 4, title: "source domain tag" }),
      h("span", { class: "muted", text: "→" }),
      h("input", { id: "seal-tl", value: d.target_lang, size: 4, title: "target domain tag" }),
      h("span", { class: "spacer" }),
      h("button", { class: "primary small", disabled: S.state.read_only, onclick: submitSeal }, "Seal")));
  return card;
}

async function submitSeal() {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const body = {
    source: $("seal-source").value, target: $("seal-target").value,
    source_lang: $("seal-sl").value, target_lang: $("seal-tl").value,
    verifier: verifier(),
  };
  try {
    await api("/api/seal", body);
    toast("Sealed.", "ok");
    await refresh();
  } catch (e) {
    if (e.data && (e.data.code === "conflicting_seal" || e.data.code === "rejected_pair")) {
      if (confirm(e.message + "\n\nOverride and seal anyway? This is recorded as a deliberate overrule.")) {
        await act("/api/seal", { ...body, override: true }, "Sealed with an explicit override.");
      }
      return;
    }
    toast(e.message, "err");
  }
}

/* ---------- Ask ----------------------------------------------------------- */
function viewAsk() {
  const d = S.state.domain;
  $("view").append(h("div", { class: "card" },
    h("h2", { text: "Ask Nestor" }),
    h("p", { class: "muted small", style: "margin-top:0",
      text: "Runs the cascade and shows which of the three states came back. Every ask is appended to the ledger, like any other serve." }),
    // The asked text stays in the box across the re-render: a reviewer reads the
    // answer against the question, and after sealing they usually ask it again.
    h("textarea", { id: "ask-text", placeholder: "text to look up…" },
      S.result ? S.result.query.text : ""),
    h("div", { class: "row", style: "margin-top:8px" },
      h("input", { id: "ask-sl", value: d.source_lang, size: 4 }),
      h("span", { class: "muted", text: "→" }),
      h("input", { id: "ask-tl", value: d.target_lang, size: 4 }),
      h("span", { class: "chip", text: "engine: " + S.state.engine }),
      h("span", { class: "spacer" }),
      h("button", { class: "primary", disabled: S.state.read_only, onclick: submitAsk }, "Ask"))));
  if (S.result) $("view").append(resultCard(S.result));
}

async function submitAsk() {
  const text = $("ask-text").value.trim();
  if (!text) return;
  const body = { text, source_lang: $("ask-sl").value, target_lang: $("ask-tl").value };
  try { S.result = { ...(await api("/api/ask", body)), query: body }; render(); }
  catch (e) { toast(e.message, "err"); }
}

function resultCard(r) {
  const p = r.passage;
  const explain = {
    sealed: "A human verified this. Served verbatim.",
    draft: "A machine produced it. Queued for review, never served as verified.",
    pending: "Nothing to offer. Said plainly rather than improvised.",
  }[p.state];
  const card = h("div", { class: "card" },
    h("div", { class: "row" }, mark(p.state),
      h("b", { class: p.state, text: p.state }),
      h("span", { class: "chip", text: "tier " + p.tier }),
      p.engine ? h("span", { class: "chip", text: p.engine }) : null,
      p.confidence ? h("span", { class: "chip mono", text: "confidence " + p.confidence }) : null,
      p.meta && p.meta.verifier ? h("span", { class: "chip", text: "verified by " + p.meta.verifier }) : null),
    h("p", { style: "font-size:17px;margin:10px 0 2px", text: p.target || "—" }),
    h("p", { class: "small muted", style: "margin-top:0", text: explain }));

  if (p.state !== "sealed") {
    card.append(h("div", { class: "row", style: "margin-top:10px" },
      h("input", { id: "ask-seal-target", value: p.target || "", placeholder: "verified target text",
                   style: "flex:1;min-width:220px" }),
      h("button", { class: "primary small", disabled: S.state.read_only, onclick: () => sealFromAsk(r) },
        "Seal this answer")));
  }

  const table = h("table", {}, h("tr", {},
    h("th", { text: "" }), h("th", { text: "similarity" }), h("th", { text: "pair" }), h("th", { text: "" })));
  for (const m of r.matches) {
    table.append(h("tr", {},
      h("td", {}, mark(m.status)),
      h("td", {}, sim(m.similarity)),
      h("td", {},
        h("div", { text: m.source_text + "  →  " + m.target_text }),
        h("div", { class: "small muted" },
          h("span", { class: "chip", text: m.status }),
          m.status === "sealed" && !m.servable ? h("span", { class: "badge bad", text: "not servable" }) : null,
          m.verifier ? h("span", { class: "chip", text: "by " + m.verifier }) : null)),
      h("td", {}, h("button", { class: "small danger", disabled: S.state.read_only,
        title: "wrong answer for THIS query — the pair stays valid for its own source",
        onclick: () => rejectMatch(r, m) }, "Wrong for this"))));
  }
  card.append(h("p", { class: "small muted", style: "margin:14px 0 4px",
    text: "Ranked candidates. A sealed one serves only at or above " + r.threshold + "." }), table);
  return card;
}

async function sealFromAsk(r) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const target = $("ask-seal-target").value.trim();
  if (!target) return toast("Nothing to seal — type the verified text.", "err");
  const body = { source: r.query.text, target, source_lang: r.query.source_lang,
                 target_lang: r.query.target_lang, verifier: verifier(), origin: "ui:ask" };
  try {
    await api("/api/seal", body);
    toast("Sealed. Ask again and it serves as tier 1.", "ok");
    await refresh();
  } catch (e) {
    if (e.data && (e.data.code === "conflicting_seal" || e.data.code === "rejected_pair")) {
      if (confirm(e.message + "\n\nOverride and seal anyway?")) {
        await act("/api/seal", { ...body, override: true }, "Sealed with an explicit override.");
      }
      return;
    }
    toast(e.message, "err");
  }
}

async function rejectMatch(r, m) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const reason = await askFor("Why is this the wrong answer for this query?", "reason");
  if (reason === null) return;
  await act("/api/reject-match", {
    source: r.query.text, source_lang: r.query.source_lang, target_lang: r.query.target_lang,
    pair_id: m.id, target_text: m.target_text, verifier: verifier(), reason,
  }, "Suppressed for this query. The pair still serves its own source text.");
}

/* ---------- Ledger -------------------------------------------------------- */
function viewLedger() {
  const l = S.ledger || { entries: [], kinds: [], ok: true, detail: "" };
  $("view").append(h("div", { class: "card" },
    h("div", { class: "row" },
      h("span", { class: "badge " + (l.ok ? "good" : "bad"), text: l.ok ? "chain intact" : "chain broken" }),
      h("span", { class: "muted small", text: l.detail }),
      h("span", { class: "spacer" }),
      h("select", { onchange: (e) => { S.ledgerKind = e.target.value; refresh(); } },
        ...[["", "every kind"]].concat(l.kinds.map((k) => [k, k]))
          .map(([v, t]) => h("option", { value: v, selected: (S.ledgerKind || "") === v }, t))),
      h("span", { class: "chip mono", text: S.state.ledger.path }))));

  const card = h("div", { class: "card" });
  if (!l.entries.length) card.append(h("p", { class: "empty", text: "Nothing recorded yet." }));
  const table = h("table", {}, h("tr", {}, h("th", { text: "when" }), h("th", { text: "kind" }), h("th", { text: "detail" })));
  for (const e of l.entries) {
    const chips = h("td", {});
    for (const [k, v] of Object.entries(e)) {
      if (["ts", "kind", "prev"].includes(k)) continue;
      if (v === "" || v === null || v === undefined) continue;
      chips.append(h("span", { class: "chip mono", text: k + "=" + String(v).slice(0, 42) }));
    }
    table.append(h("tr", {},
      h("td", { class: "mono small", text: (e.ts || "").replace("T", " ").slice(0, 19) }),
      h("td", {}, h("b", { text: e.kind || "?" })),
      chips));
  }
  if (l.entries.length) card.append(table);
  $("view").append(card);
}

/* ---------- shell --------------------------------------------------------- */
function badges() {
  const s = S.state, box = $("badges");
  box.replaceChildren();
  const c = s.summary || {};
  box.append(h("span", { class: "badge good", text: (c.sealed ?? s.stats.sealed ?? 0) + " sealed" }));
  box.append(h("span", { class: "badge", text: (c.draft ?? s.stats.draft ?? 0) + " draft" }));
  if (c.rejected) box.append(h("span", { class: "badge", text: c.rejected + " rejected" }));
  if (c.sealed_unverifiable) {
    box.append(h("span", { class: "badge bad", title: "sealed rows Nestor would refuse to serve",
                           text: c.sealed_unverifiable + " unverifiable" }));
  }
  box.append(h("span", { class: s.signing_enabled ? "badge good" : "badge warn",
    title: s.signing_enabled ? "seals are bound to a key the store does not hold"
                             : "NESTOR_SEAL_KEY is not set: any row claiming 'sealed' is trusted",
    text: s.signing_enabled ? "signed seals" : "unsigned seals" }));
  box.append(h("span", { class: S.state.ledger.ok ? "badge good" : "badge bad",
    text: S.state.ledger.ok ? "ledger ok" : "ledger broken" }));
  if (s.read_only) box.append(h("span", { class: "badge warn", text: "read-only" }));
}

function tabs() {
  const nav = $("tabs");
  nav.replaceChildren();
  for (const [id, label] of TABS) {
    nav.append(h("button", { class: S.tab === id ? "on" : "", onclick: () => { S.tab = id; refresh(); } }, label));
  }
}

function applyFilters() {
  S.filters = {
    contains: $("f-contains").value.trim(), status: $("f-status").value,
    verifier: $("f-verifier").value.trim(), unverifiable: $("f-unverifiable").checked ? "1" : "",
  };
  refresh();
}

function render() {
  tabs(); badges();
  const view = $("view");
  view.replaceChildren();
  if (S.tab === "queue") viewQueue();
  else if (S.tab === "memory") viewMemory();
  else if (S.tab === "ask") viewAsk();
  else viewLedger();
}

async function refresh() {
  try {
    S.state = await api("/api/state");
    if (S.tab === "queue" && S.state.capabilities.queue) S.queue = await api("/api/queue");
    if (S.tab === "memory" && S.state.capabilities.curation) {
      const q = new URLSearchParams(S.filters);
      S.pairs = (await api("/api/pairs?" + q.toString())).pairs;
    }
    if (S.tab === "ledger") {
      S.ledger = await api("/api/ledger?limit=200&kind=" + encodeURIComponent(S.ledgerKind || ""));
    }
    render();
  } catch (e) {
    toast(e.message, "err");
  }
}

$("verifier").value = localStorage.getItem("nestor.verifier") || "";
$("verifier").addEventListener("change", () => localStorage.setItem("nestor.verifier", verifier()));
api("/api/state").then((s) => {
  if (!$("verifier").value && s.verifier_hint) $("verifier").value = s.verifier_hint;
  refresh();
});
</script>
</body>
</html>
"""
