/**
 * Unit tests for nestor/ui_pure.js — the pure functions extracted from the
 * nestor ui page so they can run under Node.js without a browser.
 *
 * Run:  node --test tests/js/test_ui_pure.js
 *
 * Uses Node's built-in test runner (stable since v20) — no npm install, no
 * devDependencies, no package.json needed.
 */
"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const P = require(path.resolve(__dirname, "../../nestor/ui_pure.js"));

// ---------------------------------------------------------------------------
// relativeAge
// ---------------------------------------------------------------------------
describe("relativeAge", () => {
  it("returns empty string for falsy input", () => {
    assert.equal(P.relativeAge(""), "");
    assert.equal(P.relativeAge(null), "");
    assert.equal(P.relativeAge(undefined), "");
  });

  it("returns the input for unparseable dates", () => {
    assert.equal(P.relativeAge("not-a-date"), "not-a-date");
  });

  it("returns 'just now' for timestamps less than 60s ago", () => {
    const recent = new Date(Date.now() - 10_000).toISOString();
    assert.equal(P.relativeAge(recent), "just now");
  });

  it("returns minutes for timestamps 1-59 minutes ago", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60_000).toISOString();
    assert.equal(P.relativeAge(fiveMinAgo), "5m ago");
  });

  it("returns hours for timestamps 1-47 hours ago", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000).toISOString();
    assert.equal(P.relativeAge(threeHoursAgo), "3h ago");
  });

  it("returns days for timestamps 2-13 days ago", () => {
    const fiveDaysAgo = new Date(Date.now() - 5 * 86_400_000).toISOString();
    assert.equal(P.relativeAge(fiveDaysAgo), "5d ago");
  });

  it("returns ISO date prefix for timestamps >= 14 days ago", () => {
    const old = new Date(Date.now() - 30 * 86_400_000).toISOString();
    // Should return the first 10 characters (YYYY-MM-DD)
    assert.equal(P.relativeAge(old), old.slice(0, 10));
  });
});

// ---------------------------------------------------------------------------
// hex / hexToBytes round-trip
// ---------------------------------------------------------------------------
describe("hex", () => {
  it("encodes an empty buffer", () => {
    assert.equal(P.hex(new Uint8Array([]).buffer), "");
  });

  it("encodes known bytes", () => {
    assert.equal(P.hex(new Uint8Array([0xde, 0xad, 0xbe, 0xef]).buffer), "deadbeef");
  });

  it("zero-pads single-digit bytes", () => {
    assert.equal(P.hex(new Uint8Array([0x00, 0x01, 0x0f]).buffer), "00010f");
  });
});

describe("hexToBytes", () => {
  it("decodes known hex", () => {
    const out = P.hexToBytes("deadbeef");
    assert.deepEqual(Array.from(out), [0xde, 0xad, 0xbe, 0xef]);
  });

  it("handles whitespace", () => {
    const out = P.hexToBytes("  de ad  ");
    assert.deepEqual(Array.from(out), [0xde, 0xad]);
  });

  it("throws on odd-length hex", () => {
    assert.throws(() => P.hexToBytes("abc"), /even number of digits/);
  });

  it("throws on non-hex characters", () => {
    assert.throws(() => P.hexToBytes("xyz0"), /expected hex/);
  });

  it("round-trips with hex()", () => {
    const original = new Uint8Array([0, 127, 128, 255]);
    const roundTripped = P.hexToBytes(P.hex(original.buffer));
    assert.deepEqual(Array.from(roundTripped), Array.from(original));
  });
});

// ---------------------------------------------------------------------------
// hasLoneSurrogate
// ---------------------------------------------------------------------------
describe("hasLoneSurrogate", () => {
  it("returns false for plain ASCII", () => {
    assert.equal(P.hasLoneSurrogate("hello"), false);
  });

  it("returns false for a paired surrogate (emoji)", () => {
    // U+1F600 (grinning face) — a surrogate pair in UTF-16
    assert.equal(P.hasLoneSurrogate("😀"), false);
  });

  it("returns true for a lone high surrogate", () => {
    assert.equal(P.hasLoneSurrogate("a\uD800b"), true);
  });

  it("returns true for a lone low surrogate", () => {
    assert.equal(P.hasLoneSurrogate("a\uDC00b"), true);
  });

  it("returns false for empty string", () => {
    assert.equal(P.hasLoneSurrogate(""), false);
  });
});

// ---------------------------------------------------------------------------
// pyJsonString — must match CPython json.dumps(s, ensure_ascii=False)
// ---------------------------------------------------------------------------
describe("pyJsonString", () => {
  it("encodes a plain string", () => {
    assert.equal(P.pyJsonString("hello"), '"hello"');
  });

  it("escapes double quotes", () => {
    assert.equal(P.pyJsonString('say "hi"'), '"say \\"hi\\""');
  });

  it("escapes backslashes", () => {
    assert.equal(P.pyJsonString("a\\b"), '"a\\\\b"');
  });

  it("escapes control characters with named escapes", () => {
    assert.equal(P.pyJsonString("\b"), '"\\b"');
    assert.equal(P.pyJsonString("\t"), '"\\t"');
    assert.equal(P.pyJsonString("\n"), '"\\n"');
    assert.equal(P.pyJsonString("\f"), '"\\f"');
    assert.equal(P.pyJsonString("\r"), '"\\r"');
  });

  it("escapes other control characters with \\u00XX", () => {
    assert.equal(P.pyJsonString("\x01"), '"\\u0001"');
    assert.equal(P.pyJsonString("\x1f"), '"\\u001f"');
  });

  it("passes non-ASCII through unescaped (ensure_ascii=False)", () => {
    assert.equal(P.pyJsonString("é"), '"é"');     // e-acute
    assert.equal(P.pyJsonString(" "), '" "');     // line separator
  });

  it("passes emoji through unescaped", () => {
    assert.equal(P.pyJsonString("😀"), '"😀"');
  });

  // The hardcoded vector from test_client_signed_seals.py
  it("matches the frozen Python wire-contract vector", () => {
    // Python: json.dumps('café "quote"', separators=(",",":"), ensure_ascii=False)
    //       = '"café \\"quote\\""'
    assert.equal(P.pyJsonString('café "quote"'), '"café \\"quote\\""');
  });
});

describe("pyJsonArray", () => {
  it("encodes an array of strings", () => {
    assert.equal(P.pyJsonArray(["a", "b"]), '["a","b"]');
  });

  it("encodes a single-element array", () => {
    assert.equal(P.pyJsonArray(["hello"]), '["hello"]');
  });
});

// ---------------------------------------------------------------------------
// frozenMessageBytes — the seal message that must match signing._message
// ---------------------------------------------------------------------------
describe("frozenMessageBytes", () => {
  it("produces a Uint8Array", () => {
    const out = P.frozenMessageBytes("norm", "target", "verifier");
    assert.ok(out instanceof Uint8Array);
  });

  it("matches the expected JSON encoding", () => {
    const out = P.frozenMessageBytes("hello", "world", "alice");
    const expected = new TextEncoder().encode('["hello","world","alice"]');
    assert.deepEqual(Array.from(out), Array.from(expected));
  });

  it("handles non-ASCII correctly", () => {
    const out = P.frozenMessageBytes("café", "thé", "bob");
    const expected = new TextEncoder().encode('["café","thé","bob"]');
    assert.deepEqual(Array.from(out), Array.from(expected));
  });

  it("throws on lone surrogates", () => {
    assert.throws(
      () => P.frozenMessageBytes("a\uD800b", "target", "v"),
      /unpaired UTF-16 surrogate/
    );
  });
});

// ---------------------------------------------------------------------------
// STATE_MOOD
// ---------------------------------------------------------------------------
describe("STATE_MOOD", () => {
  it("maps sealed to pleased", () => {
    assert.equal(P.STATE_MOOD.sealed, "pleased");
  });
  it("maps draft to unconvinced", () => {
    assert.equal(P.STATE_MOOD.draft, "unconvinced");
  });
  it("maps rejected to unconvinced", () => {
    assert.equal(P.STATE_MOOD.rejected, "unconvinced");
  });
  it("maps pending to idle", () => {
    assert.equal(P.STATE_MOOD.pending, "idle");
  });
});

// ---------------------------------------------------------------------------
// askMood — recipe-specific mood from an Ask-tab result
// ---------------------------------------------------------------------------
describe("askMood", () => {
  // -- forged-seal alarm (across all recipes) --
  it("returns alert when a match is sealed but not servable", () => {
    const result = {
      recipe: "translate",
      matches: [{ status: "sealed", servable: false }],
    };
    assert.equal(P.askMood(result), "alert");
  });

  it("ignores matches that are servable", () => {
    const result = {
      recipe: "translate",
      matches: [{ status: "sealed", servable: true }],
      passage: { state: "sealed" },
    };
    assert.equal(P.askMood(result), "pleased");
  });

  // -- translate / match --
  it("translate: pleased when passage is sealed", () => {
    assert.equal(
      P.askMood({ recipe: "translate", passage: { state: "sealed" } }),
      "pleased"
    );
  });

  it("translate: unconvinced when passage is draft", () => {
    assert.equal(
      P.askMood({ recipe: "translate", passage: { state: "draft" } }),
      "unconvinced"
    );
  });

  it("translate: idle when nothing is served", () => {
    assert.equal(
      P.askMood({ recipe: "translate", served: false }),
      "idle"
    );
  });

  it("translate: pleased when served is true and no passage", () => {
    assert.equal(
      P.askMood({ recipe: "translate", served: true }),
      "pleased"
    );
  });

  // -- entity --
  it("entity: pleased when sealed", () => {
    assert.equal(
      P.askMood({ recipe: "entity", sealed: true }),
      "pleased"
    );
  });

  it("entity: unconvinced when not sealed but has a suggestion", () => {
    assert.equal(
      P.askMood({
        recipe: "entity",
        sealed: false,
        provenance: { suggestion: "something" },
      }),
      "unconvinced"
    );
  });

  it("entity: idle when not sealed and no suggestion", () => {
    assert.equal(
      P.askMood({ recipe: "entity", sealed: false }),
      "idle"
    );
  });

  // -- numeric --
  it("numeric: idle when no baseline", () => {
    assert.equal(
      P.askMood({ recipe: "numeric", baseline: null }),
      "idle"
    );
  });

  it("numeric: pleased when within tolerance", () => {
    assert.equal(
      P.askMood({ recipe: "numeric", baseline: 42, within_tolerance: true }),
      "pleased"
    );
  });

  it("numeric: unconvinced when outside tolerance", () => {
    assert.equal(
      P.askMood({ recipe: "numeric", baseline: 42, within_tolerance: false }),
      "unconvinced"
    );
  });
});

// ---------------------------------------------------------------------------
// moodFromState — the top-level mood dispatcher
// ---------------------------------------------------------------------------
describe("moodFromState", () => {
  it("returns idle when tab is not ask or memory", () => {
    assert.equal(P.moodFromState("queue", null, null), "idle");
    assert.equal(P.moodFromState("welcome", null, null), "idle");
    assert.equal(P.moodFromState("signals", null, null), "idle");
  });

  it("returns idle on ask tab with no result", () => {
    assert.equal(P.moodFromState("ask", null, null), "idle");
  });

  it("delegates to askMood on ask tab with a result", () => {
    const result = { recipe: "translate", passage: { state: "sealed" } };
    assert.equal(P.moodFromState("ask", result, null), "pleased");
  });

  it("returns idle on memory tab with no detail", () => {
    assert.equal(P.moodFromState("memory", null, null), "idle");
  });

  it("returns alert when memory detail is sealed with invalid signature", () => {
    const detail = { status: "sealed", signature_valid: false };
    assert.equal(P.moodFromState("memory", null, detail), "alert");
  });

  it("returns pleased when memory detail is sealed with valid signature", () => {
    const detail = { status: "sealed", signature_valid: true };
    assert.equal(P.moodFromState("memory", null, detail), "pleased");
  });

  it("returns pleased when memory detail is sealed with no sig check", () => {
    const detail = { status: "sealed" };
    assert.equal(P.moodFromState("memory", null, detail), "pleased");
  });

  it("returns unconvinced when memory detail is draft", () => {
    const detail = { status: "draft" };
    assert.equal(P.moodFromState("memory", null, detail), "unconvinced");
  });

  it("returns unconvinced when memory detail is rejected", () => {
    const detail = { status: "rejected" };
    assert.equal(P.moodFromState("memory", null, detail), "unconvinced");
  });

  it("returns idle when memory detail has pending status", () => {
    const detail = { status: "pending" };
    assert.equal(P.moodFromState("memory", null, detail), "idle");
  });
});

// ---------------------------------------------------------------------------
// mdInline / mdBlocks — the little markdown a `reason` actually carries
//
// Scope was measured, not guessed: across 2,796 rows of one box's stores, 851
// carry `code` and 163 carry **bold**; links, bullets, headings and fences are
// single figures, and italics, block quotes and ordered lists never appear.
// These tests pin what is supported and, as importantly, that everything else
// survives as plain text rather than being mangled by a half-implementation.
// ---------------------------------------------------------------------------

describe("mdInline", () => {
  it("splits code, bold and links out of the surrounding text", () => {
    const t = P.mdInline("set `--db` and **seal** it, see [docs](http://x/y)");
    assert.deepEqual(t.map((x) => x.type),
      ["text", "code", "text", "strong", "text", "link"]);
    assert.equal(t[1].text, "--db");
    assert.equal(t[3].text, "seal");
    assert.equal(t[5].text, "docs");
    assert.equal(t[5].href, "http://x/y");
  });

  it("returns one text token for a line with no markup", () => {
    assert.deepEqual(P.mdInline("merged 2026-08-18 by Sean Campbell"),
      [{ type: "text", text: "merged 2026-08-18 by Sean Campbell" }]);
  });

  it("never returns markup — only tokens the caller renders as text", () => {
    // A reason is data. If it could produce markup, a row could script the page.
    const t = P.mdInline("<script>alert(1)</script> and `<b>x</b>`");
    assert.equal(t[0].type, "text");
    assert.ok(t[0].text.includes("<script>"), "kept verbatim as text");
    assert.equal(t.find((x) => x.type === "code").text, "<b>x</b>");
  });

  it("leaves an unmatched marker alone rather than eating the rest of the line", () => {
    assert.deepEqual(P.mdInline("a ** dangling marker"),
      [{ type: "text", text: "a ** dangling marker" }]);
  });
});

describe("mdBlocks", () => {
  it("groups headings, bullets and paragraphs", () => {
    const b = P.mdBlocks("## Why\n\n- one\n- two\n\nbecause.");
    assert.deepEqual(b.map((x) => x.type), ["h", "li", "li", "p"]);
    assert.equal(b[0].level, 2);
    assert.equal(b[1].text, "one");
    assert.deepEqual(b[3].lines, ["because."]);
  });

  it("does not interpret markdown inside a fence", () => {
    const b = P.mdBlocks("```\nraw **not** bold\n```");
    assert.equal(b.length, 1);
    assert.equal(b[0].type, "pre");
    assert.equal(b[0].text, "raw **not** bold");
  });

  it("closes an unterminated fence rather than dropping its contents", () => {
    const b = P.mdBlocks("```\nstill worth showing");
    assert.equal(b[0].type, "pre");
    assert.equal(b[0].text, "still worth showing");
  });

  it("collects a paragraph's lines for mdParagraph to join", () => {
    const b = P.mdBlocks("merged 2026-08-18\nPR #157 · branch fix/x");
    assert.equal(b.length, 1);
    assert.deepEqual(b[0].lines, ["merged 2026-08-18", "PR #157 · branch fix/x"]);
  });

  it("keeps the file:// convention the gap importer writes", () => {
    const b = P.mdBlocks("file:///home/x/notes.md");
    assert.equal(b[0].type, "path");
    assert.equal(b[0].text, "/home/x/notes.md");
  });

  it("treats an empty or absent reason as no blocks at all", () => {
    assert.deepEqual(P.mdBlocks(""), []);
    assert.deepEqual(P.mdBlocks(null), []);
  });
});


describe("mdParagraph", () => {
  it("joins soft-wrapped lines instead of breaking them again", () => {
    // The defect this exists for, seen on screen: a reason hard-wrapped at ~72
    // columns and re-broken at every newline wraps twice and shreds — two words
    // on a line, then a long one, then two more. An earlier version of this
    // renderer kept every break, on the theory that reasons are stacks of short
    // facts. Some are; the prose ones are not, and those are the readable ones.
    const wrapped = ["This commit was written for #154 and did not land",
                     "with it. The merge took f7a6e06 plus a merge commit;",
                     "the follow-up push arrived after the merge had"];
    const out = P.mdParagraph(wrapped);
    assert.equal(out.length, 1, "one paragraph, not three lines");
    assert.ok(out[0].startsWith("This commit was written for #154 and did not land with it."));
  });

  it("keeps a break the author asked for with two trailing spaces", () => {
    assert.deepEqual(P.mdParagraph(["merged 2026-08-18  ", "PR #157 · branch fix/x"]),
      ["merged 2026-08-18", "PR #157 · branch fix/x"]);
  });

  it("drops empty runs rather than emitting blank paragraphs", () => {
    assert.deepEqual(P.mdParagraph(["   ", ""]), []);
  });
});

describe("mdPlain", () => {
  it("takes the markers off a list row instead of rendering them", () => {
    assert.equal(P.mdPlain("**This commit was written for #154.** The merge"),
      "This commit was written for #154. The merge");
    assert.equal(P.mdPlain("## Summary"), "Summary");
    assert.equal(P.mdPlain("run the suite on `master`"), "run the suite on master");
  });

  it("flattens a row to one line so it cannot break the scan", () => {
    assert.equal(P.mdPlain("first line\nsecond   line"), "first line second line");
  });

  it("drops a fenced block rather than dumping code into a row", () => {
    assert.equal(P.mdPlain("before ```\nraw\n``` after"), "before after");
  });
});

describe("parseGitOrigin", () => {
  it("turns an origin into the places a reader would go", () => {
    const g = P.parseGitOrigin("rudi193-cmd/Nestor@c68b8be:PR #41");
    assert.equal(g.prUrl, "https://github.com/rudi193-cmd/Nestor/pull/41");
    assert.equal(g.commitUrl, "https://github.com/rudi193-cmd/Nestor/commit/c68b8be");
    assert.equal(g.repoUrl, "https://github.com/rudi193-cmd/Nestor");
    assert.equal(g.showCmd, "git -C Nestor show c68b8be");
  });

  it("handles a merge with no pull request", () => {
    const g = P.parseGitOrigin("owner/repo@abc1234");
    assert.equal(g.prUrl, "", "no PR, no PR link");
    assert.equal(g.commitUrl, "https://github.com/owner/repo/commit/abc1234");
  });

  it("returns null rather than guessing at an origin of another shape", () => {
    // A wrong link into somebody's repository is worse than no link.
    for (const bad of ["ui:seal-draft", "willow:gap#12", "", null,
                       "not/a/thing@nothex:PR #1", "owner/repo@c68b8be:MR !41"]) {
      assert.equal(P.parseGitOrigin(bad), null, JSON.stringify(bad));
    }
  });
});
