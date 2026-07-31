"""The dashboard, and the contract it has with the results it renders.

`bench/serve_ui.py` serves static files and committed JSON. There is nothing to
mock and nothing to seal, so what is worth pinning is the seam: the dashboard
reads fields out of `bench/results/*.json`, and those files are rewritten by
every bench run. Drift there is silent — the page renders an empty chart, or
throws, and the numbers look like they were never measured.

That is not hypothetical. The dashboard arrived on a branch whose default tab
was the review playground, and its Accuracy tab threw on the first render
against any results file at all; nobody saw it because nobody landed on that tab.
"""
import json
import pathlib

import pytest

RESULTS = pathlib.Path(__file__).resolve().parent.parent / "bench" / "results"
UI = pathlib.Path(__file__).resolve().parent.parent / "bench" / "ui"
APP_JS = (UI / "app.js").read_text(encoding="utf-8")


def test_the_dashboard_is_self_contained():
    """Stdlib server, no build step, and nothing fetched off-origin."""
    assert (UI / "index.html").exists() and (UI / "app.css").exists()
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert "//" not in html.split("<body")[0].replace("http://www.w3.org", ""), \
        "no external stylesheet, font or script in the head"


def test_the_dashboard_cannot_record_a_decision():
    """One review surface. This is not it — see bench/serve_ui.py's docstring."""
    serve_ui = (UI.parent / "serve_ui.py").read_text(encoding="utf-8")
    assert "do_POST" not in serve_ui
    assert "/api/" not in APP_JS
    for word in ("seal", "approve", "reject"):
        assert f'"/api/{word}"' not in APP_JS


@pytest.mark.parametrize("bench", ["accuracy", "margin"])
def test_every_field_the_dashboard_reads_is_in_the_results(bench):
    doc = json.loads((RESULTS / f"{bench}.json").read_text(encoding="utf-8"))
    assert doc["runs"], f"{bench}.json has no runs"
    for run in doc["runs"]:
        # renderGlobalControls / runLabel / shippedThreshold
        for field in ("run_id", "recorded_at", "complete", "params", "measurements"):
            assert field in run, f"{bench} run is missing {field}"
        assert run["measurements"], f"{bench} run {run['run_id']} has no measurements"
        # Accuracy charts a sweep over thresholds; margin charts a threshold ×
        # margin grid. Both label the row from corpus and size.
        rows = "sweep" if bench == "accuracy" else "grid"
        for m in run["measurements"]:
            assert {"corpus", "size", rows} <= set(m), f"{bench} measurement fields"


def test_the_accuracy_sweep_carries_the_three_series_that_are_charted():
    doc = json.loads((RESULTS / "accuracy.json").read_text(encoding="utf-8"))
    for run in doc["runs"]:
        for m in run["measurements"]:
            for row in m["sweep"]:
                assert {"threshold", "false_seal_rate", "recall_paraphrase",
                        "recall_surface"} <= set(row)


def test_the_margin_grid_carries_what_the_heatmap_colours_by():
    doc = json.loads((RESULTS / "margin.json").read_text(encoding="utf-8"))
    for run in doc["runs"]:
        for m in run["measurements"]:
            for cell in m["grid"]:
                assert {"threshold", "margin", "false_seal_rate", "recall"} <= set(cell)


def test_the_shipped_threshold_line_has_a_point_to_sit_on():
    """The dashed line marks the threshold Nestor actually ships. A sweep that
    steps over it draws the line through empty space."""
    from nestor import memory

    doc = json.loads((RESULTS / "accuracy.json").read_text(encoding="utf-8"))
    for run in doc["runs"]:
        shipped = run.get("params", {}).get("seal_threshold", memory.SEAL_THRESHOLD)
        for m in run["measurements"]:
            assert any(abs(r["threshold"] - shipped) < 1e-9 for r in m["sweep"]), \
                f"{run['run_id']}/{m['corpus']} never measures {shipped}"
