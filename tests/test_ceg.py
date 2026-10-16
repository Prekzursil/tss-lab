"""CEG (cause–effect graph + decision table) suite for the pricing module.

Derived exclusively from ``SPEC.md`` §9 (CEG anchor) together with the fee
rules §5 (F1–F5), VAT rules §6 (V1–V5) and totals composition §7 (T1–T8).
The full derivation — causes, effects, the boolean graph, the struck-out
impossible combinations and the restricted-entry decision table — lives in
``tss/lab/docs/ceg.md``.

One test below = one feasible column of that decision table (columns 1–17);
combinations struck out as impossible in the derivation get no test.

Conventions:
* every test drives ``compute_totals`` (the only callable through which all
  four modelled decision outcomes — fee applied/0, VAT base composition,
  VAT 0/override/computed, totals clamping — are jointly observable);
* every test spells out the full input vector, so tests are independent
  (no shared fixtures, no ordering assumptions, no module state);
* assertions are exact ``Decimal`` equalities on the whole frozen
  ``PricingBreakdown`` plus the E10 invariant from T7:
  ``total == taxable + shipping + fee + vat`` and ``total >= 0``;
* ``rounding`` stays at its ``"half_up"`` default everywhere: rounding-mode
  behaviour belongs to the EP/BVA suites, not to the decision table.
"""

from decimal import Decimal

from pricing import PricingBreakdown, compute_totals


def assert_column(result: PricingBreakdown, *, subtotal: str, discount: str,
                  taxable: str, shipping: str, fee: str, vat: str,
                  total: str) -> None:
    """Assert the exact breakdown of one decision-table column (E10 incl.)."""
    assert result == PricingBreakdown(
        subtotal=Decimal(subtotal),
        discount=Decimal(discount),
        taxable_subtotal=Decimal(taxable),
        shipping=Decimal(shipping),
        fee=Decimal(fee),
        vat=Decimal(vat),
        total=Decimal(total),
    )
    # E10 (T7): the total is exactly the sum of the reported summands and is
    # non-negative by construction in every feasible column.
    assert result.total == (result.taxable_subtotal + result.shipping
                            + result.fee + result.vat)
    assert result.total >= 0


# --------------------------------------------------------------------------
# Fee decision: fee applied (flat / percent) or 0  (E1, E2, E3)
# --------------------------------------------------------------------------

def test_col_01_fee_flat_applied():
    """Column 1: C1∧C2∧¬C3 → E2 flat fee; also the E8 computed-VAT frame."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # base = 100.00 + 10.00 + 5.00 = 115.00 → vat = 11.50
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="11.50", total="126.50")


def test_col_02_fee_percent_applied():
    """Column 2: C1∧C2∧C3 → E3 percent fee (7 % of the taxable subtotal)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="percent",
        fee_value=Decimal("7"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # fee = 100.00 * 7 / 100 = 7.00; base = 117.00 → vat = 11.70
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="7.00",
                  vat="11.70", total="128.70")


def test_col_03_fee_zero_when_disabled():
    """Column 3: ¬C1 → E1 fee 0.00; every other fee input (C2=T) ignored."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=False,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # fee = 0.00 → base = 110.00 → vat = 11.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="0.00",
                  vat="11.00", total="121.00")


def test_col_04_fee_zero_when_value_nonpositive():
    """Column 4: C1∧¬C2 → E1 fee 0.00 (negative fee_value never charged)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("-3.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # fee = 0.00 → base = 110.00 → vat = 11.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="0.00",
                  vat="11.00", total="121.00")


# --------------------------------------------------------------------------
# VAT base composition: taxable [+ shipping if C6∧C12] [+ fee if C7∧fee>0]
# --------------------------------------------------------------------------

def test_col_05_vat_base_taxable_only():
    """Column 5: C6=F, C7=F → base = taxable alone."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=False,
        vat_override=None,
    )
    # base = 100.00 → vat = 10.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="10.00", total="125.00")


def test_col_06_vat_base_plus_shipping():
    """Column 6: C6∧C12 → base = taxable + shipping (fee excluded)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=False,
        vat_override=None,
    )
    # base = 110.00 → vat = 11.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="11.00", total="126.00")


def test_col_07_vat_base_plus_fee():
    """Column 7: C7∧fee>0 → base = taxable + fee (shipping excluded)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # base = 105.00 → vat = 10.50
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="10.50", total="125.50")


def test_col_08_shipping_flag_true_but_nonpositive_shipping_contributes_nothing():
    """Column 8: C6=T with C12=F → shipping ≤ 0 reports 0.00 (T4) and the
    AND-gate C6∧C12 adds nothing to the VAT base."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("-10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=False,
        vat_override=None,
    )
    # shipping_q = 0.00; base = 100.00 + 0.00 → vat = 10.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="0.00", fee="5.00",
                  vat="10.00", total="115.00")


def test_col_09_fee_flag_true_but_zero_fee_contributes_nothing():
    """Column 9: C7=T with fee=0 (¬C2) → the AND-gate C7∧(fee>0) adds
    nothing to the VAT base."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("0.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=False,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # fee = 0.00 (F2); base = 100.00 + 0.00 → vat = 10.00;
    # total = 100 + 10 + 0 + 10 = 120.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="0.00",
                  vat="10.00", total="120.00")


# --------------------------------------------------------------------------
# VAT resolution: 0 (disabled / clamped override / rate / base) vs override
# vs computed  (E4, E5, E6, E7, E8)
# --------------------------------------------------------------------------

def test_col_10_vat_disabled_override_ignored():
    """Column 10: ¬C4 → E4 vat 0.00; a positive override (C9∧C10) present
    in the input is nevertheless ignored (T6 arm 1)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=False,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=Decimal("99.99"),
    )
    # vat = 0.00 despite override 99.99; total = 100 + 10 + 5 + 0
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="0.00", total="115.00")


def test_col_11_vat_override_positive_wins():
    """Column 11: C4∧C9∧C10 → E6 vat = override; rate and apply flags are
    present-and-ignored (computed value would have been 11.50)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=Decimal("8.75"),
    )
    # vat = 8.75 (not 11.50); total = 100 + 10 + 5 + 8.75
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="8.75", total="123.75")


def test_col_12_vat_override_nonpositive_clamped():
    """Column 12: C4∧C9∧¬C10 → E5 vat 0.00 (negative override clamps to
    zero; positive rate and positive base are ignored)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=Decimal("-8.75"),
    )
    # vat = max(0, -8.75) = 0.00; total = 100 + 10 + 5 + 0
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="0.00", total="115.00")


def test_col_13_vat_zero_when_rate_nonpositive():
    """Column 13: C4∧¬C9∧¬C5 → E7 vat 0.00 via V2 (rate = 0) even though
    the composed base is positive (115.00)."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("0"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # rate ≤ 0 → vat = 0.00
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="0.00", total="115.00")


def test_col_14_vat_zero_when_base_zero_and_taxable_floored():
    """Column 14: C4∧¬C9∧C5∧¬C8 → E7 vat 0.00 via V4 (base = 0). The base
    is zero because C11∧X2 floors the taxable subtotal at 0.00 (E9), the
    percent fee follows the floored taxable (E3 value 0.00) and shipping is
    0.00 — so both apply flags are true yet add nothing."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("250.00"),
        shipping=Decimal("0.00"),
        fee_enabled=True,
        fee_type="percent",
        fee_value=Decimal("7"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # taxable = max(0, 100.00 - 250.00) = 0.00; fee = 0% of 0 = 0.00;
    # base = 0 → vat = 0.00; total = 0; discount is reported as 250.00
    # (the excess is not refunded anywhere else — T3).
    assert_column(result, subtotal="100.00", discount="250.00",
                  taxable="0.00", shipping="0.00", fee="0.00",
                  vat="0.00", total="0.00")


# --------------------------------------------------------------------------
# Totals clamping: discount/shipping contribution, taxable floor, total sign
# --------------------------------------------------------------------------

def test_col_15_negative_discount_reports_zero():
    """Column 15: ¬C11 → the reported discount is 0.00 (T2: a non-positive
    discount contributes nothing) and the taxable subtotal is unaffected."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("-20.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # discount ≤ 0 → 0.00; taxable = 100.00; same arithmetic as column 1
    assert_column(result, subtotal="100.00", discount="0.00",
                  taxable="100.00", shipping="10.00", fee="5.00",
                  vat="11.50", total="126.50")


def test_col_16_positive_discount_below_subtotal_reduces_taxable():
    """Column 16: C11 with discount < subtotal → no floor (X2=F): the
    taxable subtotal is reduced and the fee/VAT follow the reduced base."""
    result = compute_totals(
        subtotal=Decimal("100.00"),
        discount=Decimal("25.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # taxable = 75.00; base = 75 + 10 + 5 = 90.00 → vat = 9.00;
    # total = 75 + 10 + 5 + 9 = 99.00
    assert_column(result, subtotal="100.00", discount="25.00",
                  taxable="75.00", shipping="10.00", fee="5.00",
                  vat="9.00", total="99.00")


def test_col_17_negative_subtotal_reported_as_is_taxable_floored_total_nonnegative():
    """Column 17: X1 → the subtotal is reported as-is (negative, T1) yet the
    taxable floors at 0.00 (E9 via X2 with ¬C11), the flat fee is still
    charged, VAT is computed on the residual positive base, and the total
    stays non-negative (T7)."""
    result = compute_totals(
        subtotal=Decimal("-50.00"),
        discount=Decimal("0.00"),
        shipping=Decimal("10.00"),
        fee_enabled=True,
        fee_type="flat",
        fee_value=Decimal("5.00"),
        vat_enabled=True,
        vat_rate_percent=Decimal("10"),
        vat_apply_to_shipping=True,
        vat_apply_to_fee=True,
        vat_override=None,
    )
    # subtotal reported -50.00 (no clamp); taxable = max(0, -50.00) = 0.00;
    # fee = 5.00 (flat, independent of the floored taxable);
    # base = 0 + 10 + 5 = 15.00 → vat = 1.50; total = 16.50 ≥ 0
    assert_column(result, subtotal="-50.00", discount="0.00",
                  taxable="0.00", shipping="10.00", fee="5.00",
                  vat="1.50", total="16.50")
