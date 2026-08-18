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
