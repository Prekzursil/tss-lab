"""Demonstration runner for the manual mutation-testing lab (tasks 5 & 6).

For each of the three hand-built order-1 mutants of ``pricing.py`` in this
directory it:

1. runs the CHOSEN test case
   ``tests/test_mcdc.py::test_mcdc_c03_compute_fee_type_percent``
   (the MC/DC pair for condition C3, ``fee_type == "percent"``,
   pricing.py:59) against the mutant, and
2. runs the FULL suite (tests/test_ep.py, test_bva.py, test_ceg.py,
   test_mcdc.py -- 212 tests) against the mutant,

each in an isolated sandbox where the mutant file is installed as
``pricing.py`` (the tests import ``pricing`` via tests/conftest.py), and then

3. prints KILLED / SURVIVED / EQUIVALENT verdict lines and checks them
   against the claims made in ``tss/lab/docs/mutants-manual.md``:

   - mutant_equivalent  -> EQUIVALENT (survives every possible test; proof in
     docs/mutants-manual.md). Also probed in-process on the only input state
     where the mutated branch fires (total == 0).
   - mutant_killed      -> KILLED by the chosen test (non-equivalent).
   - mutant_surviving   -> SURVIVED by the chosen test (non-equivalent; the
     full suite kills it, which is the empirical proof of non-equivalence).

Additionally it executes, in-process, the distinguishing inputs that prove
non-equivalence of the two non-equivalent mutants (original vs mutant outputs
shown side by side).

Exit code 0 iff every printed verdict matches the claim.

Usage:  python tss/lab/mutants/run_demo.py
"""

from __future__ import annotations

import dataclasses
import importlib
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

MUTANTS_DIR = Path(__file__).resolve().parent
LAB_ROOT = MUTANTS_DIR.parent
TESTS_DIR = LAB_ROOT / "tests"

CHOSEN_TEST = "tests/test_mcdc.py::test_mcdc_c03_compute_fee_type_percent"

VARIANTS = [
    # (module file, claim for the chosen test, claim for the full suite, verdict claim)
    ("mutant_equivalent", "SURVIVED", "SURVIVED", "EQUIVALENT"),
    ("mutant_killed", "KILLED", "KILLED", "KILLED"),
    ("mutant_surviving", "SURVIVED", "KILLED", "SURVIVED"),
]


# ---------------------------------------------------------------------------
# In-process probes (original module vs each mutant module)
# ---------------------------------------------------------------------------

def _fields(breakdown) -> tuple:
    """Field tuple of a PricingBreakdown (compares across modules)."""
    return tuple((f.name, getattr(breakdown, f.name)) for f in dataclasses.fields(breakdown))


def _load(name: str):
    sys.path.insert(0, str(LAB_ROOT))
    sys.path.insert(0, str(MUTANTS_DIR))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.remove(str(LAB_ROOT))
        sys.path.remove(str(MUTANTS_DIR))


def probe_distinguishing_inputs() -> bool:
    """Show inputs on which the two NON-equivalent mutants differ from the
    original (proof of non-equivalence), and inputs on which the equivalent
    mutant matches it (including the only state where its branch fires)."""
    ok = True
    orig = _load("pricing")

    print("--- distinguishing-input probes (in-process, original vs mutant) ---")

    # mutant_killed: the chosen test's percent row.
    mk = _load("mutant_killed")
    kwargs = dict(
        taxable_subtotal=Decimal("200"), enabled=True,
        fee_type="percent", fee_value=Decimal("5"),
    )
    o, m = orig.compute_fee(**kwargs), mk.compute_fee(**kwargs)
    differs = o != m
    ok &= differs
    print(f"[mutant_killed]     compute_fee(taxable=200, enabled=True, percent, 5): "
          f"original={o} mutant={m} -> {'DIFFER (non-equivalent)' if differs else 'IDENTICAL (!! claim broken)'}")

    # mutant_surviving: a positive fee_value inside the shifted boundary (0, 4].
    ms = _load("mutant_surviving")
    kwargs = dict(
        taxable_subtotal=Decimal("100"), enabled=True,
        fee_type="flat", fee_value=Decimal("2"),
    )
    o, m = orig.compute_fee(**kwargs), ms.compute_fee(**kwargs)
    differs = o != m
    ok &= differs
    print(f"[mutant_surviving]  compute_fee(taxable=100, enabled=True, flat, 2):    "
          f"original={o} mutant={m} -> {'DIFFER (non-equivalent)' if differs else 'IDENTICAL (!! claim broken)'}")

    # mutant_equivalent: the ONLY input state where the mutated branch fires is
    # total == 0 (sum-of-nonnegatives argument); probe it plus neighbours.
    me = _load("mutant_equivalent")
    neutral = dict(
        subtotal=Decimal("0"), discount=Decimal("0"), shipping=Decimal("0"),
        fee_enabled=False, fee_type="flat", fee_value=Decimal("0"),
        vat_enabled=False, vat_rate_percent=Decimal("0"),
        vat_apply_to_shipping=False, vat_apply_to_fee=False,
    )
    cases = {
        "all-zero (total==0, mutated branch FIRES)": {},
        "negative subtotal (total==0, fires)": {"subtotal": Decimal("-50")},
        "normal positive (total>0)": {"subtotal": Decimal("100")},
        "full scenario (total 203.50)": {
            "subtotal": Decimal("200"), "discount": Decimal("50"),
            "shipping": Decimal("20"), "fee_enabled": True,
            "fee_type": "percent", "fee_value": Decimal("10"),
            "vat_enabled": True, "vat_rate_percent": Decimal("10"),
            "vat_apply_to_shipping": True, "vat_apply_to_fee": True,
        },
    }
    for label, overrides in cases.items():
        kw = dict(neutral, **overrides)
        o, m = orig.compute_totals(**kw), me.compute_totals(**kw)
        same = _fields(o) == _fields(m)
        ok &= same
        print(f"[mutant_equivalent] compute_totals {label:42s} -> "
              f"{'all 7 fields IDENTICAL' if same else 'DIFFER (!! equivalence broken)'}")
    print()
    return ok


# ---------------------------------------------------------------------------
# Sandbox pytest runs (mutant installed as pricing.py)
# ---------------------------------------------------------------------------

def _run_pytest(sandbox: Path, test: str) -> tuple[bool, str]:
    """Run pytest inside the sandbox; return (passed, summary line)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=sandbox, capture_output=True, text=True,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    summary = lines[-1] if lines else f"(no output; rc={proc.returncode})"
    failed_names = [ln for ln in lines if ln.startswith("FAILED")]
    detail = summary + (" | " + "; ".join(failed_names[:3]) if failed_names else "")
    return proc.returncode == 0, detail


def _make_sandbox(mutant: str) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix=f"tss_mutant_demo_{mutant}_"))
    shutil.copy2(MUTANTS_DIR / f"{mutant}.py", sandbox / "pricing.py")
    shutil.copytree(TESTS_DIR, sandbox / "tests",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return sandbox


def main() -> int:
    print("=" * 78)
    print("TSS lab tasks 5-6: manual mutation demo  (chosen test case: "
          f"{CHOSEN_TEST})")
    print("=" * 78)
    all_ok = probe_distinguishing_inputs()

    overall = True
    for mutant, claim_chosen, claim_suite, claim_verdict in VARIANTS:
        sandbox = _make_sandbox(mutant)
        try:
            chosen_pass, chosen_info = _run_pytest(sandbox, CHOSEN_TEST)
            suite_pass, suite_info = _run_pytest(sandbox, "tests")
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

        chosen = "SURVIVED" if chosen_pass else "KILLED"
        suite = "SURVIVED" if suite_pass else "KILLED"
        if mutant == "mutant_equivalent":
            verdict = "EQUIVALENT" if (chosen_pass and suite_pass) else "NOT-EQUIVALENT (!!)"
        else:
            verdict = chosen  # verdict w.r.t. the chosen test, per the task statement

        print(f"=== {mutant} ===")
        print(f"  chosen test : {chosen:9s} ({chosen_info})")
        print(f"  full suite  : {suite:9s} ({suite_info})")
        print(f"  VERDICT {mutant}: {verdict}")

        match_chosen = chosen == claim_chosen
        match_suite = suite == claim_suite
        match_verdict = verdict == claim_verdict
        for label, m in (("chosen-test", match_chosen), ("full-suite", match_suite),
                         ("verdict", match_verdict)):
            print(f"  claim check ({label}): expected {claim_verdict if label == 'verdict' else (claim_chosen if label == 'chosen-test' else claim_suite)}"
                  f" -> {'MATCH' if m else 'MISMATCH'}")
            overall &= m
        print()

    print("=" * 78)
    print(f"DEMO RESULT: {'ALL CLAIMS MATCH (kill / survive / equivalence demonstrated)' if overall and all_ok else 'CLAIM MISMATCH - see above'}")
    print("=" * 78)
    return 0 if (overall and all_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
