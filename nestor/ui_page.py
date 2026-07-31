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
  <div class="who" id="who">
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
  ["queue",   "Queue"],
  ["memory",  "Memory"],
  ["ask",     "Ask"],
  ["signals", "Signals"],
  ["ledger",  "Ledger"],
];

// How many pairs the Memory list shows at once. One more than this is asked
// for, so "is there a next page" is answered by the server's own result
// instead of by a count query the Storage Protocol does not have.
const PAGE = 50;

// The recipes: one mechanic — normalize, match against sealed pairs, serve
// above the threshold or don't — with a different matcher and a different
// meaning for "source → target". Translation is one instance, not the product.
const RECIPES = [
  ["translate", "Translate", "phrase → verified translation, through the three-tier cascade"],
  ["entity",    "Entity",    "alias/surface → canonical entity, over a sealed alias graph"],
  ["numeric",   "Numeric",   "figure → sealed baseline, with tolerance and variation"],
  ["match",     "Match",     "the bare seam: any domain, either shipped matcher"],
];

const S = { tab: "queue", state: null, pairs: [], detail: null, queue: null,
            ledger: null, result: null, domains: [], signals: null,
            offset: 0, more: false, session: null, typedVerifier: "",
            recipe: localStorage.getItem("nestor.recipe") || "translate",
            filters: { status: "", contains: "", verifier: "", unverifiable: "",
                       source_lang: "", target_lang: "" } };

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

function verifier() {
  const box = $("verifier");
  return box ? box.value.trim() : (S.session ? S.session.verifier : "");
}

/* ---------- identity -------------------------------------------------------
 *
 * Without a keyring the "acting as" box is a text field, and the honest
 * description of that is: this UI seals as whatever you type. With one, the
 * same corner becomes a sign-in — a verifier presents their own seal key, and
 * every decision in the session is signed with it, so the name on a seal is
 * evidence about a person rather than evidence that somebody typed it.
 *
 * The token is kept here and sent with every write; the key is not kept at all.
 */
function whoBox() {
  const box = $("who");
  box.replaceChildren();
  const id = (S.state && S.state.identity) || { required: false };
  if (!id.required) {
    box.append(h("label", { for: "verifier", text: "acting as" }),
      h("input", { id: "verifier", placeholder: "your name", size: 14, autocomplete: "off",
                   value: S.typedVerifier || "",
                   onchange: (e) => { S.typedVerifier = e.target.value.trim();
                                      localStorage.setItem("nestor.verifier", S.typedVerifier); } }));
    return;
  }
  if (S.session && S.session.verifier) {
    box.append(h("label", { text: "signed in as" }),
      h("b", { text: S.session.verifier }),
      h("button", { class: "small", onclick: signOut }, "Sign out"));
    return;
  }
  const names = id.verifiers || [];
  box.append(h("label", { text: "sign in" }),
    names.length
      ? h("select", { id: "who-name" }, ...names.map((n) => h("option", { value: n }, n)))
      : h("input", { id: "who-name", placeholder: "verifier", size: 10 }),
    h("input", { id: "who-key", type: "password", placeholder: "seal key", size: 16,
                 autocomplete: "off",
                 onkeydown: (e) => { if (e.key === "Enter") signIn(); } }),
    h("button", { class: "primary small", onclick: signIn }, "Sign in"));
}

async function signIn() {
  const name = $("who-name").value.trim(), key = $("who-key").value.trim();
  try {
    const out = await api("/api/session", { verifier: name, key });
    S.session = { token: out.token, verifier: out.verifier };
    localStorage.setItem("nestor.session", out.token);
    toast("signed in as " + out.verifier);
    refresh();
  } catch (e) { toast(e.message, "err"); }
}

async function signOut() {
  const token = S.session ? S.session.token : "";
  S.session = null;
  localStorage.removeItem("nestor.session");
  try { await api("/api/session/end", { session: token }); } catch (e) { /* already gone */ }
  refresh();
}

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
    // Every write carries the session, in one place rather than at each call
    // site — a decision that forgot it would be refused, which is the right
    // failure, but a page that has to remember is a page that will not.
    if (S.session && S.session.token && body.session === undefined) {
      body = { ...body, session: S.session.token };
    }
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ error: res.statusText }));
  if (res.status === 401 && data.code === "session_required" && S.session) {
    S.session = null;                    // the shift ended, or the UI restarted
    localStorage.removeItem("nestor.session");
    refresh();
  }
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
      // Domains are the store's generic tag pairs — languages for translation,
      // an entity type for a graph, label/domain for a numeric bucket. One store
      // holds several disjoint graphs, so browsing has to be able to say which.
      h("select", { id: "f-domain", title: "domain (source → target tags)" },
        h("option", { value: "", selected: !f.source_lang && !f.target_lang }, "every domain"),
        // The value is the index into S.domains, not the tags joined by a
        // separator: a domain tag is arbitrary text and may contain anything.
        ...S.domains.map((d, i) => h("option", {
          value: String(i),
          selected: f.source_lang === d.source_lang && f.target_lang === d.target_lang,
        }, domainLabel(d)))),
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
  if (S.pairs.length || S.offset) list.append(pager());

  view.append(h("div", { class: "grid" }, list,
                h("div", {}, detailPanel(), sealForm(), portableCard())));
}

// The list stopped at 50 rows with nothing to say it had. A curator whose
// memory is larger than one page was looking at an arbitrary slice of it and
// had no way to know — "no pairs match" and "no more pairs on this page" read
// identically when the page is the only thing you can see.
function pager() {
  const first = S.offset + 1, last = S.offset + S.pairs.length;
  return h("div", { class: "row small muted", style: "border-top:1px solid var(--line);padding-top:10px;margin-top:4px" },
    h("button", { class: "small", disabled: S.offset === 0,
                  onclick: () => { S.offset = Math.max(0, S.offset - PAGE); refresh(); } }, "‹ Previous"),
    h("button", { class: "small", disabled: !S.more,
                  onclick: () => { S.offset += PAGE; refresh(); } }, "Next ›"),
    h("span", { text: S.pairs.length ? `showing ${first}–${last}${S.more ? "" : " (end)"}`
                                     : "past the end" }));
}

// Whose key signed a seal, when that is a question with more than one answer.
// "Valid" covers a seal signed by rita's key and one signed by the old
// deployment-wide key alike, and those are different facts about who verified
// something — which is the whole reason per-verifier keys exist.
function keyChip(p) {
  if (!p.key_status) return null;                      // no keyring: nothing to say
  const bad = "color:var(--rejected);border-color:var(--rejected)";
  if (p.key_status === "compromised") {
    return h("span", { class: "chip", style: bad, title:
      "this key was reported stolen: nothing it signed can be told apart from the "
      + "thief's, so none of it is served", text: "key compromised" });
  }
  if (p.key_status === "unknown" && p.status === "sealed") {
    return h("span", { class: "chip", style: bad, title:
      "the keyring has no key for this verifier", text: "unknown verifier" });
  }
  if (p.signed_by === "legacy") {
    return h("span", { class: "chip", title:
      "signed by the deployment-wide key from before the keyring — verified by "
      + "somebody here, not attributable to a person", text: "legacy key" });
  }
  if (p.key_status === "revoked") {
    return h("span", { class: "chip", title:
      "key retired; the seals it already made stand", text: "key retired" });
  }
  return null;
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
      keyChip(p),
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

function domainLabel(d) {
  return (d.source_lang === d.target_lang ? d.source_lang
                                          : d.source_lang + " → " + d.target_lang)
       + (d.count ? "  (" + d.count + ")" : "");
}

function sealDomains() {
  // Every domain the store actually holds, plus this session's default if it is
  // not among them — so a first seal into an empty instance still has somewhere
  // to go, and every later one can pick any graph rather than the language pair
  // the process happened to start with.
  const list = S.domains.map((d) => ({ ...d }));
  const d = S.state.domain;
  if (!list.some((x) => x.source_lang === d.source_lang && x.target_lang === d.target_lang)) {
    list.unshift({ source_lang: d.source_lang, target_lang: d.target_lang, count: 0 });
  }
  return list;
}

function sealSelection(list) {
  // An explicit pick wins; otherwise follow the domain being browsed, so sealing
  // while filtered to an entity graph does not file the pair under en→es.
  if (S.sealDomain === "new") return "new";
  if (S.sealDomain !== undefined && S.sealDomain !== "" && list[Number(S.sealDomain)]) {
    return Number(S.sealDomain);
  }
  const f = S.filters;
  const match = (a) => list.findIndex(
    (d) => d.source_lang === a.source_lang && d.target_lang === a.target_lang);
  if (f.source_lang || f.target_lang) {
    const i = match(f);
    if (i >= 0) return i;
  }
  const i = match(S.state.domain);
  return i >= 0 ? i : 0;
}

function sealForm() {
  const list = sealDomains();
  const picked = sealSelection(list);
  const custom = picked === "new";
  const card = h("div", { class: "card" },
    h("h2", { text: "Seal a pair by hand" }),
    // Wording stays domain-neutral: this card seals a phrase, an alias or any
    // other pair, and calling the halves "source text" and "translation" was the
    // form telling the user it only did one recipe.
    h("input", { id: "seal-source", placeholder: "source — the phrase, alias or value asked",
                 style: "width:100%;margin-bottom:6px" }),
    h("input", { id: "seal-target", placeholder: "verified target — the answer you stand behind",
                 style: "width:100%;margin-bottom:6px" }),
    h("div", { class: "row" },
      h("select", { id: "seal-domain", title: "which graph this pair belongs to",
                    onchange: (e) => { S.sealDomain = e.target.value; render(); } },
        ...list.map((d, i) => h("option", { value: String(i), selected: picked === i },
                                domainLabel(d))),
        h("option", { value: "new", selected: custom }, "new domain…")),
      custom ? h("input", { id: "seal-sl", placeholder: "source tag", size: 8,
                            title: "source domain tag" }) : null,
      custom ? h("span", { class: "muted", text: "→" }) : null,
      custom ? h("input", { id: "seal-tl", placeholder: "target tag", size: 8,
                            title: "target domain tag" }) : null,
      h("span", { class: "spacer" }),
      h("button", { class: "primary small", disabled: S.state.read_only, onclick: submitSeal }, "Seal")),
    h("p", { class: "small muted", style: "margin:10px 0 0" },
      "Tags are generic: languages for a translation, the entity type for a graph, " +
      "label → domain for a figure. Scored with the string matcher — to seal a " +
      "numeric baseline, use ",
      h("b", { text: "Ask → Numeric" }), ", which keeps a label to one baseline."));
  return card;
}

function sealTags() {
  const list = sealDomains();
  const picked = sealSelection(list);
  if (picked === "new") {
    return { source_lang: $("seal-sl").value.trim(), target_lang: $("seal-tl").value.trim() };
  }
  const d = list[picked];
  return { source_lang: d.source_lang, target_lang: d.target_lang };
}

async function submitSeal() {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const tags = sealTags();
  if (!tags.source_lang || !tags.target_lang) {
    return toast("A new domain needs both tags — they are what keeps one graph out " +
                 "of another.", "err");
  }
  const body = {
    source: $("seal-source").value, target: $("seal-target").value,
    ...tags, verifier: verifier(),
  };
  await sealWithOverride("/api/seal", body, "Sealed into " + domainLabel(tags) + ".");
  // The new domain exists now, so select it instead of leaving the form on
  // "new domain…" with the tag boxes empty — the next seal would be refused.
  const i = sealDomains().findIndex((d) => d.source_lang === tags.source_lang
                                        && d.target_lang === tags.target_lang);
  if (i >= 0 && S.sealDomain === "new") { S.sealDomain = String(i); render(); }
}

function portableCard() {
  const card = h("div", { class: "card" },
    h("h2", { text: "Take it elsewhere" }),
    h("div", { class: "row" },
      h("a", { href: "/api/bundle", download: "nestor-bundle.json" },
        h("button", { class: "small" }, "Export bundle")),
      h("a", { href: "/api/export", download: "nestor-export.json" },
        h("button", { class: "small" }, "Curator JSON")),
      h("span", { class: "spacer" }),
      h("label", { class: "small muted" }, "Import ",
        h("input", { type: "file", accept: ".json,application/json", id: "import-file",
                     disabled: S.state.read_only, style: "max-width:150px",
                     onchange: (e) => readBundle(e.target.files[0]) }))),
    h("p", { class: "small muted", style: "margin:10px 0 0",
      text: "A bundle carries the pairs, the rejections and the signatures. Importing " +
            "reports first and writes nothing until you confirm — and a seal whose " +
            "signature does not verify here lands as a draft for review, never as sealed." }));
  if (S.importReport) card.append(importReport(S.importReport));
  return card;
}

function readBundle(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      S.importBundle = JSON.parse(reader.result);
    } catch (e) {
      return toast("That file is not JSON: " + e.message, "err");
    }
    try {
      S.importReport = await api("/api/import", { bundle: S.importBundle, dry_run: true });
      render();
    } catch (e) { toast(e.message, "err"); }
  };
  reader.readAsText(file);
}

function importReport(r) {
  const box = h("div", { style: "margin-top:12px;border-top:1px solid var(--line);padding-top:10px" },
    h("div", { class: "row" },
      h("span", { class: "chip", text: r.sealed + " would land sealed" }),
      r.demoted ? h("span", { class: "badge warn", title: "signature does not verify here",
                              text: r.demoted + " demoted to draft" }) : null,
      r.drafts ? h("span", { class: "chip", text: r.drafts + " draft" }) : null,
      r.existing ? h("span", { class: "chip", text: r.existing + " already here" }) : null,
      r.conflicts.length ? h("span", { class: "badge bad", text: r.conflicts.length + " conflict(s)" }) : null,
      r.rejections ? h("span", { class: "chip", text: r.rejections + " rejection(s)" }) : null));
  for (const c of r.conflicts) {
    box.append(h("div", { class: "small", style: "margin-top:6px" },
      h("div", { text: c.source_text }),
      h("div", { class: "muted", text: "here: " + c.here.target_text + " (" + (c.here.verifier || "—") +
                                       ")  ·  incoming: " + c.incoming.target_text +
                                       " (" + (c.incoming.verifier || "—") + ")" })));
  }
  box.append(h("div", { class: "row", style: "margin-top:10px" },
    h("button", { class: "primary small", disabled: S.state.read_only, onclick: applyImport },
      "Write these to the memory"),
    h("button", { class: "small", onclick: () => { S.importReport = null; S.importBundle = null; render(); } },
      "Discard"),
    r.conflicts.length
      ? h("label", { class: "row small muted", style: "gap:6px" },
          h("input", { type: "checkbox", id: "import-override" }), "take the incoming answer where we disagree")
      : null));
  return box;
}

async function applyImport() {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const override = $("import-override") ? $("import-override").checked : false;
  const out = await act("/api/import",
    { bundle: S.importBundle, dry_run: false, verifier: verifier(), override_conflicts: override },
    "Imported.");
  if (out) {
    S.importReport = null; S.importBundle = null;
    if (out.demoted) {
      toast(out.demoted + " pair(s) claimed sealed but do not verify here — they are " +
            "drafts in the queue now.", "err");
    }
  }
  render();
}

/* ---------- Ask: one mechanic, four recipes -------------------------------- */
function viewAsk() {
  const view = $("view");
  const picker = h("div", { class: "card" },
    h("h2", { text: "Ask Nestor" }),
    h("div", { class: "row", style: "margin-bottom:6px" },
      ...RECIPES.map(([id, label]) =>
        h("button", { class: S.recipe === id ? "primary small" : "small",
          onclick: () => { S.recipe = id; localStorage.setItem("nestor.recipe", id);
                           S.result = null; render(); } }, label))),
    h("p", { class: "muted small", style: "margin:0",
      text: RECIPES.find((r) => r[0] === S.recipe)[2] +
            " — same seal, same threshold, same ledger." }));
  view.append(picker);
  view.append({ translate: translateForm, entity: entityForm,
                numeric: numericForm, match: matchForm }[S.recipe]());
  if (S.result && S.result.recipe === S.recipe) {
    view.append({ translate: translateResult, entity: entityResult,
                  numeric: numericResult, match: matchResult }[S.recipe](S.result));
  }
}

function remembered(key, fallback) { return localStorage.getItem("nestor." + key) || fallback; }
function remember(key, value) { localStorage.setItem("nestor." + key, value); return value; }
function asked() { return S.result && S.result.recipe === S.recipe ? S.result.query : {}; }

function domainList(id) {
  // The tag pairs actually in the store, offered as completions. Which recipe
  // a domain belongs to is the human's call — nothing here guesses.
  return h("datalist", { id },
    ...S.domains.map((d) => h("option", { value: d.source_lang === d.target_lang
      ? d.source_lang : d.source_lang + " → " + d.target_lang })));
}

/* --- translate: the three-tier cascade ------------------------------------ */
function translateForm() {
  const d = S.state.domain, q = asked();
  return h("div", { class: "card" },
    // The asked text stays in the box across the re-render: a reviewer reads the
    // answer against the question, and after sealing they usually ask it again.
    h("textarea", { id: "ask-text", placeholder: "text to look up…" }, q.text || ""),
    h("div", { class: "row", style: "margin-top:8px" },
      h("input", { id: "ask-sl", value: q.source_lang || d.source_lang, size: 4 }),
      h("span", { class: "muted", text: "→" }),
      h("input", { id: "ask-tl", value: q.target_lang || d.target_lang, size: 4 }),
      h("span", { class: "chip", text: "engine: " + S.state.engine }),
      h("span", { class: "spacer" }),
      h("button", { class: "primary", disabled: S.state.read_only, onclick: submitAsk }, "Ask")));
}

async function submitAsk() {
  const text = $("ask-text").value.trim();
  if (!text) return;
  const body = { text, source_lang: $("ask-sl").value, target_lang: $("ask-tl").value };
  try { S.result = { recipe: "translate", ...(await api("/api/ask", body)), query: body }; render(); }
  catch (e) { toast(e.message, "err"); }
}

/* --- entity: alias → canonical -------------------------------------------- */
function entityForm() {
  const q = asked();
  return h("div", { class: "card" },
    h("div", { class: "row" },
      h("input", { id: "ent-surface", placeholder: "surface form, e.g. AMZN",
                   value: q.surface || "", style: "flex:1;min-width:220px",
                   onkeydown: (e) => { if (e.key === "Enter") submitEntity(); } }),
      h("input", { id: "ent-domain", list: "nestor-domains", size: 10, title: "entity domain tag",
                   value: q.domain || remembered("entityDomain", "entity") }),
      h("button", { class: "primary", disabled: S.state.read_only, onclick: submitEntity }, "Resolve")),
    domainList("nestor-domains"));
}

async function submitEntity() {
  const surface = $("ent-surface").value.trim();
  if (!surface) return;
  const body = { surface, domain: remember("entityDomain", $("ent-domain").value.trim() || "entity") };
  try { S.result = { recipe: "entity", ...(await api("/api/entity/resolve", body)), query: body }; render(); }
  catch (e) { toast(e.message, "err"); }
}

function entityResult(r) {
  const state = r.sealed ? "sealed" : (r.provenance && r.provenance.suggestion ? "draft" : "pending");
  const explain = {
    sealed: "A human verified that this alias denotes this entity.",
    draft: "Nothing verified matched closely enough. This is a suggestion to seal, not an answer.",
    pending: "No alias in this graph comes close. Said plainly rather than guessed.",
  }[state];
  const prov = r.provenance || {};
  const card = h("div", { class: "card" },
    h("div", { class: "row" }, mark(state), h("b", { class: state, text: state }),
      h("span", { class: "chip", text: "domain " + r.domain }),
      r.confidence ? h("span", { class: "chip mono", text: "confidence " + r.confidence }) : null,
      prov.verifier ? h("span", { class: "chip", text: "verified by " + prov.verifier }) : null,
      prov.sealed_surface ? h("span", { class: "chip", text: "via “" + prov.sealed_surface + "”" }) : null),
    h("p", { style: "font-size:17px;margin:10px 0 2px",
             text: r.canonical || prov.suggestion || "—" }),
    h("p", { class: "small muted", style: "margin-top:0", text: explain }));

  if (!r.sealed) {
    card.append(h("div", { class: "row", style: "margin-top:10px" },
      h("span", { class: "muted small", text: r.query.surface + "  →" }),
      h("input", { id: "ent-canonical", value: prov.suggestion || "",
                   placeholder: "canonical entity", style: "flex:1;min-width:200px" }),
      h("button", { class: "primary small", disabled: S.state.read_only,
        onclick: () => sealAlias(r) }, "Seal alias")));
  }
  card.append(candidates(r.candidates, r.threshold, "alias", "entity",
    (m) => rejectMatch({ source: r.query.surface, source_lang: r.domain,
                         target_lang: r.domain }, m)));
  return card;
}

async function sealAlias(r) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const canonical = $("ent-canonical").value.trim();
  if (!canonical) return toast("Nothing to seal — type the canonical entity.", "err");
  const body = { surface: r.query.surface, canonical, domain: r.domain,
                 verifier: verifier(), origin: "ui:entity" };
  await sealWithOverride("/api/entity/seal", body,
    "Sealed. That alias now resolves to " + canonical + ".");
}

/* --- numeric: figure vs sealed baseline ----------------------------------- */
function numericForm() {
  const q = asked();
  return h("div", { class: "card" },
    h("div", { class: "row" },
      h("input", { id: "num-label", placeholder: "label, e.g. ceiling", size: 14,
                   value: q.label || remembered("numLabel", "") }),
      h("input", { id: "num-observed", placeholder: "observed figure, e.g. $1,030,000",
                   value: q.observed || "", style: "flex:1;min-width:180px",
                   onkeydown: (e) => { if (e.key === "Enter") submitNumeric(); } }),
      h("input", { id: "num-domain", list: "nestor-domains", size: 9, title: "domain tag",
                   value: q.domain || remembered("numDomain", "value") }),
      h("button", { class: "primary", disabled: S.state.read_only, onclick: submitNumeric }, "Check")),
    h("div", { class: "row small muted", style: "margin-top:8px" },
      "tolerance", h("input", { id: "num-abs", size: 6, title: "absolute tolerance",
                                value: q.abs_tol !== undefined ? q.abs_tol : remembered("numAbs", "0") }),
      "absolute, or", h("input", { id: "num-pct", size: 6, title: "proportional tolerance, as a fraction",
                                   value: q.pct_tol !== undefined ? q.pct_tol : remembered("numPct", "0.05") }),
      "proportional — whichever is wider"),
    domainList("nestor-domains"));
}

function numericBody() {
  return {
    label: remember("numLabel", $("num-label").value.trim()),
    observed: $("num-observed").value.trim(),
    domain: remember("numDomain", $("num-domain").value.trim() || "value"),
    abs_tol: remember("numAbs", $("num-abs").value.trim() || "0"),
    pct_tol: remember("numPct", $("num-pct").value.trim() || "0.05"),
  };
}

async function submitNumeric() {
  const body = numericBody();
  if (!body.label || !body.observed) return toast("A check needs a label and a figure.", "err");
  try { S.result = { recipe: "numeric", ...(await api("/api/reconcile/check", body)), query: body }; render(); }
  catch (e) { toast(e.message, "err"); }
}

function partialParse(r) {
  const bad = [];
  if (r.observed_partial) bad.push(["observed", r.observed_text, r.observed]);
  if (r.baseline_partial) bad.push(["baseline", r.baseline_text, r.baseline]);
  if (!bad.length) return null;
  const box = h("div", { class: "banner small",
                         style: "border-left:3px solid var(--draft);padding-left:10px;margin:10px 0" });
  for (const [which, text, value] of bad) {
    box.append(h("p", { style: "margin:2px 0" },
      h("b", { text: "the " + which + " figure is not what was typed: " }),
      h("span", { class: "mono", text: String(text) }),
      " was read as ",
      h("span", { class: "mono", text: String(value) }),
      " — digits were left outside the number."));
  }
  return box;
}

function numericResult(r) {
  const state = r.baseline === null ? "pending" : (r.within_tolerance ? "sealed" : "rejected");
  const label = { pending: "no baseline", sealed: "within tolerance", rejected: "flagged" }[state];
  const explain = {
    pending: "No verified baseline for this label. Nothing to check against — seal one below.",
    sealed: "Inside the tolerance band around a human-verified baseline.",
    rejected: "Outside the tolerance band. The variation is reported, not smoothed.",
  }[state];
  const pct = (x) => x === null || x === undefined ? "—" : (x * 100).toFixed(2) + "%";
  const num = (x) => x === null || x === undefined ? "—" : x.toLocaleString();
  const card = h("div", { class: "card" },
    h("div", { class: "row" }, mark(state), h("b", { class: state, text: label }),
      h("span", { class: "chip", text: r.label + " · " + r.domain }),
      r.ambiguous ? h("span", { class: "badge bad", title: "more than one sealed baseline stands for this label",
                                text: r.baseline_count + " baselines — ambiguous" }) : null),
    h("table", {},
      h("tr", {}, h("th", { text: "baseline" }), h("th", { text: "observed" }),
        h("th", { text: "variation" }), h("th", { text: "as %" }), h("th", { text: "tolerance" })),
      h("tr", {},
        h("td", { class: "mono", text: num(r.baseline) }),
        h("td", { class: "mono", text: num(r.observed) }),
        h("td", { class: "mono", text: num(r.variation) }),
        h("td", { class: "mono", text: pct(r.variation_pct) }),
        h("td", { class: "mono small muted",
                  text: "±" + num(r.tolerance.abs_tol) + " or " + pct(r.tolerance.pct_tol) }))),
    // The matcher SEARCHES for a number rather than requiring one, so
    // "1,00o,000" — one typo — is compared as 100. The failure direction is
    // safe, but "the number I compared was not the number you typed" is a bad
    // sentence in an audit and a worse one to discover later.
    partialParse(r),
    h("p", { class: "small muted", text: explain }),
    h("div", { class: "row" },
      h("input", { id: "num-baseline", placeholder: "verified baseline for " + r.label,
                   value: r.baseline === null ? r.query.observed : "",
                   style: "flex:1;min-width:200px" }),
      h("button", { class: "primary small", disabled: S.state.read_only,
        onclick: () => sealBaseline(r) }, "Seal baseline")));
  if (r.baselines && r.baselines.length) {
    card.append(h("p", { class: "small muted", style: "margin:12px 0 2px",
      text: "Standing baseline(s) for this label — a label should have exactly one:" }));
    for (const b of r.baselines) {
      card.append(h("div", { class: "small" },
        h("span", { class: "mono", text: b.value }),
        h("span", { class: "chip", text: "by " + (b.verifier || "—") }),
        h("span", { class: "chip mono", text: (b.created_at || "").slice(0, 19).replace("T", " ") })));
    }
  }
  return card;
}

async function sealBaseline(r) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const value = $("num-baseline").value.trim();
  if (!value) return toast("Nothing to seal — type the verified figure.", "err");
  await sealWithOverride("/api/reconcile/seal",
    { ...r.query, value, verifier: verifier(), origin: "ui:numeric" },
    "Baseline sealed for " + r.label + ".");
}

/* --- match: the bare seam ------------------------------------------------- */
function matchForm() {
  const d = S.state.domain, q = asked();
  return h("div", { class: "card" },
    h("div", { class: "row" },
      h("input", { id: "m-text", placeholder: "value to normalize and score…",
                   value: q.text || "", style: "flex:1;min-width:220px",
                   onkeydown: (e) => { if (e.key === "Enter") submitMatch(); } }),
      h("input", { id: "m-sl", value: q.source_lang || d.source_lang, size: 6, title: "source domain tag" }),
      h("span", { class: "muted", text: "→" }),
      h("input", { id: "m-tl", value: q.target_lang || d.target_lang, size: 6, title: "target domain tag" }),
      h("select", { id: "m-matcher" },
        ...[["string", "StringMatcher"], ["numeric", "NumericMatcher"]].map(([v, t]) =>
          h("option", { value: v, selected: (q.matcher || "string") === v }, t))),
      h("button", { class: "primary", disabled: S.state.read_only, onclick: submitMatch }, "Look up")),
    h("p", { class: "small muted", style: "margin:8px 0 0" },
      "No engine, no queue, no recipe — normalize, score against the sealed pairs in this domain, ",
      "and answer the only question Nestor answers: would this be served as verified?"));
}

async function submitMatch() {
  const text = $("m-text").value.trim();
  if (!text) return;
  const body = { text, source_lang: $("m-sl").value.trim(), target_lang: $("m-tl").value.trim(),
                 matcher: $("m-matcher").value };
  try { S.result = { recipe: "match", ...(await api("/api/match", body)), query: body }; render(); }
  catch (e) { toast(e.message, "err"); }
}

function matchResult(r) {
  const state = r.served ? "sealed" : (r.matches.length ? "draft" : "pending");
  const card = h("div", { class: "card" },
    h("div", { class: "row" }, mark(state),
      h("b", { class: state, text: r.served ? "would be served" : "would not be served" }),
      h("span", { class: "chip", text: r.matcher }),
      h("span", { class: "chip mono", title: "the key the matcher reduced this to",
                  text: "normalized: " + r.normalized }),
      r.confidence ? h("span", { class: "chip mono", text: "confidence " + r.confidence }) : null),
    r.served ? h("p", { style: "font-size:17px;margin:10px 0 2px", text: r.target }) : null,
    r.served && r.verifier ? h("p", { class: "small muted", style: "margin-top:0",
                                      text: "verified by " + r.verifier }) : null);
  card.append(candidates(r.matches, r.threshold, "source", "target",
    (m) => rejectMatch(r.query, m)));
  return card;
}

/* --- shared: candidates, sealing, rejecting ------------------------------- */
function candidates(rows, threshold, leftLabel, rightLabel, onReject) {
  const box = h("div", {}, h("p", { class: "small muted", style: "margin:14px 0 4px",
    text: rows.length ? "Ranked candidates. A sealed one serves only at or above " + threshold + "."
                      : "No candidate scored high enough to be worth showing." }));
  if (!rows.length) return box;
  const table = h("table", {}, h("tr", {}, h("th", { text: "" }), h("th", { text: "similarity" }),
    h("th", { text: leftLabel + " → " + rightLabel }), h("th", { text: "" })));
  for (const m of rows) {
    const left = m.source_text !== undefined ? m.source_text : m.surface;
    const right = m.target_text !== undefined ? m.target_text : m.canonical;
    table.append(h("tr", {},
      h("td", {}, mark(m.status)),
      h("td", {}, sim(m.similarity)),
      h("td", {},
        h("div", { text: left + "  →  " + right }),
        h("div", { class: "small muted" },
          h("span", { class: "chip", text: m.status }),
          m.status === "sealed" && !m.servable ? h("span", { class: "badge bad", text: "not servable" }) : null,
          m.verifier ? h("span", { class: "chip", text: "by " + m.verifier }) : null)),
      h("td", {}, onReject ? h("button", { class: "small danger", disabled: S.state.read_only,
        title: "wrong answer for THIS query — the pair stays valid for its own source",
        onclick: () => onReject(m) }, "Wrong for this") : null)));
  }
  box.append(table);
  return box;
}

async function sealWithOverride(path, body, okMessage) {
  try {
    await api(path, body);
    toast(okMessage, "ok");
    await refresh();
  } catch (e) {
    if (e.data && (e.data.code === "conflicting_seal" || e.data.code === "rejected_pair")) {
      if (confirm(e.message + "\n\nOverride and seal anyway? This is recorded as a deliberate overrule.")) {
        await act(path, { ...body, override: true }, "Sealed with an explicit override.");
      }
      return;
    }
    toast(e.message, "err");
  }
}

function translateResult(r) {
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

  card.append(candidates(r.matches, r.threshold, "source", "target",
    (m) => rejectMatch(r.query, m)));
  return card;
}

async function sealFromAsk(r) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const target = $("ask-seal-target").value.trim();
  if (!target) return toast("Nothing to seal — type the verified text.", "err");
  await sealWithOverride("/api/seal",
    { source: r.query.text, target, source_lang: r.query.source_lang,
      target_lang: r.query.target_lang, verifier: verifier(), origin: "ui:ask" },
    "Sealed. Ask again and it serves as tier 1.");
}

// `query` carries whatever the recipe asked with — the text and the two domain
// tags. Rejection is domain-generic: it suppresses one answer for one query key,
// whether that query was a phrase, an alias or a figure.
async function rejectMatch(query, m) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const reason = await askFor("Why is this the wrong answer for this query?", "reason");
  if (reason === null) return;
  await act("/api/reject-match", {
    source: query.source !== undefined ? query.source : query.text,
    source_lang: query.source_lang, target_lang: query.target_lang,
    pair_id: m.id, target_text: m.target_text !== undefined ? m.target_text : m.canonical,
    verifier: verifier(), reason,
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
      h("span", { class: "chip mono", text: S.state.ledger.path })),
    h("p", { class: "small muted", style: "margin:10px 0 0" },
      "The walk vouches for every entry except the newest — nothing follows it to " +
      "carry its hash. Pin this tip somewhere the ledger's writer cannot reach " +
      "(CI, a monitor) and check against it: ",
      h("code", { class: "mono", text: "nestor ledger verify --expect-head " + (l.head || "").slice(0, 16) + "…" })),
    h("p", { class: "small mono muted", style: "margin:4px 0 0", text: "head " + (l.head || "") })));

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
  if (s.identity && s.identity.required) {
    box.append(h("span", { class: "badge good", title:
      "each verifier signs with their own key, so a seal names a person",
      text: "per-verifier keys" }));
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

/* ---------- Signals: what the memory says that no single row does ---------- */
//
// Three findings the package records and nothing displayed. Each one is a
// question about the memory as a whole rather than about a pair, which is why
// none of them fit in the Memory list.

function viewSignals() {
  const view = $("view");
  if (!S.state.capabilities.curation) {
    view.append(h("div", { class: "card" }, h("p", { class: "empty",
      text: "This store does not implement the curation capability (storage.supports_curation)." })));
    return;
  }
  view.append(replacedCard(), rejectedQueriesCard(), junkPairsCard());
}

function replacedCard() {
  const rows = (S.signals && S.signals.replaced) || [];
  const card = h("div", { class: "card" },
    h("h2", { text: "Seals that were overwritten" }),
    h("p", { class: "small muted", text:
      "The memory keeps one row per source, so a replaced seal leaves no trace in the "
      + "store — the previous target and verifier exist only in the ledger. Sealing over "
      + "another verifier's answer is refused, so an entry here means somebody chose to "
      + "overrule a recorded human decision." }),
    h("div", { class: "row small" },
      h("label", { class: "row small", style: "gap:6px" },
        h("input", { type: "checkbox", checked: !!S.showAllReplaced,
                     onchange: (e) => { S.showAllReplaced = e.target.checked; refresh(); } }),
        "include self-corrections")));
  if (!rows.length) {
    card.append(h("p", { class: "empty", text: S.showAllReplaced
      ? "No seal has ever been replaced." : "No seal has been overruled by a different verifier." }));
    return card;
  }
  const table = h("table", {}, h("tr", {},
    ...["when", "pair", "replaced verifier", "by", "old → new target"].map((t) => h("th", { text: t }))));
  for (const r of rows) {
    table.append(h("tr", {},
      h("td", { class: "small muted", text: (r.ts || "").slice(0, 19).replace("T", " ") }),
      h("td", { class: "mono small", text: (r.pair_id || "").slice(0, 8) }),
      h("td", { text: r.replaced_verifier || "(unknown)" }),
      h("td", {}, h("b", { text: r.verifier || "(unknown)" }), " ",
        r.same_verifier ? h("span", { class: "chip", text: "self" })
                        : h("span", { class: "chip", style: "color:var(--rejected);border-color:var(--rejected)", text: "overruled" })),
      // Digests, not text: nestor.frank mirrors ledger entries verbatim into a
      // ledger somebody else holds, so the trail carries hashes.
      h("td", { class: "mono small",
                text: (r.replaced_target_sha || "?") + " → " + (r.target_sha || "?") })));
  }
  card.append(table);
  return card;
}

function rejectedQueriesCard() {
  const sig = (S.signals && S.signals.rejections) || { queries: [], pairs: [], rejections: 0 };
  const card = h("div", { class: "card" },
    h("h2", { text: "Queries the reviewers keep refusing" }),
    h("p", { class: "small muted", text:
      "Several different answers offered for one input, all refused. That is evidence about "
      + "the THRESHOLD in this domain rather than about any one pair — and the seal threshold "
      + "is one global constant, which no single value fits across corpora. Read from the "
      + `chain: ${sig.rejections} rejection(s) seen.` }));
  if (!sig.queries.length) {
    card.append(h("p", { class: "empty", text: "No query has been refused more than once." }));
    return card;
  }
  const table = h("table", {}, h("tr", {},
    ...["times", "query (normalized)", "distinct answers", "reviewers"].map((t) => h("th", { text: t }))));
  for (const q of sig.queries) {
    table.append(h("tr", {},
      h("td", {}, h("b", { text: String(q.rejections) })),
      h("td", { class: "mono small", text: q.query_norm }),
      h("td", { text: String(q.distinct_answers) }),
      h("td", { class: "small", text: q.verifiers.join(", ") })));
  }
  card.append(table);
  return card;
}

function junkPairsCard() {
  const sig = (S.signals && S.signals.rejections) || { pairs: [] };
  const card = h("div", { class: "card" },
    h("h2", { text: "Pairs refused against many queries" }),
    h("p", { class: "small muted", text:
      "A good mapping is the wrong answer now and then. One that is wrong for many unrelated "
      + "inputs is junk — and a sealed one is still being served while reviewers keep saying no. "
      + "Open it in Memory to unseal or reject it." }));
  if (!sig.pairs.length) {
    card.append(h("p", { class: "empty", text: "No pair has been refused for more than one query." }));
    return card;
  }
  for (const p of sig.pairs) {
    card.append(h("div", { class: "pair",
                           onclick: async () => { S.tab = "memory"; await refresh(); openPair(p.pair_id); } },
      h("div", { class: "texts" },
        mark(p.status),
        h("span", { class: "src", text: p.source_text || "(row is gone)" }),
        h("span", { class: "arrow", text: "→" }),
        h("span", { text: p.target_text })),
      h("div", { class: "row small muted", style: "margin-top:4px" },
        h("span", { class: "chip", text: p.queries + " queries refused" }),
        h("span", { class: "chip", text: p.status }),
        p.servable ? h("span", { class: "chip", style: "color:var(--rejected);border-color:var(--rejected)",
                                 text: "still served" }) : null,
        h("span", { class: "small", text: p.query_norms.slice(0, 4).join(" · ") }))));
  }
  return card;
}

function applyFilters() {
  const picked = $("f-domain").value === "" ? null : S.domains[Number($("f-domain").value)];
  S.filters = {
    contains: $("f-contains").value.trim(), status: $("f-status").value,
    verifier: $("f-verifier").value.trim(), unverifiable: $("f-unverifiable").checked ? "1" : "",
    source_lang: picked ? picked.source_lang : "", target_lang: picked ? picked.target_lang : "",
  };
  S.offset = 0;               // a new filter is a new list, not page 3 of it
  refresh();
}

function render() {
  tabs(); badges(); whoBox();
  const view = $("view");
  view.replaceChildren();
  if (S.tab === "queue") viewQueue();
  else if (S.tab === "memory") viewMemory();
  else if (S.tab === "ask") viewAsk();
  else if (S.tab === "signals") viewSignals();
  else viewLedger();
}

async function refresh() {
  try {
    S.state = await api("/api/state?session="
                        + encodeURIComponent(S.session ? S.session.token : ""));
    // The server is the authority on whether a token is still good; a stale one
    // in localStorage must not leave the header claiming somebody is signed in.
    if (S.state.identity && S.state.identity.required && !S.state.identity.signed_in) {
      S.session = null;
      localStorage.removeItem("nestor.session");
    }
    S.domains = (await api("/api/domains")).domains;
    if (S.tab === "queue" && S.state.capabilities.queue) S.queue = await api("/api/queue");
    if (S.tab === "memory" && S.state.capabilities.curation) {
      const q = new URLSearchParams(S.filters);
      q.set("offset", String(S.offset));
      q.set("limit", String(PAGE + 1));   // the extra row answers "is there more"
      const rows = (await api("/api/pairs?" + q.toString())).pairs;
      S.more = rows.length > PAGE;
      S.pairs = rows.slice(0, PAGE);
    }
    if (S.tab === "signals" && S.state.capabilities.curation) {
      const q = new URLSearchParams({ source_lang: S.filters.source_lang,
                                      target_lang: S.filters.target_lang });
      S.signals = {
        replaced: (await api("/api/replaced-seals?all=" + (S.showAllReplaced ? "1" : "0"))).replaced,
        rejections: await api("/api/rejections?" + q.toString()),
      };
    }
    if (S.tab === "ledger") {
      S.ledger = await api("/api/ledger?limit=200&kind=" + encodeURIComponent(S.ledgerKind || ""));
    }
    render();
  } catch (e) {
    toast(e.message, "err");
  }
}

S.typedVerifier = localStorage.getItem("nestor.verifier") || "";
const savedToken = localStorage.getItem("nestor.session");
api("/api/state?session=" + encodeURIComponent(savedToken || "")).then((s) => {
  if (!S.typedVerifier && s.verifier_hint) S.typedVerifier = s.verifier_hint;
  if (s.identity && s.identity.signed_in) {
    S.session = { token: savedToken, verifier: s.identity.signed_in };
  }
  refresh();
});
</script>
</body>
</html>
"""
