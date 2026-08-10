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
  --glow: #9a7830; --band: #ebe6dc; --warm: #5a5040;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14150f; --panel: #1c1e17; --ink: #ece9e1; --muted: #9c988e;
    --line: #2e3128; --accent: #8fbc9b; --sealed: #7fc39a; --draft: #d7a94f;
    --pending: #9c988e; --rejected: #e08376; --shadow: none;
    --glow: #c9a050; --band: #1a1510; --warm: #e8dcc8;
  }
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
body.shell-memory {
  display: flex; flex-direction: column; overflow: hidden;
}
body.shell-memory main#view {
  flex: 1; min-height: 0; max-width: none; margin: 0; padding: 0; overflow: hidden;
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
nav button.on { position: relative; border-color: transparent; }
nav button.on::after {
  content: ""; position: absolute; left: 12px; right: 12px; bottom: -1px;
  height: 2px; background: var(--accent);
}
main { padding: 22px; max-width: 1180px; margin: 0 auto; }
.mem-shell { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.mem-filters {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  padding: 12px 22px; border-bottom: 1px solid var(--line);
  background: var(--panel); flex-shrink: 0;
}
.mem-grid {
  flex: 1; display: grid; grid-template-columns: 1fr min(440px, 42vw);
  min-height: 0; align-items: stretch;
}
@media (max-width: 900px) { .mem-grid { grid-template-columns: 1fr; } }
.mem-list { overflow-y: auto; padding: 8px 14px 20px; border-right: 1px solid var(--line); min-height: 0; }
.mem-side { overflow-y: auto; padding: 16px 18px; min-height: 0; display: flex; flex-direction: column; gap: 14px; }
.mem-oracle {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; color: var(--muted); padding: 28px; min-height: 200px;
}
.mem-oracle .glyph { font-size: 42px; opacity: .35; margin-bottom: 12px; }
.pair.on {
  background: color-mix(in srgb, var(--accent) 10%, var(--panel));
  border-radius: 8px; padding-left: 8px; margin-left: -8px; margin-right: -8px;
}
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
.gap-context { margin-top: 8px; cursor: default; }
.gap-context summary { cursor: pointer; color: var(--accent); font-weight: 500; }
.gap-context .context-body a { word-break: break-all; }
.context-panel { white-space: pre-wrap; margin: 10px 0; padding: 10px; border: 1px solid var(--line);
  border-radius: 6px; background: color-mix(in srgb, var(--bg) 60%, var(--panel)); }
.commitment-opt { display: flex; gap: 8px; align-items: flex-start; margin: 8px 0; }
.commitment-opt input { margin-top: 4px; }
.commitment-seal-preview { margin-left: 22px; font-size: 12px; color: var(--muted); }
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

/* Fleet gate review — editorial desk, not a CRUD table */
body.fleet-review {
  --display: Georgia, "Iowan Old Style", "Palatino Linotype", Palatino, serif;
}
body.fleet-review {
  background:
    radial-gradient(ellipse 120% 80% at 10% -20%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 55%),
    radial-gradient(ellipse 90% 60% at 100% 100%, color-mix(in srgb, var(--glow) 10%, transparent), transparent 50%),
    var(--bg);
}
body.fleet-review header {
  background: color-mix(in srgb, var(--panel) 92%, var(--bg));
  border-bottom-color: color-mix(in srgb, var(--glow) 35%, var(--line));
}
body.fleet-review .brand b {
  font-family: var(--display);
  font-size: 22px;
  letter-spacing: 0.04em;
  color: color-mix(in srgb, var(--accent) 85%, var(--ink));
}
body.fleet-review .brand b::before {
  content: "◆";
  display: inline-block;
  margin-right: 10px;
  font-size: 0.65em;
  vertical-align: 0.15em;
  color: var(--glow);
  opacity: 0.9;
}
body.fleet-review nav { background: transparent; border-bottom-color: color-mix(in srgb, var(--line) 80%, transparent); }
body.fleet-review nav button.on { background: transparent; color: var(--glow); }
body.fleet-review nav button.on::after { background: var(--glow); height: 3px; }
.brief-band {
  flex-shrink: 0;
  padding: 10px 22px 12px;
  background: linear-gradient(90deg, var(--band), transparent 70%);
  border-bottom: 1px solid var(--line);
  display: flex; flex-wrap: wrap; align-items: center; gap: 14px 20px;
}
.brief-band .eyebrow {
  font: 11px/1 ui-monospace, monospace;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--warm) 70%, var(--muted));
}
.brief-band .brief-title {
  font-family: var(--display);
  font-size: 1.05rem;
  font-weight: normal;
  margin: 0;
  flex: 1;
  min-width: 200px;
}
.gate-progress { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
.gate-progress .track {
  width: 100px; height: 6px; border-radius: 99px;
  background: var(--line); overflow: hidden;
}
.gate-progress .track i {
  display: block; height: 100%; border-radius: 99px;
  background: linear-gradient(90deg, var(--sealed), var(--accent));
  transition: width 0.4s ease;
}
body.fleet-review .mem-filters {
  background: color-mix(in srgb, var(--bg) 70%, var(--panel));
  font-family: ui-monospace, monospace;
  font-size: 12px;
}
body.fleet-review .mem-list {
  padding: 16px 18px 28px;
  display: flex; flex-direction: column; gap: 12px;
}
.decision-card {
  font-family: var(--display);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px 14px 20px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 12px color-mix(in srgb, #000 8%, transparent);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s;
}
.decision-card::before {
  content: "";
  position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: var(--line);
}
.decision-card.is-draft::before { background: linear-gradient(180deg, var(--draft), color-mix(in srgb, var(--draft) 40%, var(--line))); }
.decision-card.is-sealed::before { background: linear-gradient(180deg, var(--sealed), var(--accent)); }
.decision-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px color-mix(in srgb, #000 14%, transparent);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
}
.decision-card.on {
  border-color: color-mix(in srgb, var(--glow) 55%, var(--accent));
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--glow) 30%, transparent),
              0 12px 32px color-mix(in srgb, #000 18%, transparent);
}
.decision-card-gutter {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.gap-code {
  font-family: ui-monospace, monospace;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--glow);
}
.status-ribbon {
  font: 10px/1 ui-monospace, monospace;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  padding: 4px 9px;
  border-radius: 99px;
  border: 1px solid var(--line);
  color: var(--muted);
}
.is-sealed .status-ribbon { color: var(--sealed); border-color: color-mix(in srgb, var(--sealed) 45%, var(--line)); }
.is-draft .status-ribbon {
  color: var(--draft);
  border-color: color-mix(in srgb, var(--draft) 50%, var(--line));
  animation: pulse-draft 2.5s ease-in-out infinite;
}
@keyframes pulse-draft {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}
.decision-headline { margin: 0 0 8px; font-size: 1.12rem; font-weight: normal; line-height: 1.35; }
.decision-teaser { margin: 0; font-size: 0.92rem; color: var(--muted); line-height: 1.5; font-style: italic; }
.decision-cta {
  margin: 12px 0 0;
  font: 12px/1 ui-monospace, monospace;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--draft);
}
.decision-byline { margin: 10px 0 0; font-size: 12px; color: var(--sealed); }
body.fleet-review .mem-side { padding: 20px 22px 28px; }
.stage-card {
  font-family: var(--display);
  background: color-mix(in srgb, var(--panel) 95%, var(--bg));
  border: 1px solid color-mix(in srgb, var(--glow) 25%, var(--line));
  border-radius: 16px;
  padding: 20px 22px;
  box-shadow: 0 4px 20px color-mix(in srgb, #000 10%, transparent);
}
.stage-card .stage-eyebrow {
  font: 11px/1 ui-monospace, monospace;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--warm) 80%, var(--muted));
  margin-bottom: 6px;
}
.stage-card .stage-headline { margin: 0 0 12px; font-size: 1.35rem; font-weight: normal; line-height: 1.3; }
.stage-card .stage-lede { margin: 0 0 16px; font-style: italic; color: var(--muted); line-height: 1.55; }
.stage-card .stage-question {
  margin: 0 0 18px;
  padding: 12px 14px;
  border-left: 3px solid var(--glow);
  background: color-mix(in srgb, var(--bg) 50%, transparent);
  border-radius: 0 8px 8px 0;
  line-height: 1.5;
}
.choice-card {
  display: flex; gap: 12px; align-items: flex-start;
  margin: 10px 0; padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
  font-family: var(--display);
  font-size: 0.95rem;
  line-height: 1.45;
}
.choice-card:hover { border-color: color-mix(in srgb, var(--accent) 50%, var(--line)); }
.choice-card.is-selected {
  border-color: var(--glow);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--glow) 40%, transparent);
  background: color-mix(in srgb, var(--glow) 8%, var(--panel));
}
.choice-card input { margin-top: 5px; accent-color: var(--glow); }
.choice-letter {
  font-family: ui-monospace, monospace;
  font-weight: 700;
  color: var(--glow);
  min-width: 1.5em;
}
.sealed-verdict {
  margin: 16px 0;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px dashed color-mix(in srgb, var(--sealed) 50%, var(--line));
  background: color-mix(in srgb, var(--sealed) 8%, var(--panel));
  font-size: 1rem;
  line-height: 1.45;
}
.sealed-verdict b { color: var(--sealed); font-weight: 600; }
body.fleet-review .mem-oracle {
  font-family: var(--display);
  font-style: italic;
  font-size: 1.05rem;
  line-height: 1.6;
}
body.fleet-review .mem-oracle .glyph {
  font-size: 56px;
  opacity: 0.25;
  animation: drift 6s ease-in-out infinite;
}
@keyframes drift {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-6px) rotate(8deg); }
}
body.fleet-review button.primary {
  background: linear-gradient(180deg, color-mix(in srgb, var(--glow) 90%, #fff), var(--glow));
  border-color: var(--glow);
  color: #1a1208;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 10px 18px;
}
.provenance-fold { margin-top: 18px; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px; }
.provenance-fold summary { cursor: pointer; color: var(--accent); font-weight: 500; }
body.fleet-review.gate-closed .brief-band {
  background: linear-gradient(105deg, var(--band), color-mix(in srgb, var(--sealed) 12%, var(--band)) 45%, transparent 85%);
}
.fleet-echo {
  margin-top: 14px; padding: 12px 14px; border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--sealed) 35%, var(--line));
  background: color-mix(in srgb, var(--sealed) 6%, var(--panel));
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 13px; line-height: 1.45;
}
.fleet-echo b { color: var(--sealed); font-weight: 600; }
.fleet-echo .mono { font-size: 11px; color: var(--muted); }
.echo-pill {
  font: 10px/1 ui-monospace, monospace; letter-spacing: 0.08em; text-transform: uppercase;
  padding: 3px 8px; border-radius: 99px; margin-left: 8px;
  border: 1px solid color-mix(in srgb, var(--sealed) 40%, var(--line));
  color: var(--sealed);
}
.echo-pill.wait { color: var(--draft); border-color: color-mix(in srgb, var(--draft) 45%, var(--line)); }
.mem-list-title {
  font: 11px/1 ui-monospace, monospace; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--muted); padding: 4px 6px 10px;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
body.fleet-review .decision-card { animation: card-in 0.4s ease backwards; }
body.fleet-review .mem-list .decision-card:nth-child(2) { animation-delay: 0.04s; }
body.fleet-review .mem-list .decision-card:nth-child(3) { animation-delay: 0.08s; }
body.fleet-review .mem-list .decision-card:nth-child(4) { animation-delay: 0.12s; }
body.fleet-review .mem-list .decision-card:nth-child(5) { animation-delay: 0.16s; }
body.fleet-review .mem-list .decision-card:nth-child(6) { animation-delay: 0.2s; }
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
<!-- The in-browser-key manager (Nestor#17): generate, import, unlock, forget.
     Filled by renderKeyDialog() — a plain div, not a <form method=dialog>,
     because it has several independent async steps (generate, sign a
     self-check, enroll) rather than one field and an OK button. -->
<dialog id="key-dialog"><div id="key-dialog-body"></div></dialog>
<!-- Sign & Seal confirmation (Nestor#17): the human approves the EXACT bytes
     about to be signed — server-computed source_norm, and the target/verifier
     already on screen — before crypto.subtle ever touches them. This is the
     one dialog in the page a client signature is never produced without. -->
<dialog id="sign-dialog"><div id="sign-dialog-body"></div></dialog>

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
            commitmentPickByPair: {},
            gateEcho: null,
            recipe: localStorage.getItem("nestor.recipe") || "translate",
            filters: { status: "", contains: "", verifier: "", unverifiable: "",
                       source_lang: "", target_lang: "" },
            // Nestor#17's browser signer: an in-browser Ed25519 identity, live
            // only in this tab. `browserKey.privateKey` is a non-extractable
            // CryptoKey handle (or a session-only imported one) — never a byte
            // string, and never sent anywhere. `null` means no browser-key
            // identity is unlocked; the typed/session identity is unaffected.
            browserKey: null,
            keyDialogMode: "menu" };

/* ---------- tiny DOM helper: every value lands as text, never as markup ---- */
function relativeAge(iso) {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return min + "m ago";
  const hr = Math.floor(min / 60);
  if (hr < 48) return hr + "h ago";
  const day = Math.floor(hr / 24);
  if (day < 14) return day + "d ago";
  return iso.slice(0, 10);
}

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
  // Browser-key identity wins when unlocked: it is the one that can actually
  // seal without a session (see signSealFields / _verifier_for_seal), so it
  // is also the one every "who are you" gate in the page should show.
  if (S.browserKey) return S.browserKey.verifier;
  const box = $("verifier");
  return box ? box.value.trim() : (S.session ? S.session.verifier : "");
}

/* ---------- in-browser Ed25519 signing (Nestor#17) -------------------------
 *
 * The last open cell of #17: an instance that VERIFIES a seal it structurally
 * cannot have signed, because the private key never touches it. Everything in
 * this block runs entirely in the browser and never sends anything but a
 * public key (at enrollment, printed for the human to run themselves — see
 * enrollmentBlock) and, at seal time, a signature over fields the human has
 * already seen (see confirmSign / signSealFields). See decision 0078.
 *
 * Key custody: `crypto.subtle.generateKey({name:"Ed25519"}, false, ...)` —
 * extractable=false on the PRIVATE key. WebCrypto always returns the paired
 * PUBLIC key extractable regardless of that flag (measured against this exact
 * Chromium build before relying on it), which is the asymmetry this needs:
 * the public half has to leave the browser, the private half structurally
 * cannot. The non-extractable CryptoKey is then either kept only in memory
 * for this tab (session-only) or written into IndexedDB as a structured-clone
 * value — IndexedDB is the standard place an unexportable CryptoKey persists;
 * nothing here ever asks WebCrypto to export the private key, so there is no
 * raw-bytes form of it in this page to leak in the first place.
 */
const NESTOR_IDB_NAME = "nestor-keys", NESTOR_IDB_STORE = "identities";

function idbOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(NESTOR_IDB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(NESTOR_IDB_STORE)) {
        req.result.createObjectStore(NESTOR_IDB_STORE, { keyPath: "verifier" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function idbPut(record) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(NESTOR_IDB_STORE, "readwrite");
    tx.objectStore(NESTOR_IDB_STORE).put(record);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
async function idbGet(verifierName) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(NESTOR_IDB_STORE, "readonly");
    const req = tx.objectStore(NESTOR_IDB_STORE).get(verifierName);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}
async function idbList() {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(NESTOR_IDB_STORE, "readonly");
    const req = tx.objectStore(NESTOR_IDB_STORE).getAll();
    req.onsuccess = () => resolve((req.result || []).sort((a, b) => a.verifier.localeCompare(b.verifier)));
    req.onerror = () => reject(req.error);
  });
}
async function idbDelete(verifierName) {
  const db = await idbOpen();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(NESTOR_IDB_STORE, "readwrite");
    tx.objectStore(NESTOR_IDB_STORE).delete(verifierName);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// Cached after the first check — generateKey is not free, and every render of
// the "acting as" box would otherwise probe it again.
let _ed25519Support = null;
function ed25519Supported() {
  if (_ed25519Support === null) {
    _ed25519Support = (async () => {
      try {
        if (!window.isSecureContext || !window.crypto || !window.crypto.subtle) return false;
        await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"]);
        return true;
      } catch (e) { return false; }
    })();
  }
  return _ed25519Support;
}

function hex(buf) {
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function hexToBytes(s) {
  const clean = (s || "").trim().replace(/\s+/g, "");
  if (!/^[0-9a-fA-F]*$/.test(clean) || clean.length % 2 !== 0) {
    throw new Error("expected hex (0-9, a-f, A-F), an even number of digits");
  }
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
}

async function generateBrowserIdentity(verifierName, persist) {
  const kp = await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"]);
  const publicHex = hex(await crypto.subtle.exportKey("raw", kp.publicKey));
  const record = { verifier: verifierName, publicHex, privateKey: kp.privateKey,
                    createdAt: new Date().toISOString(), imported: false };
  if (persist) await idbPut(record);
  return record;
}

// The fixed, parameter-free PKCS8 DER header WebCrypto needs to import a raw
// 32-byte Ed25519 seed as a private key: `importKey("raw", ...)` is only
// defined for the PUBLIC half (measured against this Chromium build: raw
// PRIVATE import fails outright), so the seed is wrapped in the constant
// prefix every unencrypted, parameter-free Ed25519 PKCS8 key shares — the
// format differs from key to key only in its final 32 bytes. See decision
// 0078 for the round-trip this was checked against before being relied on.
const ED25519_PKCS8_PREFIX_HEX = "302e020100300506032b657004220420";

async function importBrowserIdentity(verifierName, privHex, pubHexOrEmpty, persist) {
  const raw = hexToBytes(privHex);
  if (raw.length !== 32) {
    throw new Error("an ed25519 private key is 32 raw bytes — 64 hex characters, the same form " +
      "a Nestor keyring file's \"private\" field stores (not PEM, not PKCS8, not a passphrase-" +
      "protected file)");
  }
  const prefix = hexToBytes(ED25519_PKCS8_PREFIX_HEX);
  const pkcs8 = new Uint8Array(prefix.length + raw.length);
  pkcs8.set(prefix, 0);
  pkcs8.set(raw, prefix.length);
  const privateKey = await crypto.subtle.importKey("pkcs8", pkcs8, { name: "Ed25519" }, false, ["sign"]);

  let publicHex = (pubHexOrEmpty || "").trim();
  if (publicHex) {
    const pubRaw = hexToBytes(publicHex);
    if (pubRaw.length !== 32) throw new Error("an ed25519 public key is 32 raw bytes — 64 hex characters");
    const publicKey = await crypto.subtle.importKey("raw", pubRaw, { name: "Ed25519" }, true, ["verify"]);
    // Self-check: sign a random client-side challenge with the imported
    // private key and verify it against the imported public key, both via
    // crypto.subtle, before persisting anything — catches a copy-paste
    // mismatch here instead of at seal time, where the failure would read
    // as a forged signature rather than as a typo.
    const challenge = crypto.getRandomValues(new Uint8Array(32));
    const sig = await crypto.subtle.sign({ name: "Ed25519" }, privateKey, challenge);
    const ok = await crypto.subtle.verify({ name: "Ed25519" }, publicKey, sig, challenge);
    if (!ok) throw new Error("that private key and public key do not form a pair — check both values");
    publicHex = hex(pubRaw);
  }
  const record = { verifier: verifierName, publicHex, privateKey,
                    createdAt: new Date().toISOString(), imported: true };
  if (persist) await idbPut(record);
  return record;
}

/* ---------- the frozen wire contract, reproduced byte-for-byte ------------
 *
 * signing._message is FROZEN (nestor/signing.py):
 *   json.dumps([source_norm, target_text, verifier],
 *              separators=(",", ":"), ensure_ascii=False).encode("utf-8")
 *
 * JSON.stringify is not relied on here — it is not proven byte-identical to
 * json.dumps for arbitrary input, and Nestor accepts arbitrary human-typed
 * target text, so there is no smaller "allowed" character set to restrict to
 * instead. pyJsonString hand-encodes each string the way CPython's json.dumps
 * does for exactly this call shape: escape `"`, `\`, and code points below
 * 0x20 (`\b\t\n\f\r` where Python uses those, `\u00XX` otherwise), and emit
 * every other code point literally (ensure_ascii=False — U+2028/U+2029, 0x7f,
 * and non-ASCII letters all pass through unescaped, exactly as json.dumps
 * leaves them). Checked, not assumed: this table was run against live
 * CPython 3.11 and this Chromium build side by side — matching strings AND
 * matching UTF-8 bytes — for a plain-ASCII case, a non-ASCII letter, an
 * embedded quote, raw control bytes 0x00/0x1f/0x7f, a backslash, and a
 * non-BMP emoji, before being relied on here. tests/test_client_signed_seals.py
 * pins the same table from the Python side.
 *
 * The one case Python and a naive JS port CANNOT agree on: an unpaired UTF-16
 * surrogate. Python's str.encode("utf-8") refuses one outright
 * (UnicodeEncodeError, no surrogatepass); TextEncoder silently replaces it
 * with U+FFFD. hasLoneSurrogate refuses it client-side, with a clear message,
 * before any bytes are built — the mandated alternative to silently producing
 * bytes Python could never have produced from the same string.
 */
function hasLoneSurrogate(s) {
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) {                 // high surrogate
      const next = s.charCodeAt(i + 1);
      if (Number.isNaN(next) || next < 0xdc00 || next > 0xdfff) return true;
      i++;                                            // paired — skip the low half
    } else if (c >= 0xdc00 && c <= 0xdfff) {           // unpaired low surrogate
      return true;
    }
  }
  return false;
}

function pyJsonString(s) {
  let out = '"';
  for (const ch of s) {          // iterates by CODE POINT (keeps a surrogate
                                  // pair together), matching Python's str
    const cp = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === '\\') out += '\\\\';
    else if (cp === 0x08) out += '\\b';
    else if (cp === 0x09) out += '\\t';
    else if (cp === 0x0a) out += '\\n';
    else if (cp === 0x0c) out += '\\f';
    else if (cp === 0x0d) out += '\\r';
    else if (cp < 0x20) out += '\\u' + cp.toString(16).padStart(4, '0');
    else out += ch;
  }
  return out + '"';
}
function pyJsonArray(values) { return '[' + values.map(pyJsonString).join(',') + ']'; }

function frozenMessageBytes(sourceNorm, targetText, verifierName) {
  for (const [label, v] of [["the normalized source", sourceNorm], ["the target text", targetText],
                             ["the verifier name", verifierName]]) {
    if (hasLoneSurrogate(v)) {
      throw new Error(label + " contains an unpaired UTF-16 surrogate. The frozen signing " +
        "contract cannot represent that the same way in Python and in the browser (Python " +
        "refuses to encode it at all) — remove or replace that character before sealing.");
    }
  }
  return new TextEncoder().encode(pyJsonArray([sourceNorm, targetText, verifierName]));
}

async function signWithBrowserKey(sourceNorm, targetText, verifierName) {
  if (!S.browserKey) throw new Error("no browser key is unlocked");
  const message = frozenMessageBytes(sourceNorm, targetText, verifierName);
  const sig = await crypto.subtle.sign({ name: "Ed25519" }, S.browserKey.privateKey, message);
  return hex(sig);
}

/* ---------- Sign & seal: the human approves the exact bytes ---------------
 *
 * `target_text` and `verifier` here are the values already on screen and
 * approved by the human clicking "Seal" — never echoed back from some OTHER
 * server response the human did not look at. `source_norm` is the one field
 * the client cannot compute alone (it is a domain Matcher method, not a pure
 * function of the text), so it comes from the read-only /api/normalize
 * endpoint — which writes nothing and is reachable even under --read-only —
 * and is DISPLAYED, not trusted blindly, in confirmSign before anything is
 * signed. This is the entire point: a compromised or merely buggy server
 * could return a norm for different bytes than it will actually check the
 * seal against, and showing it is what lets a human notice.
 */
async function signSealFields(sourceText, targetText, sourceLang, targetLang) {
  if (!S.browserKey) return { verifier: verifier() };     // unchanged: server signs
  const who = S.browserKey.verifier;
  let norm;
  try {
    norm = (await api("/api/normalize",
      { text: sourceText, source_lang: sourceLang, target_lang: targetLang })).source_norm;
  } catch (e) { toast("Could not normalize the source text: " + e.message, "err"); return null; }
  const approved = await confirmSign(norm, targetText, who);
  if (!approved) return null;
  try {
    const seal_sig = await signWithBrowserKey(norm, targetText, who);
    return { verifier: who, seal_sig };
  } catch (e) { toast("Signing failed: " + e.message, "err"); return null; }
}

function confirmSign(norm, target, who) {
  return new Promise((resolve) => {
    const dlg = $("sign-dialog"), body = $("sign-dialog-body");
    let settled = false;
    const finish = (v) => { if (settled) return; settled = true; dlg.close(); resolve(v); };
    body.replaceChildren(
      h("h2", { style: "margin:0 0 10px;font-size:15px", text: "Sign & seal" }),
      h("p", { class: "small muted", style: "margin:0 0 10px" },
        "This is exactly what " + who + "'s browser key is about to sign — the server-computed, " +
        "read-only normalized source, and the target and verifier as they appear below. Nothing " +
        "is written until after you sign."),
      h("div", { class: "context-panel small" },
        h("div", {}, h("b", {}, "source_norm  "), h("span", { class: "mono", text: norm })),
        h("div", { style: "margin-top:4px" }, h("b", {}, "target  "), h("span", { class: "mono", text: target })),
        h("div", { style: "margin-top:4px" }, h("b", {}, "verifier  "), h("span", { class: "mono", text: who }))),
      h("div", { class: "row", style: "justify-content:flex-end;margin-top:14px;gap:8px" },
        h("button", { onclick: () => finish(false) }, "Cancel"),
        h("button", { class: "primary", onclick: () => finish(true) }, "Sign & seal")));
    dlg.onclose = () => finish(dlg.returnValue === "ok" ? true : false);
    dlg.showModal();
  });
}

/* ---------- the key manager dialog ------------------------------------------ */
function keyDialogChrome(kids) {
  return [
    h("div", { class: "row", style: "justify-content:space-between;align-items:flex-start;margin-bottom:10px" },
      h("h2", { style: "margin:0;font-size:15px", text: "In-browser signing key" }),
      h("button", { class: "small", onclick: () => $("key-dialog").close() }, "Close")),
    ...kids,
  ];
}

async function openKeyDialog() {
  S.keyDialogMode = "menu";
  await renderKeyDialog();
  $("key-dialog").showModal();
}

async function renderKeyDialog() {
  const body = $("key-dialog-body");
  const supported = await ed25519Supported();
  if (!supported) {
    body.replaceChildren(...keyDialogChrome([
      h("p", {}, "This browser's WebCrypto does not implement Ed25519 " +
        "(crypto.subtle.generateKey({name:\"Ed25519\"}) failed, or this page is not a secure " +
        "context). Recent Chrome, Edge, Firefox and Safari support it; older ones do not. An " +
        "in-browser key cannot be used here — sign in with a shared key instead.")]));
    return;
  }
  const identities = await idbList().catch(() => []);
  let content;
  if (S.keyDialogMode === "generate") content = keyDialogGenerate();
  else if (S.keyDialogMode === "import") content = keyDialogImport();
  else content = keyDialogMenu(identities);
  body.replaceChildren(...keyDialogChrome(content));
}

function keyDialogMenu(identities) {
  const kids = [
    h("p", { class: "small muted", style: "margin:0 0 12px" },
      "The private key is generated by crypto.subtle, marked non-extractable, and kept in this " +
      "browser (IndexedDB, or only this tab if you choose not to store it). It never leaves this " +
      "page — sealing signs here and sends only the signature. It proves the browser that holds " +
      "the key signed, not which human is at the keyboard — the same limit a password has."),
  ];
  if (identities.length) {
    kids.push(h("div", { class: "small muted", style: "margin-bottom:4px", text: "stored on this device:" }));
    for (const rec of identities) {
      kids.push(h("div", { class: "row", style: "justify-content:space-between;margin:4px 0" },
        h("span", {},
          h("b", { text: rec.verifier }),
          h("span", { class: "mono small muted", style: "margin-left:8px",
                      text: (rec.publicHex || "(no public key recorded)").slice(0, 16) + "…" })),
        h("span", { class: "row", style: "gap:6px" },
          h("button", { class: "primary small", onclick: () => unlockStored(rec.verifier) }, "Use"),
          h("button", { class: "small danger", onclick: () => forgetStored(rec.verifier) }, "Forget"))));
    }
  } else {
    kids.push(h("p", { class: "empty small", text: "No browser key stored on this device yet." }));
  }
  kids.push(h("div", { class: "row", style: "margin-top:14px;gap:8px" },
    h("button", { class: "primary small",
      onclick: () => { S.keyDialogMode = "generate"; renderKeyDialog(); } }, "Generate a new identity"),
    h("button", { class: "small",
      onclick: () => { S.keyDialogMode = "import"; renderKeyDialog(); } }, "Import an existing key")));
  kids.push(h("p", { class: "small muted", style: "margin-top:14px" },
    "Can seal from Queue (once you edit the candidate text), Memory, and Ask → Translate. It " +
    "cannot yet sign in for unseal, reject, restore, or the entity/numeric recipes — those need " +
    "a shared-key sign-in above (decision 0078 says why)."));
  return kids;
}

function enrollmentBlock(name, publicHex) {
  const cmd = "nestor keys add " + name + " --type ed25519 --public " + publicHex;
  return h("div", { class: "context-panel small", style: "margin-top:10px" },
    h("p", { style: "margin:0 0 6px" }, h("b", {}, "Public key — nothing else was sent anywhere:")),
    h("p", { class: "mono", style: "word-break:break-all;margin:0 0 8px", text: publicHex }),
    h("p", { style: "margin:0 0 4px" }, h("b", {}, "Enroll it yourself, out of band:")),
    h("p", { class: "mono", style: "word-break:break-all;margin:0", text: cmd }),
    h("p", { class: "small muted", style: "margin-top:8px" },
      "Run that on the machine that holds this instance's keyring. This page never runs it for " +
      "you and never could — it only ever had the public half. Until it is enrolled, a seal " +
      "signed with this key is refused as an unknown verifier."));
}

function keyDialogGenerate() {
  return [
    h("p", { class: "small muted", style: "margin:0 0 10px" },
      "Names the verifier this key signs as. Generating changes nothing server-side by itself — " +
      "the server only learns about this key once you run the enrollment command it prints, " +
      "yourself, out of band."),
    h("input", { id: "gen-name", placeholder: "verifier name", style: "width:100%;margin-bottom:8px",
                 value: S.typedVerifier || (S.session ? S.session.verifier : "") }),
    h("label", { class: "row small", style: "gap:6px;margin-bottom:10px" },
      h("input", { type: "checkbox", id: "gen-persist", checked: true }),
      "remember this key on this device (IndexedDB) — uncheck for a one-tab, this-session-only key"),
    h("div", { class: "row" },
      h("button", { class: "small", onclick: () => { S.keyDialogMode = "menu"; renderKeyDialog(); } }, "Back"),
      h("button", { class: "primary small", onclick: doGenerate }, "Generate")),
    h("div", { id: "gen-result" }),
  ];
}

async function doGenerate() {
  const name = $("gen-name").value.trim();
  if (!name) return toast("Name the verifier this key signs as.", "err");
  const persist = $("gen-persist").checked;
  try {
    const rec = await generateBrowserIdentity(name, persist);
    S.browserKey = { verifier: name, privateKey: rec.privateKey, publicHex: rec.publicHex };
    $("gen-result").replaceChildren(enrollmentBlock(name, rec.publicHex));
    render();
  } catch (e) { toast(e.message, "err"); }
}

function keyDialogImport() {
  return [
    h("p", { class: "small muted", style: "margin:0 0 10px" },
      "Bring in an Ed25519 private key minted elsewhere — RAW 32-byte hex (64 hex characters), " +
      "the same form a Nestor keyring file's \"private\" field stores. Not PEM, not PKCS8, not a " +
      "passphrase-protected file."),
    h("input", { id: "imp-name", placeholder: "verifier name", style: "width:100%;margin-bottom:8px",
                 value: S.typedVerifier || (S.session ? S.session.verifier : "") }),
    h("input", { id: "imp-priv", type: "password", placeholder: "private key — 64 hex characters",
                 style: "width:100%;margin-bottom:8px;font-family:ui-monospace,monospace" }),
    h("input", { id: "imp-pub", placeholder: "public key — 64 hex characters (optional, self-checked)",
                 style: "width:100%;margin-bottom:8px;font-family:ui-monospace,monospace" }),
    h("label", { class: "row small", style: "gap:6px;margin-bottom:10px" },
      h("input", { type: "checkbox", id: "imp-persist", checked: true }),
      "remember this key on this device (IndexedDB)"),
    h("div", { class: "row" },
      h("button", { class: "small", onclick: () => { S.keyDialogMode = "menu"; renderKeyDialog(); } }, "Back"),
      h("button", { class: "primary small", onclick: doImport }, "Import")),
    h("div", { id: "imp-result" }),
  ];
}

async function doImport() {
  const name = $("imp-name").value.trim();
  const privHex = $("imp-priv").value.trim();
  const pubHex = $("imp-pub").value.trim();
  if (!name) return toast("Name the verifier this key signs as.", "err");
  if (!privHex) return toast("Paste the private key.", "err");
  try {
    const rec = await importBrowserIdentity(name, privHex, pubHex, $("imp-persist").checked);
    S.browserKey = { verifier: name, privateKey: rec.privateKey, publicHex: rec.publicHex };
    $("imp-result").replaceChildren(rec.publicHex
      ? enrollmentBlock(name, rec.publicHex)
      : h("p", { class: "small muted", style: "margin-top:8px" },
          "Imported — no public key was given to self-check against. Confirm with `nestor keys " +
          "list` that this instance already holds the matching public key for " + name + "."));
    render();
    toast("Imported. Signing as " + name + " with the browser key.", "ok");
  } catch (e) { toast(e.message, "err"); }
}

async function unlockStored(name) {
  try {
    const rec = await idbGet(name);
    if (!rec) return toast("No stored key for " + name + ".", "err");
    S.browserKey = { verifier: name, privateKey: rec.privateKey, publicHex: rec.publicHex };
    $("key-dialog").close();
    render();
    toast("Signing as " + name + " with the browser key stored on this device.", "ok");
  } catch (e) { toast(e.message, "err"); }
}

async function forgetStored(name) {
  if (!confirm("Forget the browser key stored for " + name + " on this device? If it was never " +
               "enrolled anywhere else, nothing will ever be able to sign as " + name + " again.")) {
    return;
  }
  await idbDelete(name);
  if (S.browserKey && S.browserKey.verifier === name) S.browserKey = null;
  await renderKeyDialog();
  render();
}

/* ---------- identity -------------------------------------------------------
 *
 * Without a keyring the "acting as" box is a text field, and the honest
 * description of that is: this UI seals as whatever you type. With one, the
 * same corner offers two sign-ins. A shared-key one — a verifier presents
 * their own seal key, and every decision in the session is signed with it
 * server-side, so the name on a seal is evidence about a person rather than
 * evidence that somebody typed it — and, now, an in-browser one: a verifier
 * unlocks (or generates, or imports) an Ed25519 key that never leaves this
 * page, and sealing signs client-side (see the block above). Both prove a
 * key; neither proves a face. The shared-key form additionally requires the
 * SERVER to hold that key, which a verifier who wants true client custody may
 * not want — that is exactly the gap the browser-key form closes.
 *
 * The shared-key token is kept here and sent with every write; that key
 * itself is never kept. The browser-key private CryptoKey is kept (in
 * IndexedDB, or only in memory) but never sent anywhere at all.
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
  if (S.browserKey) {
    box.append(
      h("label", { text: "browser key" }),
      h("b", { title: "signing every seal client-side with this name's in-browser key",
               text: S.browserKey.verifier }),
      h("button", { class: "small", onclick: openKeyDialog }, "Switch"),
      h("button", { class: "small", onclick: () => { S.browserKey = null; render(); } }, "Lock"));
    return;
  }
  if (S.session && S.session.verifier) {
    box.append(h("label", { text: "signed in as" }),
      h("b", { text: S.session.verifier }),
      h("button", { class: "small", onclick: signOut }, "Sign out"),
      h("button", { class: "small", onclick: openKeyDialog }, "or use a browser key"));
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
    h("button", { class: "primary small", onclick: signIn }, "Sign in"),
    h("button", { class: "small", onclick: openKeyDialog }, "Browser key…"));
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
        onclick: () => sealSegment(doc, seg, box.value) }, "Seal"),
      h("button", { class: "small danger", disabled: ro || !seg.candidate,
        onclick: () => rejectSegment(seg) }, "Reject"),
      h("span", { class: "chip mono", text: (seg.id || "").slice(0, 8) })));
}

async function sealSegment(doc, seg, target) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const trimmed = target.trim();
  if (!trimmed) return toast("Nothing to seal — type the verified text.", "err");
  // /api/queue/seal only accepts seal_sig on the EDITED branch (server-side,
  // matching decision 0077's scope) — sealing an unedited candidate verbatim
  // still goes through `graduate_segment`, which has no signature seam and
  // needs a session. Checked here so a browser-key-only verifier gets a clear
  // answer instead of a wasted sign-and-then-401 round trip.
  const willEdit = trimmed !== (seg.candidate || "");
  if (S.browserKey && !willEdit) {
    return toast("Sealing this candidate as drafted (no edits) still needs a shared-key sign-in " +
                 "— only an edited correction seals with a browser key here. Edit the text, or " +
                 "sign in above.", "err");
  }
  const extra = await signSealFields(seg.source_text, trimmed,
                                     doc.source_lang || (S.state && S.state.domain.source_lang),
                                     doc.target_lang || (S.state && S.state.domain.target_lang));
  if (!extra) return;
  const body = { segment_id: seg.id, target: trimmed, ...extra };
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
  const filterRow = h("div", { class: "row" },
    h("input", { id: "f-contains", placeholder: "contains…", value: f.contains,
                 onkeydown: (e) => { if (e.key === "Enter") applyFilters(); } }),
    h("select", { id: "f-status" },
      ...[["", "any status"], ["sealed", "sealed"], ["draft", "draft"], ["rejected", "rejected"]]
        .map(([v, t]) => h("option", { value: v, selected: f.status === v }, t))),
    h("input", { id: "f-verifier", placeholder: "verifier", value: f.verifier, size: 12 }),
    h("select", { id: "f-domain", title: "domain (source → target tags)" },
      h("option", { value: "", selected: !f.source_lang && !f.target_lang }, "every domain"),
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
      h("button", { class: "small" }, "Export JSON")));

  const list = h("div", { class: "mem-list" });
  if (fleetGapReviewMode()) {
    list.append(h("div", { class: "mem-list-title", text: "Decisions you sealed" }));
  }
  if (!S.pairs.length) list.append(h("p", { class: "empty", text: "No pairs match." }));
  for (const p of S.pairs) list.append(pairRow(p));
  if (S.pairs.length || S.offset) list.append(pager());

  const sideKids = [];
  if (S.detail) {
    sideKids.push(detailPanel());
    if (!fleetGapReviewMode()) {
      sideKids.push(sealForm(), portableCard());
    }
  } else {
    sideKids.push(h("div", { class: "mem-oracle" },
      h("div", { class: "glyph", text: fleetGapReviewMode() ? "☽" : "◇" }),
      h("p", { text: fleetGapReviewMode()
        ? "Choose a card. The fleet waits on your witness — not another dashboard row."
        : "Select a pair to inspect it." })));
  }

  const shellKids = [];
  if (fleetGapReviewMode()) shellKids.push(briefBand());
  shellKids.push(
    h("div", { class: "mem-filters" }, filterRow),
    h("div", { class: "mem-grid" }, list, h("div", { class: "mem-side" }, ...sideKids)));
  view.append(h("div", { class: "mem-shell" }, ...shellKids));
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

function stripCommitmentMachine(text) {
  const i = (text || "").indexOf("---seal---");
  return i >= 0 ? text.slice(0, i).trim() : (text || "");
}

function parseCommitmentChoices(text) {
  const raw = text || "";
  const display = stripCommitmentMachine(raw);
  const choices = [];
  const sealMap = {};
  if (raw.includes("---seal---")) {
    for (const line of raw.split("\n")) {
      const m = line.match(/^([A-D])\|(.+)$/);
      if (m) sealMap[m[1]] = m[2];
    }
  }
  for (const line of display.split("\n")) {
    const m = line.match(/^([A-D])\u0029\s+(.+)$/);
    if (m) {
      choices.push({
        id: m[1],
        label: m[2],
        sealText: sealMap[m[1]] || ("DECISION: " + m[2]),
      });
    }
  }
  return { display, choices };
}

function commitmentSummary(text) {
  const { display, choices } = parseCommitmentChoices(text);
  if (choices.length) return choices.map((c) => c.id + ") " + c.label).join(" · ");
  return display.replace(/\n/g, " · ");
}

function fleetGapReviewMode() {
  return S.filters.source_lang === "fleet-gap" && S.filters.target_lang === "fleet-gap";
}

function parseGapTitle(src) {
  const s = src || "";
  const m = s.match(/^Phase 1 gate · (G\d+(?:\s+\w+)?)\s*—\s*(.+)$/i);
  if (m) return { code: m[1].trim(), title: m[2].trim() };
  const g = s.match(/\b(G\d+)\b/);
  return { code: g ? g[1] : "—", title: s || "Decision" };
}

function parseGapReason(text) {
  const raw = text || "";
  const section = (name) => {
    const lines = raw.split("\n");
    let out = [];
    let inSec = false;
    for (const line of lines) {
      if (line.startsWith("## ")) {
        if (inSec) break;
        inSec = line.toLowerCase().includes(name.toLowerCase());
        continue;
      }
      if (inSec) out.push(line);
    }
    return out.join("\n").trim();
  };
  return {
    plain: section("plain terms") || section("what happened"),
    question: section("asking you") || section("the question"),
    loki: section("exact wording"),
  };
}

function fleetGapProgressPct() {
  const c = (S.state && S.state.summary) || {};
  const sealed = c.sealed ?? 0;
  const draft = c.draft ?? 0;
  const total = sealed + draft + (c.rejected || 0);
  if (!total) return 0;
  return Math.round((sealed / total) * 100);
}

function briefBand() {
  const pct = fleetGapProgressPct();
  const c = (S.state && S.state.summary) || {};
  const sealed = c.sealed ?? 0;
  const draft = c.draft ?? 0;
  const closed = draft === 0 && sealed > 0;
  const echoes = (S.gateEcho && S.gateEcho.entries) || [];
  const hanumanDone = echoes.filter((e) => e.dispatch_id && e.status === "complete").length;
  const hanumanTotal = echoes.filter((e) => e.dispatch_id).length;
  let title = closed
    ? "Witness complete — the fleet heard you"
    : "Phase 1 — your witness, not a ticket queue";
  if (closed && hanumanTotal && hanumanDone === hanumanTotal) {
    title = "Hanuman returned — " + hanumanDone + " builder closeout" + (hanumanDone === 1 ? "" : "s");
  }
  return h("div", { class: "brief-band" },
    h("span", { class: "eyebrow", text: closed ? "Gate sealed" : "Fleet gate" }),
    h("p", { class: "brief-title", text: title }),
    h("div", { class: "gate-progress" },
      h("span", { class: "track", title: sealed + " sealed, " + draft + " awaiting" },
        h("i", { style: "width:" + pct + "%" })),
      h("span", { text: sealed + " sealed · " + draft + " open" })));
}

function gateEchoForPair(p) {
  const g = parseGapTitle(p.source_text).code.split(/\s/)[0];
  const entries = (S.gateEcho && S.gateEcho.entries) || [];
  return entries.find((e) => e.gate === g) || null;
}

function fleetEchoBlock(echo) {
  if (!echo) return null;
  if (echo.note && !echo.dispatch_id) {
    return h("div", { class: "fleet-echo" },
      h("b", { text: "Still on you — " }),
      echo.note);
  }
  if (!echo.dispatch_id) return null;
  const done = echo.status === "complete";
  return h("div", { class: "fleet-echo" },
    h("div", {},
      h("b", { text: done ? "Hanuman · complete " : "Hanuman · " }),
      h("span", { class: "mono", text: echo.dispatch_id }),
      h("span", { class: "echo-pill" + (done ? "" : " wait"), text: done ? "returned" : "pending" })),
  done && echo.narrative ? h("p", { style: "margin:8px 0 0", text: echo.narrative }) : null,
  done && echo.written_at ? h("p", { class: "mono", style: "margin:6px 0 0", text: echo.written_at }) : null);
}

// Willow fleet-gap imports stash the Loki narrative in `reason` with file:// refs.
function renderContextBody(text) {
  const kids = [];
  for (const line of (text || "").split("\n")) {
    const t = line.trim();
    if (t.startsWith("file://")) {
      const label = t.slice(7);
      kids.push(h("div", {}, h("a", { href: t, target: "_blank", rel: "noopener noreferrer",
        class: "mono small" }, label)));
    } else {
      kids.push(h("div", { text: line }));
    }
  }
  return h("div", { class: "context-body" }, ...kids);
}

function contextDetails(reason, origin, { open } = {}) {
  if (!reason && !(origin || "").startsWith("willow:gap")) return null;
  return h("details", {
    class: "gap-context small",
    open: !!open,
    onclick: (e) => e.stopPropagation(),
  },
    h("summary", { text: "Background reading" }),
    renderContextBody(reason || "(Re-import with scripts/import_willow_gaps.py for plain-language context.)"));
}

function fleetGapCard(p) {
  const { code, title } = parseGapTitle(p.source_text);
  const { plain } = parseGapReason(p.reason);
  let teaser = (plain || "").split("\n").filter(Boolean)[0] || "";
  if (teaser.length > 200) teaser = teaser.slice(0, 197) + "…";
  const st = p.status === "sealed" ? "is-sealed" : (p.status === "draft" ? "is-draft" : "");
  const on = S.detail && S.detail.id === p.id;
  const codeShort = code.split(/\s/)[0];
  const kids = [
    h("div", { class: "decision-card-gutter" },
      h("span", { class: "gap-code", text: codeShort }),
      h("span", { class: "status-ribbon", text: p.status })),
    h("h3", { class: "decision-headline", text: title }),
  ];
  if (teaser) kids.push(h("p", { class: "decision-teaser", text: teaser }));
  if (p.status === "draft") kids.push(h("p", { class: "decision-cta", text: "Pick a path and seal →" }));
  else if (p.status === "sealed" && p.verifier) {
    kids.push(h("p", { class: "decision-byline", text: "Witnessed by " + p.verifier }));
  }
  const echo = gateEchoForPair(p);
  if (echo && echo.status === "complete") {
    kids.push(h("span", { class: "echo-pill", style: "margin-top:10px;display:inline-block", text: "hanuman ✓" }));
  }
  return h("article", {
    class: "decision-card " + st + (on ? " on" : ""),
    onclick: () => openPair(p.id),
  }, ...kids);
}

function pairRow(p) {
  if (fleetGapReviewMode()) return fleetGapCard(p);
  const compact = false;
  const row = h("div", {
    class: "pair" + (S.detail && S.detail.id === p.id ? " on" : ""),
    onclick: () => openPair(p.id),
  },
    h("div", { class: "texts" },
      mark(p.status),
      h("span", { class: "src", text: p.source_text }),
      h("span", { class: "arrow", text: "→" }),
      h("span", { text: commitmentSummary(p.target_text) })),
    h("div", { class: "row small muted", style: "margin-top:4px" },
      h("span", { class: "chip", text: p.status }),
      servableChip(p),
      p.verifier ? h("span", { class: "chip", text: "by " + p.verifier }) : h("span", { class: "chip", text: "no verifier" }),
      keyChip(p),
      h("span", { class: "chip", text: (p.source_lang || "?") + "→" + (p.target_lang || "?") })));
  if (!compact) {
    const ctx = contextDetails(p.reason, p.origin);
    if (ctx) row.append(ctx);
    const commit = commitmentPanel(p, { inline: true });
    if (commit) row.append(commit);
  }
  return row;
}

function commitmentPanel(p, { inline } = {}) {
  if (p.status !== "draft") return null;
  const { display, choices } = parseCommitmentChoices(p.target_text);
  if (!choices.length) return null;
  const pickKey = "commit-" + p.id;
  if (S.commitmentPickByPair[p.id] === undefined) {
    S.commitmentPickByPair[p.id] = choices[0].id;
  }
  const pick = S.commitmentPickByPair[p.id];
  const fleet = fleetGapReviewMode() && !inline;
  const opts = choices.map((c) => {
    const lblClass = fleet ? "choice-card" + (pick === c.id ? " is-selected" : "") : "commitment-opt small";
    return h("label", { class: lblClass,
      onclick: fleet ? (e) => { e.stopPropagation(); S.commitmentPickByPair[p.id] = c.id; render(); } : undefined },
      h("input", { type: "radio", name: pickKey, checked: pick === c.id,
        onchange: () => { S.commitmentPickByPair[p.id] = c.id; if (!inline) render(); } }),
      h("div", {},
        fleet
          ? h("div", {}, h("span", { class: "choice-letter", text: c.id }), " ", c.label)
          : h("div", {}, h("b", { text: c.id + ") " }), c.label),
        h("div", { class: "commitment-seal-preview mono", text: "If you seal: " + c.sealText })));
  });
  const body = h("div", {},
    fleet ? null : h("p", { class: "small muted", style: "margin:0 0 10px", text: display.split("\n")[0] }),
    ...opts,
    h("button", { class: "primary" + (fleet ? "" : " small"), style: fleet ? "margin-top:16px" : "margin-top:10px",
      disabled: S.state && S.state.read_only,
      onclick: (e) => { e.stopPropagation(); sealCommitment(p, p.id); } },
      fleet ? "Seal this witness" : "Seal this commitment"));
  if (inline) {
    return h("details", {
      class: "gap-context",
      open: true,
      onclick: (e) => e.stopPropagation(),
    }, h("summary", { text: "Three paths" }), body);
  }
  return h("div", { class: fleet ? "stage-choices" : "context-panel" },
    fleet ? null : h("h3", { style: "margin:0 0 6px;font-size:14px", text: "Your call" }),
    fleet ? h("p", { class: "stage-eyebrow", style: "margin:0 0 8px", text: "Three paths" }) : null,
    body);
}

async function sealCommitment(p, pairId) {
  if (!verifier()) return toast("Set who you are in the 'acting as' box first.", "err");
  const { choices } = parseCommitmentChoices(p.target_text);
  const letter = S.commitmentPickByPair[pairId || p.id] || choices[0]?.id;
  const pick = choices.find((c) => c.id === letter) || choices[0];
  if (!pick) return toast("No commitment options on this pair.", "err");
  const extra = await signSealFields(p.source_text, pick.sealText, p.source_lang, p.target_lang);
  if (!extra) return;
  const out = await sealWithOverride("/api/seal-draft",
    { pair_id: p.id, target: pick.sealText, ...extra },
    "Commitment sealed. If this is a fleet gap, willow should run apply_sealed_fleet_gaps.py.");
  if (out && out.pair) S.detail = out.pair;
  render();
}

async function openPair(id) {
  try { S.detail = (await api("/api/pair?id=" + encodeURIComponent(id))).pair; render(); }
  catch (e) { toast(e.message, "err"); }
}

function fleetDetailStage(p) {
  const { code, title } = parseGapTitle(p.source_text);
  const { plain, question } = parseGapReason(p.reason);
  const ro = S.state.read_only;
  const stage = h("div", { class: "stage-card" },
    h("div", { class: "stage-eyebrow", text: "Phase 1 gate · " + code.split(/\s/)[0] }),
    h("h2", { class: "stage-headline", text: title }));
  if (plain) stage.append(h("p", { class: "stage-lede", text: plain.split("\n").slice(0, 2).join(" ") }));
  if (question) stage.append(h("div", { class: "stage-question", text: question }));
  const commit = commitmentPanel(p);
  if (commit) stage.append(commit);
  else if (p.status === "sealed") {
    stage.append(h("div", { class: "sealed-verdict" },
      h("b", { text: "Your witness stands. " }),
      p.target_text));
  }
  const echo = gateEchoForPair(p);
  const echoEl = fleetEchoBlock(echo);
  if (echoEl) stage.append(echoEl);
  const prov = h("details", { class: "provenance-fold" },
    h("summary", { text: "Background & provenance" }),
    renderContextBody(p.reason),
    h("div", { class: "row", style: "margin-top:12px;flex-wrap:wrap" },
      h("span", { class: "chip", text: p.status }),
      servableChip(p),
      p.status === "sealed"
        ? h("span", { class: "chip", text: p.signature_valid ? "signature valid" : "signature invalid" })
        : null,
      h("span", { class: "chip", text: "by " + (p.verifier || "—") }),
      h("span", { class: "chip mono", text: (p.origin || "").slice(0, 24) }),
      h("span", { class: "chip mono", text: p.id.slice(0, 8) })),
    h("div", { class: "row", style: "margin-top:12px" },
      h("button", { class: "small", disabled: ro || p.status !== "sealed",
        onclick: () => unseal(p) }, "Unseal"),
      h("button", { class: "small danger", disabled: ro || p.status === "rejected",
        onclick: () => rejectPair(p) }, "Reject"),
      h("button", { class: "small", disabled: ro || p.status !== "rejected",
        onclick: () => restore(p) }, "Restore")));
  stage.append(prov);
  return stage;
}

function detailPanel() {
  const p = S.detail;
  if (!p) return h("div", { class: "card" });
  if (fleetGapReviewMode()) {
    return fleetDetailStage(p);
  }
  const card = h("div", { class: "card" });
  card.append(h("h2", { text: "Provenance" }));
  const ro = S.state.read_only;
  card.append(
    h("div", { class: "row" }, mark(p.status), h("b", { text: p.source_text })),
    h("div", { style: "margin:2px 0 10px" },
      h("span", { class: "muted", text: "→ " }),
      p.status === "draft" && parseCommitmentChoices(p.target_text).choices.length
        ? commitmentSummary(p.target_text)
        : p.target_text),
    commitmentPanel(p),
    (p.reason || (p.origin || "").startsWith("willow:gap"))
      ? h("div", { class: "context-panel small" }, renderContextBody(p.reason))
      : null,
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
      h("span", { class: "chip mono", title: p.created_at || "",
        text: relativeAge(p.created_at) || "—" }),
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
  const source = $("seal-source").value, target = $("seal-target").value;
  const extra = await signSealFields(source, target, tags.source_lang, tags.target_lang);
  if (!extra) return;
  const body = { source, target, ...tags, ...extra };
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
      /* Which matcher keys this domain, where the human deciding can see it.
         Two surfaces keyed differently used to describe themselves identically,
         and that is what let §6.40 sit unfound: nothing a person could read said
         which matcher was filing their seals. The field existed in /api/state
         for one release before anything rendered it, which is the same defect
         one layer up. */
      h("span", { class: "chip mono",
                  title: d.matcher_source === "app"
                    ? "this surface was given this domain's matcher"
                    : "the process-wide default — no matcher was given to this surface",
                  text: "matcher: " + d.matcher }),
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
      /* This surface may have been handed the matcher that keys its domain, in
         which case there is nothing to pick: a name cannot conjure a custom
         matcher, and scoring under a different one answers the only question
         Nestor is asked with a confidently wrong answer. Show which one is in
         force instead of a select, and send no `matcher` field at all — the API
         refuses a named one here, and it is this page's job not to ask. */
      d.matcher_source === "app"
        ? h("span", { class: "chip mono", title: "this surface was given its domain's matcher; it cannot score another",
                      text: d.matcher })
        : h("select", { id: "m-matcher" },
            ...[["string", "StringMatcher"], ["numeric", "NumericMatcher"],
                ["semantic", "SemanticMatcher (optional extra)"],
                ["ollama", "Ollama nomic-embed-text (local daemon)"]].map(([v, t]) =>
              h("option", { value: v, selected: (q.matcher || "string") === v }, t))),
      h("button", { class: "primary", disabled: S.state.read_only, onclick: submitMatch }, "Look up")),
    h("p", { class: "small muted", style: "margin:8px 0 0" },
      "No engine, no queue, no recipe — normalize, score against the sealed pairs in this domain, ",
      "and answer the only question Nestor answers: would this be served as verified?"));
}

async function submitMatch() {
  const text = $("m-text").value.trim();
  if (!text) return;
  const picker = $("m-matcher");
  const body = { text, source_lang: $("m-sl").value.trim(), target_lang: $("m-tl").value.trim(),
                 ...(picker ? { matcher: picker.value } : {}) };
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
                                      text: "verified by " + r.verifier }) : null,
    // WHY it would not be served. answer.match computes this, the CLI prints
    // it, and this panel — the surface a human actually reviews on — rendered
    // only "would not be served" and left the reader to guess between "nothing
    // matched", "nothing is sealed" and "a signature does not verify". A
    // review surface that withholds its own reason is the defect this field
    // was added to close; it was closed everywhere except here.
    !r.served && r.reason ? h("p", { class: "small", style: "margin:8px 0 2px",
                                     text: r.reason }) : null);
  card.append(candidates(r.matches, r.threshold, "source", "target",
    (m) => rejectMatch(r.query, m), r.reason));
  return card;
}

/* --- shared: candidates, sealing, rejecting ------------------------------- */
function candidates(rows, threshold, leftLabel, rightLabel, onReject, reason) {
  // The empty case used to assert "No candidate scored high enough" — which is
  // false whenever the list is empty because every candidate was REJECTED, or
  // because the domain holds nothing at all. Say only what is true, and let
  // the reason above carry the explanation.
  const box = h("div", {}, h("p", { class: "small muted", style: "margin:14px 0 4px",
    text: rows.length ? "Ranked candidates. A sealed one serves only at or above " + threshold + "."
                      : (reason ? "No candidates to show — see above."
                                : "No candidates to show.") }));
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
  const extra = await signSealFields(r.query.text, target, r.query.source_lang, r.query.target_lang);
  if (!extra) return;
  await sealWithOverride("/api/seal",
    { source: r.query.text, target, source_lang: r.query.source_lang,
      target_lang: r.query.target_lang, origin: "ui:ask", ...extra },
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
  const l = S.ledger || { entries: [], kinds: [], ok: true, detail: "", unreadable: [] };
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

  // A line that will not parse has no kind and no timestamp, so it cannot
  // appear in the table below and cannot be filtered for. Say how many and
  // where, or the table is a shorter chain than the file with nothing marking
  // the difference.
  const torn = l.unreadable || [];
  if (torn.length) {
    $("view").append(h("div", { class: "card" },
      h("p", { class: "small", style: "margin:0",
        text: torn.length + " line(s) on disk are not valid JSON, so they are not in "
          + "the table below: line " + torn.slice(0, 10).map((u) => u.line).join(", ")
          + (torn.length > 10 ? ", +" + (torn.length - 10) + " more" : "") + "." })));
  }

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
  document.body.classList.toggle("shell-memory", S.tab === "memory");
  document.body.classList.toggle("fleet-review", S.tab === "memory" && fleetGapReviewMode());
  const c = (S.state && S.state.summary) || {};
  document.body.classList.toggle("gate-closed",
    S.tab === "memory" && fleetGapReviewMode() && (c.draft ?? 0) === 0 && (c.sealed ?? 0) > 0);
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
    // Fleet-gap review opens on Memory, not Queue (segments are empty for SOIL imports).
    if (!S._tabBootstrapped) {
      S._tabBootstrapped = true;
      const d = S.state.domain || {};
      if (d.source_lang === "fleet-gap" && d.target_lang === "fleet-gap") {
        S.tab = "memory";
        S.filters.source_lang = "fleet-gap";
        S.filters.target_lang = "fleet-gap";
      }
    }
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
      if (fleetGapReviewMode()) {
        try { S.gateEcho = await api("/api/gate-echo"); }
        catch (_e) { S.gateEcho = null; }
      }
      const rows = (await api("/api/pairs?" + q.toString())).pairs;
      S.more = rows.length > PAGE;
      S.pairs = rows.slice(0, PAGE);
      if (S.tab === "memory" && S.pairs.length && !S.detail) {
        try {
          S.detail = (await api("/api/pair?id=" + encodeURIComponent(S.pairs[0].id))).pair;
        } catch (_e) { /* non-fatal */ }
      }
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
