/**
 * Pure functions shared between the ``nestor ui`` served page and the
 * Node.js unit-test suite.
 *
 * In the browser (inlined by ``ui_page.py`` ahead of the main ``<script>``
 * block), these become globals — exactly as they were when they lived inline.
 * Under Node.js (``require("./ui_pure.js")``), the ``module.exports`` block
 * at the bottom makes them importable without a DOM.
 *
 * Rule: nothing in this file may reference ``document``, ``window``, or any
 * other browser-only global.  If a function needs the DOM it stays in the
 * inline block inside ``ui_page.py``.
 */
"use strict";

/* ---------- relative age -------------------------------------------------- */

function relativeAge(iso) {
  if (!iso) return "";
  var t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  var sec = Math.floor((Date.now() - t) / 1000);
  if (sec < 60) return "just now";
  var min = Math.floor(sec / 60);
  if (min < 60) return min + "m ago";
  var hr = Math.floor(min / 60);
  if (hr < 48) return hr + "h ago";
  var day = Math.floor(hr / 24);
  if (day < 14) return day + "d ago";
  return iso.slice(0, 10);
}

/* ---------- hex encoding -------------------------------------------------- */

function hex(buf) {
  return Array.from(new Uint8Array(buf)).map(function (b) { return b.toString(16).padStart(2, "0"); }).join("");
}
function hexToBytes(s) {
  var clean = (s || "").trim().replace(/\s+/g, "");
  if (!/^[0-9a-fA-F]*$/.test(clean) || clean.length % 2 !== 0) {
    throw new Error("expected hex (0-9, a-f, A-F), an even number of digits");
  }
  var out = new Uint8Array(clean.length / 2);
  for (var i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
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
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) {                 // high surrogate
      var next = s.charCodeAt(i + 1);
      if (Number.isNaN(next) || next < 0xdc00 || next > 0xdfff) return true;
      i++;                                            // paired — skip the low half
    } else if (c >= 0xdc00 && c <= 0xdfff) {           // unpaired low surrogate
      return true;
    }
  }
  return false;
}

function pyJsonString(s) {
  var out = '"';
  for (var ch of s) {          // iterates by CODE POINT (keeps a surrogate
                                // pair together), matching Python's str
    var cp = ch.codePointAt(0);
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
  var fields = [["the normalized source", sourceNorm], ["the target text", targetText],
                ["the verifier name", verifierName]];
  for (var pair of fields) {
    if (hasLoneSurrogate(pair[1])) {
      throw new Error(pair[0] + " contains an unpaired UTF-16 surrogate. The frozen signing " +
        "contract cannot represent that the same way in Python and in the browser (Python " +
        "refuses to encode it at all) — remove or replace that character before sealing.");
    }
  }
  return new TextEncoder().encode(pyJsonArray([sourceNorm, targetText, verifierName]));
}

/* ---------- mood (the face's expression is a function of the verdict) ------ */

// Nestor's expression is a function of the verdict on screen, never decoration:
// he settles when a person vouched, is unconvinced by his own draft or a figure
// that will not reconcile, stays politely blank when there is simply nothing to
// serve, and alarms only at a seal whose signature does not check out.
// Recomputed each render, so the face can never disagree with the card it sits
// above — which is why it derives each recipe's state exactly as that recipe's
// result renderer does (translateResult / entityResult / numericResult), rather
// than second-guessing from `verified` (which for numeric means only "a baseline
// exists," not "the figure is within tolerance").
var STATE_MOOD = { sealed: "pleased", draft: "unconvinced", rejected: "unconvinced", pending: "idle" };

function askMood(r) {
  // A forged seal — a candidate that says sealed but would not serve — is the
  // one alarming case, and the only one worth interrupting a calm face for. A
  // plain "nothing matched" is a refusal, not an alarm.
  if ((r.matches || []).some(function (m) { return m && m.status === "sealed" && m.servable === false; })) return "alert";
  var state;
  if (r.recipe === "entity") {
    state = r.sealed ? "sealed" : (r.provenance && r.provenance.suggestion ? "draft" : "pending");
  } else if (r.recipe === "numeric") {
    state = r.baseline == null ? "pending" : (r.within_tolerance ? "sealed" : "rejected");
  } else {  // translate, match
    state = (r.passage && r.passage.state) || (r.served ? "sealed" : "pending");
  }
  return STATE_MOOD[state] || "idle";
}

function moodFromState(tab, result, detail) {
  if (tab === "ask" && result) return askMood(result);
  if (tab === "memory" && detail) {
    var d = detail;
    if (d.status === "sealed" && d.signature_valid === false) return "alert";
    if (d.status === "sealed") return "pleased";
    if (d.status === "draft" || d.status === "rejected") return "unconvinced";
  }
  return "idle";
}

/* ---------- module boundary ------------------------------------------------ */

/* ---------- the little markdown in a `reason` ----------------------------- */

/**
 * Split a line into inline runs: plain text, `code`, **bold**, [label](href).
 *
 * Returns tokens, never markup. The caller builds nodes and sets `.text`, so a
 * reason containing `<script>` is text in the document and nothing else — the
 * whole point of parsing to tokens rather than to a string of HTML.
 *
 * Scope was measured rather than assumed: across 2,796 rows of this box's
 * stores, 851 carry `code` and 163 carry **bold**; links, bullets, headings and
 * fences appear in single figures, and italics, block quotes and ordered lists
 * never appear at all. Supporting the whole of CommonMark here would be code
 * nothing in the corpus exercises.
 */
function mdInline(line) {
  var out = [];
  var rx = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g;
  var at = 0, m;
  while ((m = rx.exec(line)) !== null) {
    if (m.index > at) out.push({ type: "text", text: line.slice(at, m.index) });
    if (m[1] !== undefined) out.push({ type: "code", text: m[1] });
    else if (m[2] !== undefined) out.push({ type: "strong", text: m[2] });
    else out.push({ type: "link", text: m[3], href: m[4] });
    at = m.index + m[0].length;
  }
  if (at < line.length) out.push({ type: "text", text: line.slice(at) });
  return out.length ? out : [{ type: "text", text: line }];
}

/**
 * Group a reason into blocks: fenced code, headings, bullets, paragraphs.
 *
 * A blank line ends a paragraph; inside a fence nothing is interpreted, which
 * is what makes a fence worth having. `file://` lines keep the behaviour they
 * already had — the local-path link the gap importer writes — because that is
 * a Nestor convention rather than a markdown one.
 */
function mdBlocks(text) {
  var lines = String(text == null ? "" : text).split("\n");
  var blocks = [], para = [], fence = null;

  function flush() {
    if (para.length) { blocks.push({ type: "p", lines: para.slice() }); para.length = 0; }
  }
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i], t = line.trim();
    if (fence !== null) {
      if (t.slice(0, 3) === "```") { blocks.push({ type: "pre", text: fence.join("\n") }); fence = null; }
      else fence.push(line);
      continue;
    }
    if (t.slice(0, 3) === "```") { flush(); fence = []; continue; }
    if (t === "") { flush(); continue; }
    if (t.slice(0, 7) === "file://") { flush(); blocks.push({ type: "path", text: t.slice(7), href: t }); continue; }
    var head = /^(#{1,6})\s+(.*)$/.exec(t);
    if (head) { flush(); blocks.push({ type: "h", level: head[1].length, text: head[2] }); continue; }
    var bullet = /^[-*]\s+(.*)$/.exec(t);
    if (bullet) { flush(); blocks.push({ type: "li", text: bullet[1] }); continue; }
    para.push(line);
  }
  if (fence !== null && fence.length) blocks.push({ type: "pre", text: fence.join("\n") });
  flush();
  return blocks;
}

/**
 * Join a paragraph's soft-wrapped lines the way markdown does.
 *
 * A `reason` written by a person is hard-wrapped at about 72 columns. Rendering
 * each of those lines as its own break wraps the text twice — once at the
 * author's column and again at the panel's — and the result is shredded: two or
 * three words on a line, then a long one, then two more. An earlier version of
 * this did exactly that on the theory that reasons are stacks of short facts.
 * Some are; the prose ones are not, and they are the ones worth reading.
 *
 * So a single newline is a soft wrap and joins with a space, and a blank line
 * separates paragraphs — markdown's own rule. A line ending in two spaces keeps
 * its break, which is markdown's way of asking for one explicitly.
 */
function mdParagraph(lines) {
  var out = [], run = [];
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    var hard = /\s{2,}$/.test(line);
    run.push(line.trim());
    if (hard || i === lines.length - 1) { out.push(run.join(" ")); run = []; }
  }
  if (run.length) out.push(run.join(" "));
  return out.filter(function (x) { return x !== ""; });
}

/**
 * A one-line preview with the markdown taken off rather than rendered.
 *
 * A list row is scanned, not read: it wants the words, on one line, at one
 * weight. Leaving the markers in put `**` and backticks on screen; rendering
 * them properly would give a scan-line bold runs and code chips competing with
 * the row's own status marks. Both are worse than plain text here — so the
 * markers come off and the text stays whole.
 */
function mdPlain(text) {
  var flat = String(text == null ? "" : text)
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "");
  return mdInline(flat).map(function (t) { return t.text; }).join("")
    .replace(/\s+/g, " ").trim();
}

/* ---------- an origin, as places you can actually go ---------------------- */

/** Where a `owner/repo@sha:PR #n` origin lives. See parseGitOrigin on why this
 *  is an assumption and where it would have to move to stop being one. This is
 *  a link target the reader chooses to follow — never a resource the page
 *  fetches, which the CSP forbids outright (`default-src 'none'`). */
var FORGE_BASE = "https://" + "github.com/";

/**
 * Take `owner/repo@sha:PR #41` apart into the things a reader wants to open.
 *
 * The origin already carries everything needed to go and read the change — the
 * repository, the commit, the pull request — and it was being rendered as one
 * grey chip of text you could not click. Somebody working through a queue hits a
 * decision they want to think harder about, and the evidence for it is one
 * unclickable string away.
 *
 * Returns `null` for an origin of any other shape (`ui:seal-draft`,
 * `willow:gap…`, a corpus stamp) rather than guessing: a wrong link into
 * somebody's repository is worse than no link.
 */
function parseGitOrigin(origin) {
  var m = /^([A-Za-z0-9._-]+)\/([A-Za-z0-9._-]+)@([0-9a-f]{7,40})(?::PR #(\d+))?$/
    .exec(String(origin == null ? "" : origin).trim());
  if (!m) return null;
  var owner = m[1], repo = m[2], sha = m[3], pr = m[4] || "";
  // The origin records `owner/repo`, never a host — so the host is an
  // assumption, and it is named here rather than buried in a template. It holds
  // for every remote this corpus was built from, and `PR #` is GitHub's own
  // vocabulary (GitLab would say merge request), so a row shaped like this came
  // from GitHub. A forge that is not GitHub needs FORGE_BASE to become a value
  // the store carries, not a wider regex here.
  var base = FORGE_BASE + owner + "/" + repo;
  return {
    owner: owner, repo: repo, sha: sha, pr: pr,
    repoUrl: base,
    commitUrl: base + "/commit/" + sha,
    prUrl: pr ? base + "/pull/" + pr : "",
    // Read it without leaving the machine — the clone is right there, and this
    // works whether or not the network does.
    showCmd: "git -C " + repo + " show " + sha,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    relativeAge: relativeAge,
    hex: hex,
    hexToBytes: hexToBytes,
    hasLoneSurrogate: hasLoneSurrogate,
    pyJsonString: pyJsonString,
    pyJsonArray: pyJsonArray,
    frozenMessageBytes: frozenMessageBytes,
    STATE_MOOD: STATE_MOOD,
    askMood: askMood,
    moodFromState: moodFromState,
    mdInline: mdInline,
    mdBlocks: mdBlocks,
    mdParagraph: mdParagraph,
    mdPlain: mdPlain,
    parseGitOrigin: parseGitOrigin,
  };
}
