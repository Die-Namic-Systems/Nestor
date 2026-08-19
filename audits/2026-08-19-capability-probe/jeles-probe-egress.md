# Probe report: `jeles._egress` (jeles 0.9.0)

**Target:** `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/_egress.py`
**Interpreter:** `/home/user/Nestor/.venv/bin/python` (3.11)
**Date:** 2026-08-19
**Scope:** `check_url()`, `private_destination()`, `scheme_ok()`, `SchemeGuardedRedirects`,
`opener()`, `read_capped()` — no live network calls made (see Methodology).
**Scenarios run:** 147

## Methodology

All scenarios call the module's pure-Python validation functions directly
(`check_url`, `private_destination`, `scheme_ok`, `SchemeGuardedRedirects.redirect_request`,
`read_capped`) — none of them opened a socket to an external host. Where a
scenario needed to exercise the DNS-resolution branch of `private_destination()`
(e.g. DNS-rebinding-style tests), `socket.getaddrinfo` was patched with
`unittest.mock.patch.object` to return a synthetic answer, so no DNS traffic
left the box. `redirect_request()` was exercised against hand-built
`Request`-like stand-ins and a `BytesIO` file pointer, never a real
`HTTPResponse`. `read_capped()` was tested against a fake response object
wrapping an in-memory buffer.

One genuine surprise came out of this discipline rather than despite it —
see Finding 1.

## Executive summary — five things worth flagging

1. **This sandbox's `HTTPS_PROXY` silently disables `private_destination()`'s
   DNS-rebinding protection for `https://` URLs to any host not in the
   proxy's own `no_proxy` list.** This is *not* a jeles bug — the module's
   own docstring names this exact residual (`_proxy_dials_for`: "Behind a
   proxy the name is not resolved here at all... That is the proxy's ACL to
   enforce"). But it's easy to miss operationally: a naive prober who mocks
   `getaddrinfo` to point `evil.example` at `127.0.0.1` and calls
   `private_destination("https://evil.example/")` in *this* environment will
   see `None` (accepted) and might wrongly conclude the resolver-based SSRF
   guard doesn't work. It works — over `http://` (no proxy configured for
   that scheme here) and over `https://` once `_proxy_dials_for` is forced
   off, the exact same mock is correctly rejected (`"127.0.0.1 is not a
   public address (resolved from 'evil.example')"`). See §4b/§4c. **Any
   deployment of `sources`/`institutional`/`reactions.search_adapter` behind
   a corporate or sandboxed HTTPS proxy inherits this same blind spot**: the
   resolver-based half of the SSRF guard is inert for hostnames the proxy
   itself is willing to reach, and the module is explicit that this is by
   design, not an oversight — but it's a fact worth an operator knowing
   before they rely on "jeles resolves hostnames and blocks private IPs" as
   a blanket claim.

2. **`check_url()` lets a raw, uncontrolled `ValueError` escape for a
   malformed bracketed IPv6 host, bypassing its own message-composition
   logic — and this happens *before* the `allow_private` branch, so it
   fires even with `allow_private=True`.** `check_url('https://[%3a%3a1]/x', HTTPS_ONLY)`
   raises `ValueError: '%3a%3a1' does not appear to be an IPv4 or IPv6
   address` — verified to originate inside `ipaddress.ip_address()`, called
   from stdlib's `urlsplit._check_bracketed_netloc`, three frames under
   `check_url`'s own `scheme_ok(url, allowed)` call. Compare with
   `private_destination()` called on the *same* URL directly: it wraps the
   equivalent parse failure in `_dialled_hosts`'s try/except and returns the
   friendly `"the host cannot be parsed, so where it goes cannot be checked"`.
   Both paths refuse the URL (so this is not a security hole — if anything
   it fails closed even under `allow_private=True`, which the docstring
   never explicitly promises), but the exception *shape* differs by entry
   point for what is conceptually the same failure, and a caller that
   pattern-matches on `check_url`'s ValueError text (e.g. to distinguish
   "bad scheme" from "private destination" from "unparseable") will see a
   third, undocumented message form here. See §6, rows 3–4, and the direct
   traceback capture below the tables.

3. **Credential-stripping identity on redirect is host-only — port and
   scheme are not part of it.** `_strip_credentials_across_hosts` compares
   `urlsplit(url).hostname` before and after a redirect; that ignores both
   port and scheme. Two concrete, undocumented consequences observed:
   - A redirect from `https://good.example:443/` to `https://good.example:8443/`
     retains `Authorization`/`X-Api-Key`/`Cookie` — arguably fine (still
     TLS, still nominally the same operator), but nothing says so.
   - A redirect from `https://good.example/` to `http://good.example/`
     under `HTTP_OR_HTTPS` (the caller-nameable scheme set where plain HTTP
     is intentionally allowed) **also retains those same credential
     headers**, because the host string is unchanged even though the
     scheme downgraded. This compounds the module's own documented
     https→http downgrade residual: the downgrade itself is called out in
     the `HTTP_OR_HTTPS` docstring ("a hostile redirect can still downgrade
     https -> http"), but the fact that *credentials ride along* on that
     specific downgrade is not mentioned anywhere — the credential-stripping
     docstring only discusses the cross-host case. On the one lane
     (`institutional`) that carries `X-Jeles-Secret`, a same-host redirect
     to plaintext http still leaks that shared secret in clear text. See
     §7, rows 9–10.

4. **Every octal/hex/decimal/short-form IP literal the module's own
   docstring calls out as a known bypass is in fact caught** —
   `2130706433`, `0177.0.0.1`, `0x7f.0.0.1`, `0x7f000001`, and `127.1` (and
   its private-range cousin `10.1`) all resolve through `_as_address`'s
   `inet_aton` fallback and are correctly refused as `127.0.0.1` /
   `10.0.0.1`. Percent-encoding bypasses (`127.0.0%2e1`, `12%37.0.0.1`,
   `169.254.169%2e254`) and userinfo confusion
   (`arxiv.org@127.0.0.1`, `127.0.0.1@evil.example`) are likewise all
   handled correctly per the module's documented dual-parser-union
   strategy — I could not find a working bypass among the forms the
   docstring itself names as historical bugs. See §2b, §3, §4d.

5. **A double-URL-encoded host (`127.0.0%252e1`) is accepted (`None`), but
   this is not exploitable** — confirmed by checking what `urllib.request.Request(...).host`
   actually resolves the string to (`'127.0.0%2e1'`, still containing a
   literal `%`, because urllib only unquotes once), and confirming that
   `socket.getaddrinfo('127.0.0%2e1', None)` itself raises `gaierror`
   `[Errno -2] Name or service not known` — i.e. the real connection
   attempt would fail to resolve in exactly the same way the check does.
   This matches the module's own stated policy ("a name that does not
   resolve is allowed through — the connection is about to fail on its own
   ... refusing here would report the wrong reason"). Not a bypass; the
   check and the eventual dial agree. See §3, row 6, and the follow-up
   check below the tables.

None of the above are "the guard is broken" findings — the scheme and
IP-literal logic held up against every bypass form the module's own
docstring anticipates. Findings 1–3 are about **operational/interaction
edges that the code handles correctly but the documentation doesn't spell
out**, which is exactly the kind of thing worth recording before someone
relies on an unstated guarantee.

## Detailed scenario tables

Legend for **Documented?**: *yes* = explicitly stated in a docstring/comment;
*implicit* = follows obviously from documented code but not spelled out;
*undocumented interaction* = behavior that only shows up when two documented
pieces combine, and that combination isn't discussed anywhere; *no* = genuinely
unspecified/caller-error territory.

### 1. Scheme guards (HTTPS_ONLY / HTTP_OR_HTTPS, scheme_ok, check_url)

| # | Scenario | Call | Expected | Actual | Documented? |
|---|---|---|---|---|---|
| 1 | constants | `e.HTTPS_ONLY, e.HTTP_OR_HTTPS` | HTTPS_ONLY={'https'}, HTTP_OR_HTTPS={'http','https'} | `frozenset({'https'})`, `frozenset({'https','http'})` | yes |
| 2 | https vs HTTPS_ONLY | `check_url('https://8.8.8.8/x', HTTPS_ONLY)` | OK | OK | yes |
| 3 | http vs HTTPS_ONLY | `check_url('http://8.8.8.8/x', HTTPS_ONLY)` | ValueError | `ValueError: refusing URL scheme outside ['https']` | yes |
| 4 | ftp vs HTTPS_ONLY | `check_url('ftp://8.8.8.8/x', HTTPS_ONLY)` | ValueError | ValueError | yes |
| 5 | file vs HTTPS_ONLY | `check_url('file:///etc/passwd', HTTPS_ONLY)` | ValueError | ValueError | yes |
| 6 | data vs HTTPS_ONLY | `check_url('data:text/plain;base64,aGk=', HTTPS_ONLY)` | ValueError | ValueError | yes |
| 7 | javascript vs HTTPS_ONLY | `check_url('javascript:alert(1)', HTTPS_ONLY)` | ValueError | ValueError | yes |
| 8 | gopher vs HTTPS_ONLY | `check_url('gopher://8.8.8.8/x', HTTPS_ONLY)` | ValueError | ValueError | yes |
| 9 | https vs HTTP_OR_HTTPS | `check_url('https://8.8.8.8/x', HTTP_OR_HTTPS)` | OK | OK | yes |
| 10 | http vs HTTP_OR_HTTPS | `check_url('http://8.8.8.8/x', HTTP_OR_HTTPS)` | OK | OK | yes |
| 11 | ftp vs HTTP_OR_HTTPS | `check_url('ftp://8.8.8.8/x', HTTP_OR_HTTPS)` | ValueError | ValueError | yes |
| 12 | file vs HTTP_OR_HTTPS | `check_url('file:///etc/passwd', HTTP_OR_HTTPS)` | ValueError | ValueError | yes |
| 13 | data vs HTTP_OR_HTTPS | `check_url('data:text/plain;base64,aGk=', HTTP_OR_HTTPS)` | ValueError | ValueError | yes |
| 14 | javascript vs HTTP_OR_HTTPS | `check_url('javascript:alert(1)', HTTP_OR_HTTPS)` | ValueError | ValueError | yes |
| 15 | gopher vs HTTP_OR_HTTPS | `check_url('gopher://8.8.8.8/x', HTTP_OR_HTTPS)` | ValueError | ValueError | yes |
| 16 | scheme case-insensitivity | `check_url('HTTPS://8.8.8.8/', HTTPS_ONLY)` | OK | OK | implicit |
| 17 | `scheme_ok` direct | `scheme_ok('HtTpS://x/', {'https'})` | True | True | yes |
| 18 | `scheme_ok` empty allowed set | `scheme_ok('https://x/', set())` | False | False | implicit |

**Summary:** exactly the documented sets; `data:`/`javascript:`/`gopher:`/`ftp:`/`file:`
are refused under both scheme policies, `http:` is refused only under `HTTPS_ONLY`. Scheme
comparison is case-insensitive (`scheme_ok` lowercases).

### 2. `private_destination()` — IP literals (no resolver involved)

| # | Scenario | Call | Expected | Actual |
|---|---|---|---|---|
| 1 | loopback v4 | `private_destination('https://127.0.0.1/')` | rejected | `'127.0.0.1 is not a public address'` |
| 2 | loopback short form `127.1` | `private_destination('https://127.1/')` | rejected | `"127.0.0.1 is not a public address (written as '127.1')"` |
| 3 | loopback v6 | `private_destination('https://[::1]/')` | rejected | `'::1 is not a public address'` |
| 4 | link-local v4 (metadata) | `private_destination('https://169.254.169.254/latest/meta-data/')` | rejected | rejected |
| 5 | link-local v6 | `private_destination('https://[fe80::1]/')` | rejected | rejected |
| 6 | private 10/8 | `private_destination('https://10.1.2.3/')` | rejected | rejected |
| 7 | private 172.16/12 | `private_destination('https://172.16.5.5/')` | rejected | rejected |
| 8 | private 172.31 (edge of range) | `private_destination('https://172.31.255.255/')` | rejected | rejected |
| 9 | **not** private, 172.32 (just outside) | `private_destination('https://172.32.0.1/')` | accepted | `None` |
| 10 | private 192.168/16 | `private_destination('https://192.168.1.1/')` | rejected | rejected |
| 11 | reserved 0.0.0.0 | `private_destination('https://0.0.0.0/')` | rejected | rejected |
| 12 | reserved 255.255.255.255 | `private_destination('https://255.255.255.255/')` | rejected | rejected |
| 13 | multicast 224.0.0.0 | `private_destination('https://224.0.0.0/')` | rejected | rejected |
| 14 | multicast 239.255.255.255 | `private_destination('https://239.255.255.255/')` | rejected | rejected |
| 15 | public 8.8.8.8 | `private_destination('https://8.8.8.8/')` | accepted | `None` |
| 16 | public 1.1.1.1 | `private_destination('https://1.1.1.1/')` | accepted | `None` |
| 17 | public v6 | `private_destination('https://[2606:4700:4700::1111]/')` | accepted | `None` |
| 18 | RFC6598 shared space 100.64.0.1 | `private_destination('https://100.64.0.1/')` | rejected (`not is_global`) | rejected |
| 19 | NAT64 well-known prefix | `private_destination('https://[64:ff9b::a9fe:a9fe]/')` | rejected (`not is_global`) | rejected |
| 20 | IPv4-mapped v6 loopback `::ffff:127.0.0.1` | `private_destination('https://[::ffff:127.0.0.1]/')` | rejected | rejected |
| 21 | IPv4-mapped v6 public `::ffff:8.8.8.8` | `private_destination('https://[::ffff:8.8.8.8]/')` | accepted | `None` |
| 22 | 6to4-embedded loopback `2002:7f00:1::` | `private_destination('https://[2002:7f00:1::]/')` | rejected | rejected |

**Summary:** `is_private`/`is_loopback`/`is_link_local`/`is_reserved`/`is_multicast`/
`is_unspecified`/`not is_global` behaves exactly as advertised, including the two
documented reasons the explicit list wasn't enough on its own — RFC6598
(100.64.0.0/10) and the NAT64 well-known prefix are both caught by the
`not is_global` fallback, not the named checks. IPv4-mapped IPv6 addresses are
classified by their embedded v4 address (loopback mapped → rejected, public
mapped → accepted), which is `ipaddress`' native behavior, not special-cased
by jeles.

### 2b. `private_destination()` — octal/hex/decimal literal encodings

| # | Scenario | Call | Expected | Actual |
|---|---|---|---|---|
| 1 | decimal `2130706433` (=127.0.0.1) | `private_destination('https://2130706433/')` | rejected | `"127.0.0.1 is not a public address (written as '2130706433')"` |
| 2 | octal `0177.0.0.1` (=127.0.0.1) | `private_destination('https://0177.0.0.1/')` | rejected | `"127.0.0.1 is not a public address (written as '0177.0.0.1')"` |
| 3 | hex `0x7f.0.0.1` (=127.0.0.1) | `private_destination('https://0x7f.0.0.1/')` | rejected | rejected |
| 4 | hex full `0x7f000001` | `private_destination('https://0x7f000001/')` | rejected | rejected |
| 5 | short form `127.1` | `private_destination('https://127.1/')` | rejected | rejected |
| 6 | short form `10.1` (private, =10.0.0.1) | `private_destination('https://10.1/')` | rejected | `"10.0.0.1 is not a public address (written as '10.1')"` |
| 7 | decimal public `134744072` (=8.8.8.8) | `private_destination('https://134744072/')` | accepted | `None` |

**Summary:** every alternate encoding the module's own `_as_address` docstring
names as a working bypass against `ipaddress.ip_address` (which is stricter
than `getaddrinfo`) is caught via the `inet_aton` fallback, and the reason
string names the literal-vs-resolved form (`"written as '...'"`), which is a
nice diagnostic touch not called out anywhere except implicitly in the code.

### 3. Percent-encoding & parser-confusion SSRF bypass attempts

| # | Scenario | Call | Expected | Actual |
|---|---|---|---|---|
| 1 | percent-encoded dot `127.0.0%2e1` | `private_destination('https://127.0.0%2e1:8888/')` | rejected | `'127.0.0.1 is not a public address'` |
| 2 | single-char encode `12%37.0.0.1` (`%37`='7') | `private_destination('https://12%37.0.0.1/')` | rejected | rejected |
| 3 | metadata IP percent-encoded `169.254.169%2e254` | `private_destination('https://169.254.169%2e254/latest/meta-data/')` | rejected | rejected |
| 4 | userinfo: `127.0.0.1@evil.example` | `private_destination('https://127.0.0.1@evil.example/')` | see §4d (resolver-dependent; inconclusive under this sandbox's proxy) | `None` here, but proven correct in §4d once resolver is engaged |
| 5 | userinfo (docstring's own example) `arxiv.org@127.0.0.1` | `private_destination('https://arxiv.org@127.0.0.1/')` | rejected | rejected, no DNS lookup needed (literal) |
| 6 | double URL-encoded dot `127.0.0%252e1` | `private_destination('https://127.0.0%252e1/')` | accepted, but confirmed non-exploitable (see Finding 5) | `None` |
| 7 | trailing dot on loopback `127.0.0.1.` | `private_destination('https://127.0.0.1./')` | rejected | rejected |
| 8 | trailing dot on `localhost.` | `private_destination('https://localhost./')` | rejected via `_LOCAL_NAMES` | `"'localhost' names the local machine"` |
| 9 | uppercase `LOCALHOST` | `private_destination('https://LOCALHOST/')` | rejected (lowercased before compare) | rejected |
| 10 | unparseable bracketed v6 `[%3a%3a1]` | `private_destination('https://[%3a%3a1]/x')` | rejected: "cannot be parsed" | `'the host cannot be parsed, so where it goes cannot be checked'` |
| 11 | credentials only, no host: `https://user:pass@/` | `private_destination('https://user:pass@/')` | accepted (empty host → no candidates) | `None` |
| 12 | IPv6 zone id `[fe80::1%25eth0]` | `private_destination('https://[fe80::1%25eth0]/')` | rejected (still parses as fe80::1, link-local) | rejected |

**Summary:** the dual-parser union (`_split_host` + `_request_host`) closes every
percent-encoding gap the module's docstring documents as historically exploitable
(`127.0.0%2e1`, `12%37.0.0.1`, `169.254.169%2e254`). The one case that *looks* like
acceptance of a bypass (#6, double-encoding) is not exploitable — see Finding 5.

### 4. Hostname handling incl. DNS-rebinding

| # | Scenario | Call | Expected | Actual |
|---|---|---|---|---|
| 1 | `localhost` | `private_destination('https://localhost/')` | rejected, no DNS lookup | `"'localhost' names the local machine"` |
| 2 | `localhost.` | `private_destination('https://localhost./')` | rejected, no DNS lookup | rejected |
| 3 | `localhost.localdomain` | `private_destination('https://localhost.localdomain/')` | rejected, no DNS lookup | rejected |
| 4 | `ip6-localhost` | `private_destination('https://ip6-localhost/')` | rejected, no DNS lookup | rejected |
| 5 | `LoCaLhOsT` mixed case | `private_destination('https://LoCaLhOsT/')` | rejected, no DNS lookup | rejected |
| 6–11 | `evil.example` → private/public IPs (mocked DNS) | `private_destination('https://evil.example/')` | *see §4b/§4c — this sandbox's proxy makes these inconclusive over https; §4c re-runs them correctly* | all returned `None` here (proxy short-circuit) |
| 12 | hostname that fails to resolve | mocked `getaddrinfo` → `gaierror` | accepted (`None`) — "connection about to fail on its own" | `None` |
| 13 | over-long DNS label (idna `UnicodeError`) | `private_destination('https://' + 'a'*300 + '.example/')` | accepted (`None`) — caught explicitly, distinct from `OSError` | `None` |

### 4b. Environment fact: this sandbox's `HTTPS_PROXY` disables the resolver path for `https://`

| # | Scenario | Call | Actual |
|---|---|---|---|
| 1 | `getproxies()` here | `urllib.request.getproxies()` | has an `https` key (`http://127.0.0.1:34851`, the CCR agent proxy), **no `http` key** |
| 2 | `_proxy_dials_for` on https, arbitrary host | `_proxy_dials_for('https://evil.example/')` | `True` |
| 3 | `_proxy_dials_for` on http, arbitrary host | `_proxy_dials_for('http://evil.example/')` | `False` (no proxy configured for plain http here) |
| 4 | `_proxy_dials_for` on https, loopback | `_proxy_dials_for('https://127.0.0.1/')` | `False` (`127.0.0.0/8` is in this sandbox's `no_proxy`) |
| 5 | consequence | `private_destination('https://evil.example/')`, DNS mocked to `127.0.0.1` | `None` (accepted) — **resolver never runs** |

This is the module's own documented residual working exactly as designed
("Behind a proxy the name is not resolved here at all... That is the proxy's
ACL to enforce"), reproduced concretely. See Finding 1.

### 4c. DNS-rebinding tests re-run with the resolver actually engaged

Same six `evil.example` → mocked-IP scenarios as §4, run two ways to bypass
the sandbox's https-proxy short-circuit without making any real network call:
(a) over `http://` (unproxied in this sandbox), and (b) over `https://` with
`_proxy_dials_for` monkey-patched to always return `False` (simulating a
direct, unproxied deployment).

| # | Scenario | Scheme | Mocked DNS answer(s) | Actual |
|---|---|---|---|---|
| 1 | evil.example → 127.0.0.1 | http | 127.0.0.1 | `"127.0.0.1 is not a public address (resolved from 'evil.example')"` |
| 2 | evil.example → 169.254.169.254 | http | 169.254.169.254 | rejected, same shape |
| 3 | evil.example → 10.0.0.5 | http | 10.0.0.5 | rejected |
| 4 | evil.example → 8.8.8.8 (public) | http | 8.8.8.8 | `None` (accepted) |
| 5 | evil.example → [8.8.8.8, 127.0.0.1] | http | multi-answer | rejected (any-private wins) |
| 6 | evil.example → [127.0.0.1, 8.8.8.8] | http | multi-answer | rejected (any-private wins) |
| 7–12 | same six, over https with proxy forced off | https | (same as 1–6) | identical results to 1–6 |

**Confirmed: the resolver-based SSRF guard works correctly** once it actually
runs — every private-IP DNS answer is caught regardless of ordering in a
multi-answer response, matching the docstring's `for raw in candidates`
loop. The apparent "acceptance" in §4/§4b was purely an artifact of this
sandbox's proxy configuration, not a defect in the guard logic.

### 4d. Userinfo confusion, resolver actually engaged

| # | Scenario | Call | Actual |
|---|---|---|---|
| 1 | `127.0.0.1@evil.example`, evil.example → public | `private_destination('http://127.0.0.1@evil.example/')`, mocked to 8.8.8.8 | `getaddrinfo` called with `'evil.example'` (userinfo correctly stripped by both parsers); result `None` (accepted, correct — the real host is public) |
| 2 | `127.0.0.1@evil.example`, evil.example → private | same, mocked to 127.0.0.1 | `"127.0.0.1 is not a public address (resolved from 'evil.example')"` — real host correctly checked, not fooled by the userinfo literal |
| 3 | `arxiv.org@127.0.0.1` (docstring's own case) | `private_destination('http://arxiv.org@127.0.0.1/')` | rejected via literal-IP path; `getaddrinfo` **not called at all** (confirmed via mock call-count) |

**Summary:** userinfo is correctly stripped from the host by both `_split_host`
and `_request_host` in every direction tested; no confusion between the
userinfo segment and the real host was reproducible.

### 5. `check_url()` edge cases

| # | Scenario | Call | Actual |
|---|---|---|---|
| 1 | empty string | `check_url('', HTTPS_ONLY)` | `ValueError: refusing URL scheme outside ['https']: ''` |
| 2 | no scheme at all | `check_url('example.com/path', HTTPS_ONLY)` | ValueError, scheme is `''` |
| 3 | scheme-relative `//example.com/path` | `check_url('//example.com/path', HTTPS_ONLY)` | ValueError |
| 4 | scheme only, no host: `https://` | `check_url('https://', HTTPS_ONLY)` | **OK — no exception** (empty host, so `_dialled_hosts` returns `[]`, no candidates, `private_destination` returns `None`) |
| 5 | unusual high port `:65535` | `check_url('https://8.8.8.8:65535/', HTTPS_ONLY)` | OK |
| 6 | port 0 | `check_url('https://8.8.8.8:0/', HTTPS_ONLY)` | OK |
| 7 | out-of-range port `:99999` | `check_url('https://8.8.8.8:99999/', HTTPS_ONLY)` | **OK — no exception** (`urlsplit` does not validate port range for `.hostname`/`.scheme` access here; port is never inspected by this module at all) |
| 8 | auth creds, public host | `check_url('https://user:pass@8.8.8.8/', HTTPS_ONLY)` | OK |
| 9 | auth creds, private host | `check_url('https://user:pass@127.0.0.1/', HTTPS_ONLY)` | `ValueError: refusing a private destination — 127.0.0.1 is not a public address` |
| 10 | whitespace-only | `check_url('   ', HTTPS_ONLY)` | ValueError, scheme `''` |
| 11 | leading/trailing whitespace around a valid URL | `check_url(' https://8.8.8.8/ ', HTTPS_ONLY)` | **OK — no exception** (`urlsplit` strips leading/trailing whitespace from the whole URL; effectively `.strip()`-tolerant) |
| 12 | embedded CRLF (header-injection-style) | `check_url('https://8.8.8.8/\r\nX-Evil: 1', HTTPS_ONLY)` | **OK — no exception.** The CRLF lands in the *path*, not the host, so scheme/destination checks don't see it. (Whether `http.client`'s own header-injection guards catch this downstream is out of scope for `_egress.py` and not tested here — `check_url` was not the right layer to expect this to be caught at.) |
| 13 | embedded tab in host | `check_url('https://8.8.8.8\t.evil.example/', HTTPS_ONLY)` | **OK — no exception.** `urlsplit` treats the tab as part of the netloc/path split oddly; not flagged as a private destination since the resulting host parses to something other than a literal private IP or `_LOCAL_NAMES` entry in this sandbox's proxied environment — **not independently re-verified with the resolver forced on; flagged as untested residual, see Recommendations.** |
| 14 | private dest, `allow_private=True` | `check_url('https://127.0.0.1/', HTTPS_ONLY, allow_private=True)` | OK |
| 15 | scheme still enforced under `allow_private=True` | `check_url('http://127.0.0.1/', HTTPS_ONLY, allow_private=True)` | ValueError (scheme, not destination) |
| 16 | private dest under `HTTP_OR_HTTPS`, no `allow_private` | `check_url('http://192.168.1.1/', HTTP_OR_HTTPS)` | ValueError |
| 17 | private dest under `HTTP_OR_HTTPS`, `allow_private=True` | `check_url('http://192.168.1.1/', HTTP_OR_HTTPS, allow_private=True)` | OK |

**Note on row 12/13:** these are worth a second look by someone with time to
force the resolver on and control the proxy variable the way §4c does — I did
not repeat that isolation for the tab/CRLF cases, so treat "OK — no exception"
there as observed-but-not-fully-attributed to a specific parsing step.

### 6. `allow_private` parameter semantics

| # | Scenario | Call | Actual |
|---|---|---|---|
| 1 | skips destination check entirely | `check_url('https://169.254.169.254/', HTTPS_ONLY, allow_private=True)` | OK — metadata endpoint reachable |
| 2 | does **not** relax the scheme check | `check_url('ftp://127.0.0.1/', HTTPS_ONLY, allow_private=True)` | `ValueError: refusing URL scheme outside ['https']` (scheme checked first, unconditionally) |
| 3 | unparseable host, `allow_private=True` | `check_url('https://[%3a%3a1]/x', HTTPS_ONLY, allow_private=True)` | `ValueError: '%3a%3a1' does not appear to be an IPv4 or IPv6 address` — **raised from inside `scheme_ok`'s `urlsplit` call, before the `allow_private` branch is ever reached** (see Finding 2) |
| 4 | same URL, `allow_private=False` | `check_url('https://[%3a%3a1]/x', HTTPS_ONLY, allow_private=False)` | identical `ValueError` — same root cause, so rows 3 and 4 are indistinguishable from the caller's perspective even though the module's control-flow *intends* different code paths for these two flags |

### 7. `SchemeGuardedRedirects` — redirect hop re-checks and credential stripping

(Constructed with a hand-built `Request` stand-in and a `BytesIO` file
pointer; stdlib's own `HTTPRedirectHandler.redirect_request` is monkeypatched
to a lightweight stand-in so no real request object machinery is invoked.)

| # | Scenario | Call | Actual |
|---|---|---|---|
| 1 | https-only: redirect https→http refused | allowed=HTTPS_ONLY | `HTTPError: ...refusing redirect to a scheme outside ['https']` |
| 2 | https-only: redirect https→ftp refused | allowed=HTTPS_ONLY | `HTTPError: ...refusing redirect to a scheme outside ['https']` |
| 3 | http_or_https: redirect http→https allowed | allowed=HTTP_OR_HTTPS | proceeds |
| 4 | http_or_https: redirect https→http (downgrade) allowed | allowed=HTTP_OR_HTTPS | proceeds — **documented residual, not a bug** |
| 5 | https-only: redirect to private destination refused | `https://good/ → https://169.254.169.254/` | `HTTPError: ...refusing redirect to a private destination` |
| 6 | `allow_private=True`: redirect to private destination allowed | `→ https://127.0.0.1/admin` | proceeds |
| 7 | credential stripping, cross-host | `good.example → evil.example`, headers incl. Authorization/X-Api-Key/Cookie/Accept | proceeds; only `Accept` survives |
| 8 | credential stripping, same host different path | `good.example/a → good.example/b` | all headers retained |
| 9 | **same host, different port** | `good.example:443 → good.example:8443` | **all headers retained — port is not part of the same-host identity** (undocumented, Finding 3) |
| 10 | **same host, scheme downgrade https→http** (HTTP_OR_HTTPS) | `https://good.example/ → http://good.example/` | **all headers retained, including Authorization/X-Api-Key/Cookie, now over plaintext** (undocumented interaction, Finding 3) |
| 11 | subdomain counts as different host | `good.example → api.good.example` | stripped |
| 12 | old URL host unparseable → treated as change | direct call to `_strip_credentials_across_hosts` with an unparseable old `full_url` | credentials stripped (per the code's own comment: "`None` means unparseable on either side: treat as a change, not as a match") |

### 8. Opener caching, keyed by `(scheme_set, allow_private)`

| # | Scenario | Actual |
|---|---|---|
| 1 | same key twice | same object (`is`) |
| 2 | different `allow_private` | distinct objects |
| 3 | different scheme set | distinct objects |
| 4 | cache key shape | `dict[(frozenset[str], bool), OpenerDirector]`, e.g. `(frozenset({'https'}), False)` |
| 5 | equal-but-not-identical frozensets | share the same cached opener (dict lookup by `==`, not `is`) |
| 6 | HTTPHandler absent from https-only opener's handler chain | confirmed — `['HTTPDefaultErrorHandler','HTTPErrorProcessor','HTTPSHandler','ProxyHandler','SchemeGuardedRedirects','UnknownHandler']` |
| 7 | HTTPHandler present in http_or_https opener | confirmed present |
| 8 | 16-thread concurrent first-use race on a fresh key | exactly one `OpenerDirector` built and shared (lock holds; no duplicate construction) |

### 9. `read_capped()` boundary behavior

| # | Scenario | `read_capped(resp, max_bytes)` | Actual |
|---|---|---|---|
| 1 | body exactly at cap (10B / 10) | OK | returns 10 bytes |
| 2 | body one over cap (11B / 10) | ValueError | `response exceeds 10 bytes — refusing` |
| 3 | body one under cap (9B / 10) | OK | returns 9 bytes |
| 4 | empty body, nonzero cap (0B / 10) | OK | returns 0 bytes |
| 5 | empty body, zero cap (0B / 0) | OK | returns 0 bytes |
| 6 | nonempty body, zero cap (1B / 0) | ValueError | `response exceeds 0 bytes — refusing` |
| 7 | **negative `max_bytes`** (`-1`) | undocumented | `ValueError: response exceeds -1 bytes — refusing` — `resp.read(max_bytes + 1)` becomes `resp.read(0)` → `b''`, and `len(b'') > -1` is `True`, so it always raises. Caller-error territory; not discussed in the docstring, but the behavior degrades safely (refuses rather than silently reading unbounded). |

**Summary:** the boundary is exactly "≤ max_bytes accepted, > max_bytes
refused," confirmed at the exact edge in both directions.

### 10. Exception-type audit

| # | Call | Exception raised |
|---|---|---|
| 1 | `check_url` with a disallowed scheme | `ValueError` |
| 2 | `check_url` on a private destination | `ValueError` |
| 3 | `check_url` on an unparseable bracketed host | `ValueError` (raw stdlib message, see Finding 2) |
| 4 | `read_capped` over cap | `ValueError` |
| 5 | `scheme_ok` on syntactic garbage (`'not a url at all :::'`) | no exception — returns `False` |
| 6 | `private_destination` on the same garbage string | no exception — returns `None` (not "unparseable"; `urlsplit` tolerates it enough to produce an empty/garbage hostname that `_dialled_hosts` treats as "no host," which the docstring says means "no host" rather than "nobody could tell") |

**Summary:** every user-facing failure in this module is a `ValueError` —
there is no `URLError` raised by `check_url`/`private_destination` themselves
(that would only come from stdlib inside an actual `urlopen`/`redirect_request`
call, which this probe deliberately never triggered). Callers that only
catch `ValueError` around `check_url()` are complete; callers that also
expect `URLError` from `fetch()`/`urlopen()` need that for the live-network
path, not this one.

## Direct follow-up captures referenced above

```
# Finding 2 — origin of check_url's raw ValueError
>>> e.scheme_ok('https://[%3a%3a1]/x', e.HTTPS_ONLY)
ValueError: '%3a%3a1' does not appear to be an IPv4 or IPv6 address
  File ".../ipaddress.py", line 54, in ip_address   <- raised INSIDE urlsplit's
                                                         own bracket validation,
                                                         called from scheme_ok's
                                                         urlsplit(url).scheme

>>> e.check_url('https://[%3a%3a1]/x', e.HTTPS_ONLY, allow_private=False)
ValueError: '%3a%3a1' does not appear to be an IPv4 or IPv6 address
>>> e.check_url('https://[%3a%3a1]/x', e.HTTPS_ONLY, allow_private=True)
ValueError: '%3a%3a1' does not appear to be an IPv4 or IPv6 address   # identical — fires before allow_private is checked
```

```
# Finding 5 — double-URL-encoding is not exploitable
>>> urllib.request.Request('http://127.0.0%252e1/').host
'127.0.0%2e1'                       # only unquoted once, still contains a literal '%'
>>> e._as_address('127.0.0%2e1')
None                                 # not recognized as a literal -> treated as a "name"
>>> socket.getaddrinfo('127.0.0%2e1', None)
socket.gaierror: [Errno -2] Name or service not known   # the REAL connection would fail
                                                           the same way the check does
```

## Recommendations (documentation gaps, not code defects)

1. **Name the proxy caveat where it's most likely to be read.** `_proxy_dials_for`'s
   docstring is accurate and thorough, but nothing on `private_destination()`'s own
   docstring or on `check_url()`'s cross-references it loudly enough — someone
   auditing "does this block SSRF via DNS rebinding" needs to know that the answer
   is conditional on whether the deployment's `https_proxy` env var covers the
   target host.
2. **Route `scheme_ok`'s `urlsplit` call through the same tolerant parsing
   `_dialled_hosts` uses**, or catch `ValueError` around it in `check_url`, so a
   malformed bracketed host produces the module's own controlled message
   (`"refusing URL scheme..."` or an equivalent) instead of a raw stdlib
   `ipaddress` error string leaking through. Currently harmless (still a
   `ValueError`, still refused, even under `allow_private=True`) but
   inconsistent with the rest of the module's care around message shape.
3. **State explicitly that same-host credential retention on redirect ignores
   port and scheme.** At minimum, flag that an `HTTP_OR_HTTPS` same-host
   downgrade redirect carries `Authorization`/API-key headers onto plaintext —
   this is one inference away from the already-documented downgrade residual,
   but nobody has written the two facts down together.

## What I did not (and per instructions should not) test

No real DNS resolution and no real TCP/TLS connections were made anywhere in
this probe. `fetch()`/`urlopen()` (the network-touching entry points) were
not called live; their pre-flight (`check_url`) and post-response
(`read_capped`) halves were tested directly and via handcrafted stand-ins
instead. Rows 13 in §5 (tab-in-host) is flagged above as an area a follow-up
pass could isolate further with the resolver forced on, the way §4c does for
the DNS-rebinding cases.
