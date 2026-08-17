# Why the numbers are published

*The argument behind the [Accuracy](../README.md#accuracy-and-how-to-measure-yours)
section: why a measured false-verification rate lives in the README rather than a
better adjective. Linked from there.*

---

The [README](../README.md#accuracy-and-how-to-measure-yours) admits a failure
rate, in public. That is deliberate, and it is the point of the section rather
than a caveat attached to it.

*"We are accurate"* is a claim anyone evaluating a system for a regulated
process already knows is unfalsifiable. It names no rate, no corpus and no
cutoff, so it cannot be wrong, which is exactly why it cannot be relied on
either. The replacement is not a better adjective:

> Here is the measured false-verification rate. Here is the dial that sets it.
> Here is the harness — run it against your own corpus and get your own number.

Each of those three is a file in this repository. The harness is `bench/`; the
dial is `SEAL_THRESHOLD` and `nestor calibrate`; the numbers are committed under
[`bench/results/`](../bench/results/) as JSON carrying the parameters, the
environment and the git revision of the run that produced them, so a result can
be cited and re-derived rather than quoted. `"complete": false` marks a prefix
rather than an answer, which is a distinction a marketing number would not
bother to keep.

The argument runs the same way as the rest of the system. A seal is worth
something because a forged one is refused and the chain says so; a measurement
is worth something because the method is published and the run can be repeated.
Neither is a promise about how good this is. Both are structures that make the
claim checkable by somebody who does not trust us — which is the only kind of
claim worth making to a buyer whose job is not trusting vendors.

For the sixty-second version of the whole argument, including the failure mode
where "thirty days" matches "sixty days", run `python demo/sixty_seconds.py`.
