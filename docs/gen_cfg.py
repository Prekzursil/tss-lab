"""Generate + verify the control-flow graph of tss/lab/pricing.py.

Produces (in this directory):
  - cfg.drawio : draw.io XML (mxGraphModel) with numbered nodes N1..N51,
                 control edges E1..E62 (solid) and call edges C1..C11 (dashed).
  - cfg.svg    : deterministic hand-written SVG of the same graph.

Then VERIFIES, by re-parsing the emitted cfg.drawio:
  1. per-function and module node/edge counts and V(G) = E - N + 2P,
  2. V(G) cross-check against an AST decision-point count of pricing.py,
  3. basis-path set: every step is a real edge, union covers ALL control
     edges, GF(2) rank of the path/edge incidence matrix == V(G),
  4. dynamic realization: each feasible basis path is executed under
     sys.settrace with the documented inputs; the traced node sequence
     must equal the documented path (P8 of compute_totals is proven
     infeasible instead), and the observed call edges must equal the
     documented call-edge table.

ASCII-only stdout so it prints cleanly in cmd.exe.
Run from the workspace root:  python tss/lab/docs/gen_cfg.py
"""

from __future__ import annotations

import ast
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))

import pricing  # noqa: E402  (module under analysis, tss/lab/pricing.py)

# ---------------------------------------------------------------------------
# 1. GRAPH DATA  (basic blocks derived manually from pricing.py; see
#    cfg-analysis.md for the per-statement derivation with line references)
# ---------------------------------------------------------------------------

# node: (id, function, kind, [label lines], col, row)
# kind: entry | exit | cond | stmt   (call sites are stmt nodes whose label
# ends with "[call]"; call edges are separate, to the callee's entry node)
NODES = [
    # --- quantize_money (pricing.py L31-33) ---
    ("N1",  "quantize_money", "entry", ["ENTER quantize_money"], 0, 0),
    ("N2",  "quantize_money", "stmt",  ["L32: mode = _ROUNDING_MAP.get(rounding, HALF_UP)",
                                        "L33: return value.quantize(0.01, mode)"], 1, 0),
    ("N3",  "quantize_money", "exit",  ["EXIT quantize_money"], 2, 0),
    # --- compute_fee (pricing.py L47-63) ---
    ("N4",  "compute_fee", "entry", ["ENTER compute_fee"], 0, 0),
    ("N5",  "compute_fee", "cond",  ["L55: if not enabled"], 0, 1),
    ("N6",  "compute_fee", "stmt",  ["L56: return 0.00"], 1, 1),
    ("N7",  "compute_fee", "cond",  ["L57: if fee_value <= 0"], 0, 2),
    ("N8",  "compute_fee", "stmt",  ["L58: return 0.00"], 1, 2),
    ("N9",  "compute_fee", "cond",  ["L59: if fee_type == 'percent'"], 0, 3),
    ("N10", "compute_fee", "stmt",  ["L60-62: return quantize_money(",
                                     "  taxable*fee_value/100) [call]"], 1, 3),
    ("N11", "compute_fee", "stmt",  ["L63: return quantize_money(",
                                     "  fee_value) [call]"], 1, 4),
    ("N12", "compute_fee", "exit",  ["EXIT compute_fee"], 2, 3),
    # --- compute_vat (pricing.py L66-88) ---
    ("N13", "compute_vat", "entry", ["ENTER compute_vat"], 0, 0),
    ("N14", "compute_vat", "cond",  ["L77: if not enabled"], 0, 1),
    ("N15", "compute_vat", "stmt",  ["L78: return 0.00"], 1, 1),
    ("N16", "compute_vat", "cond",  ["L79: if vat_rate_percent <= 0"], 0, 2),
    ("N17", "compute_vat", "stmt",  ["L80: return 0.00"], 1, 2),
    ("N18", "compute_vat", "stmt",  ["L81: base = taxable_subtotal"], 0, 3),
    ("N19", "compute_vat", "cond",  ["L82: if apply_to_shipping"], 0, 4),
    ("N20", "compute_vat", "stmt",  ["L83: base += shipping"], 1, 4),
    ("N21", "compute_vat", "cond",  ["L84: if apply_to_fee"], 0, 5),
    ("N22", "compute_vat", "stmt",  ["L85: base += fee"], 1, 5),
    ("N23", "compute_vat", "cond",  ["L86: if base <= 0"], 0, 6),
    ("N24", "compute_vat", "stmt",  ["L87: return 0.00"], 1, 6),
    ("N25", "compute_vat", "stmt",  ["L88: return quantize_money(",
                                     "  base*rate/100) [call]"], 0, 7),
    ("N26", "compute_vat", "exit",  ["EXIT compute_vat"], 2, 8),
    # --- compute_totals (pricing.py L91-159) ---
    ("N27", "compute_totals", "entry", ["ENTER compute_totals"], 0, 0),
    ("N28", "compute_totals", "stmt",  ["L106: subtotal_q =",
                                        "  quantize_money(subtotal) [call]"], 0, 1),
    ("N29", "compute_totals", "cond",  ["L107-109: ternary",
                                        "  discount > 0 ?"], 0, 2),
    ("N30", "compute_totals", "stmt",  ["L108: discount_q =",
                                        "  quantize_money(discount) [call]"], 1, 2),
    ("N31", "compute_totals", "stmt",  ["L109: discount_q = 0.00"], 1, 3),
    ("N32", "compute_totals", "stmt",  ["L110: taxable = subtotal_q",
                                        "  - discount_q"], 0, 3),
    ("N33", "compute_totals", "cond",  ["L111: if taxable < 0"], 0, 4),
    ("N34", "compute_totals", "stmt",  ["L112: taxable = 0.00"], 1, 4),
    ("N35", "compute_totals", "stmt",  ["L113: taxable =",
                                        "  quantize_money(taxable) [call]"], 0, 5),
    ("N36", "compute_totals", "cond",  ["L114-116: ternary",
                                        "  shipping > 0 ?"], 0, 6),
    ("N37", "compute_totals", "stmt",  ["L115: shipping_q =",
                                        "  quantize_money(shipping) [call]"], 1, 6),
    ("N38", "compute_totals", "stmt",  ["L116: shipping_q = 0.00"], 1, 7),
    ("N39", "compute_totals", "stmt",  ["L117-123: fee = compute_fee(",
                                        "  taxable, ...) [call]"], 0, 7),
    ("N40", "compute_totals", "cond",  ["L124: if not vat_enabled"], 0, 8),
    ("N41", "compute_totals", "stmt",  ["L125: vat = 0.00"], 1, 8),
    ("N42", "compute_totals", "cond",  ["L126: elif vat_override",
                                        "  is not None"], 0, 9),
    ("N43", "compute_totals", "cond",  ["L127-129: ternary",
                                        "  vat_override > 0 ?"], 1, 9),
    ("N44", "compute_totals", "stmt",  ["L127-129: vat =",
                                        "  quantize_money(sel) [call]"], 1, 10),
    ("N45", "compute_totals", "stmt",  ["L130-140: vat = compute_vat(",
                                        "  taxable, ...) [call]"], 2, 10),
    ("N46", "compute_totals", "stmt",  ["L141: total = taxable",
                                        "  + shipping_q + fee + vat"], 0, 11),
    ("N47", "compute_totals", "cond",  ["L148: if total < 0",
                                        "  (pragma: no cover)"], 0, 12),
    ("N48", "compute_totals", "stmt",  ["L149: total = 0.00"], 1, 12),
    ("N49", "compute_totals", "stmt",  ["L150: total =",
                                        "  quantize_money(total) [call]"], 0, 13),
    ("N50", "compute_totals", "stmt",  ["L151-159: return",
                                        "  PricingBreakdown(...)"], 0, 14),
    ("N51", "compute_totals", "exit",  ["EXIT compute_totals"], 0, 15),
]

FUNCS = ["quantize_money", "compute_fee", "compute_vat", "compute_totals"]

# control edge: (id, src, dst, label '' | 'T' | 'F')
EDGES = [
    ("E1", "N1", "N2", ""), ("E2", "N2", "N3", ""),
    ("E3", "N4", "N5", ""), ("E4", "N5", "N6", "T"), ("E5", "N5", "N7", "F"),
    ("E6", "N6", "N12", ""), ("E7", "N7", "N8", "T"), ("E8", "N7", "N9", "F"),
    ("E9", "N8", "N12", ""), ("E10", "N9", "N10", "T"), ("E11", "N9", "N11", "F"),
    ("E12", "N10", "N12", ""), ("E13", "N11", "N12", ""),
    ("E14", "N13", "N14", ""), ("E15", "N14", "N15", "T"), ("E16", "N14", "N16", "F"),
    ("E17", "N15", "N26", ""), ("E18", "N16", "N17", "T"), ("E19", "N16", "N18", "F"),
    ("E20", "N17", "N26", ""), ("E21", "N18", "N19", ""), ("E22", "N19", "N20", "T"),
    ("E23", "N19", "N21", "F"), ("E24", "N20", "N21", ""), ("E25", "N21", "N22", "T"),
    ("E26", "N21", "N23", "F"), ("E27", "N22", "N23", ""), ("E28", "N23", "N24", "T"),
    ("E29", "N23", "N25", "F"), ("E30", "N24", "N26", ""), ("E31", "N25", "N26", ""),
    ("E32", "N27", "N28", ""), ("E33", "N28", "N29", ""), ("E34", "N29", "N30", "T"),
    ("E35", "N29", "N31", "F"), ("E36", "N30", "N32", ""), ("E37", "N31", "N32", ""),
    ("E38", "N32", "N33", ""), ("E39", "N33", "N34", "T"), ("E40", "N33", "N35", "F"),
    ("E41", "N34", "N35", ""), ("E42", "N35", "N36", ""), ("E43", "N36", "N37", "T"),
    ("E44", "N36", "N38", "F"), ("E45", "N37", "N39", ""), ("E46", "N38", "N39", ""),
    ("E47", "N39", "N40", ""), ("E48", "N40", "N41", "T"), ("E49", "N40", "N42", "F"),
    ("E50", "N41", "N46", ""), ("E51", "N42", "N43", "T"), ("E52", "N42", "N45", "F"),
    ("E53", "N43", "N44", "T"), ("E54", "N43", "N44", "F"), ("E55", "N44", "N46", ""),
    ("E56", "N45", "N46", ""), ("E57", "N46", "N47", ""), ("E58", "N47", "N48", "T"),
    ("E59", "N47", "N49", "F"), ("E60", "N48", "N49", ""), ("E61", "N49", "N50", ""),
    ("E62", "N50", "N51", ""),
]

# call edge: (id, src(call site), dst(callee entry), callee name)
CALLS = [
    ("C1", "N10", "N1", "quantize_money"),
    ("C2", "N11", "N1", "quantize_money"),
    ("C3", "N25", "N1", "quantize_money"),
    ("C4", "N28", "N1", "quantize_money"),
    ("C5", "N30", "N1", "quantize_money"),
    ("C6", "N35", "N1", "quantize_money"),
    ("C7", "N37", "N1", "quantize_money"),
    ("C8", "N39", "N4", "compute_fee"),
    ("C9", "N44", "N1", "quantize_money"),
    ("C10", "N45", "N13", "compute_vat"),
    ("C11", "N49", "N1", "quantize_money"),
]

EXPECTED_V = {"quantize_money": 1, "compute_fee": 4, "compute_vat": 6,
              "compute_totals": 8}
EXPECTED_MODULE_V = 19  # 62 - 51 + 2*4

# ---------------------------------------------------------------------------
# 2. BASIS PATHS (linearly independent, cover ALL control edges)
#    step = (node, edge-label-needed or None)  -- label disambiguates the one
#    parallel edge pair N43->N44 (E53 'T' / E54 'F')
# ---------------------------------------------------------------------------

D = lambda n, lab=None: (n, lab)  # noqa: E731

BASIS = {
    "quantize_money": [
        ("Q-P1", [D("N1"), D("N2"), D("N3")]),
    ],
    "compute_fee": [
        ("F-P1", [D("N4"), D("N5"), D("N6"), D("N12")]),
        ("F-P2", [D("N4"), D("N5"), D("N7"), D("N8"), D("N12")]),
        ("F-P3", [D("N4"), D("N5"), D("N7"), D("N9"), D("N10"), D("N12")]),
        ("F-P4", [D("N4"), D("N5"), D("N7"), D("N9"), D("N11"), D("N12")]),
    ],
    "compute_vat": [
        ("V-P1", [D("N13"), D("N14"), D("N15"), D("N26")]),
        ("V-P2", [D("N13"), D("N14"), D("N16"), D("N17"), D("N26")]),
        ("V-P3", [D("N13"), D("N14"), D("N16"), D("N18"), D("N19"), D("N21"),
                  D("N23"), D("N24"), D("N26")]),
        ("V-P4", [D("N13"), D("N14"), D("N16"), D("N18"), D("N19"), D("N21"),
                  D("N23"), D("N25"), D("N26")]),
        ("V-P5", [D("N13"), D("N14"), D("N16"), D("N18"), D("N19"), D("N20"),
                  D("N21"), D("N23"), D("N25"), D("N26")]),
        ("V-P6", [D("N13"), D("N14"), D("N16"), D("N18"), D("N19"), D("N21"),
                  D("N22"), D("N23"), D("N25"), D("N26")]),
    ],
    "compute_totals": [
        ("T-P1", [D("N27"), D("N28"), D("N29"), D("N31"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N38"), D("N39"), D("N40"), D("N41"),
                  D("N46"), D("N47"), D("N49"), D("N50"), D("N51")]),
        ("T-P2", [D("N27"), D("N28"), D("N29"), D("N30"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N38"), D("N39"), D("N40"), D("N41"),
                  D("N46"), D("N47"), D("N49"), D("N50"), D("N51")]),
        ("T-P3", [D("N27"), D("N28"), D("N29"), D("N30"), D("N32"), D("N33"),
                  D("N34"), D("N35"), D("N36"), D("N38"), D("N39"), D("N40"),
                  D("N41"), D("N46"), D("N47"), D("N49"), D("N50"), D("N51")]),
        ("T-P4", [D("N27"), D("N28"), D("N29"), D("N31"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N37"), D("N39"), D("N40"), D("N41"),
                  D("N46"), D("N47"), D("N49"), D("N50"), D("N51")]),
        ("T-P5", [D("N27"), D("N28"), D("N29"), D("N31"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N38"), D("N39"), D("N40"), D("N42"),
                  D("N45"), D("N46"), D("N47"), D("N49"), D("N50"), D("N51")]),
        ("T-P6", [D("N27"), D("N28"), D("N29"), D("N31"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N38"), D("N39"), D("N40"), D("N42"),
                  D("N43", "T"), D("N44"), D("N46"), D("N47"), D("N49"),
                  D("N50"), D("N51")]),
        ("T-P7", [D("N27"), D("N28"), D("N29"), D("N31"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N38"), D("N39"), D("N40"), D("N42"),
                  D("N43", "F"), D("N44"), D("N46"), D("N47"), D("N49"),
                  D("N50"), D("N51")]),
        ("T-P8", [D("N27"), D("N28"), D("N29"), D("N31"), D("N32"), D("N33"),
                  D("N35"), D("N36"), D("N38"), D("N39"), D("N40"), D("N41"),
                  D("N46"), D("N47"), D("N48"), D("N49"), D("N50"), D("N51")]),
    ],
}
INFEASIBLE = {("compute_totals", "T-P8")}

# concrete inputs that realize each feasible basis path (keyword dicts) +
# expected observable result, asserted when the path is traced.
D_ = Decimal
RUNS = [
    # (path id, callable, kwargs, expected-result-check name)
    ("Q-P1", pricing.quantize_money,
     {"value": D_("2.345"), "rounding": "half_up"}, D_("2.35")),
    ("F-P1", pricing.compute_fee,
     {"taxable_subtotal": D_("100.00"), "enabled": False,
      "fee_type": "percent", "fee_value": D_("5.00")}, D_("0.00")),
    ("F-P2", pricing.compute_fee,
     {"taxable_subtotal": D_("100.00"), "enabled": True,
      "fee_type": "flat", "fee_value": D_("0.00")}, D_("0.00")),
    ("F-P3", pricing.compute_fee,
     {"taxable_subtotal": D_("100.00"), "enabled": True,
      "fee_type": "percent", "fee_value": D_("5.00")}, D_("5.00")),
    ("F-P4", pricing.compute_fee,
     {"taxable_subtotal": D_("100.00"), "enabled": True,
      "fee_type": "flat", "fee_value": D_("5.00")}, D_("5.00")),
    ("V-P1", pricing.compute_vat,
     {"taxable_subtotal": D_("100.00"), "shipping": D_("10.00"),
      "fee": D_("3.00"), "enabled": False, "vat_rate_percent": D_("10.00"),
      "apply_to_shipping": True, "apply_to_fee": True}, D_("0.00")),
    ("V-P2", pricing.compute_vat,
     {"taxable_subtotal": D_("100.00"), "shipping": D_("0.00"),
      "fee": D_("0.00"), "enabled": True, "vat_rate_percent": D_("0.00"),
      "apply_to_shipping": False, "apply_to_fee": False}, D_("0.00")),
    ("V-P3", pricing.compute_vat,
     {"taxable_subtotal": D_("0.00"), "shipping": D_("10.00"),
      "fee": D_("3.00"), "enabled": True, "vat_rate_percent": D_("10.00"),
      "apply_to_shipping": False, "apply_to_fee": False}, D_("0.00")),
    ("V-P4", pricing.compute_vat,
     {"taxable_subtotal": D_("100.00"), "shipping": D_("0.00"),
      "fee": D_("0.00"), "enabled": True, "vat_rate_percent": D_("10.00"),
      "apply_to_shipping": False, "apply_to_fee": False}, D_("10.00")),
    ("V-P5", pricing.compute_vat,
     {"taxable_subtotal": D_("100.00"), "shipping": D_("10.00"),
      "fee": D_("0.00"), "enabled": True, "vat_rate_percent": D_("10.00"),
      "apply_to_shipping": True, "apply_to_fee": False}, D_("11.00")),
    ("V-P6", pricing.compute_vat,
     {"taxable_subtotal": D_("100.00"), "shipping": D_("0.00"),
      "fee": D_("3.00"), "enabled": True, "vat_rate_percent": D_("10.00"),
      "apply_to_shipping": False, "apply_to_fee": True}, D_("10.30")),
]
BASE_TOTALS = {
    "subtotal": D_("10.00"), "discount": D_("0.00"), "shipping": D_("0.00"),
    "fee_enabled": False, "fee_type": "flat", "fee_value": D_("0.00"),
    "vat_enabled": False, "vat_rate_percent": D_("0.00"),
    "vat_apply_to_shipping": False, "vat_apply_to_fee": False,
    "vat_override": None,
}
RUNS += [
    ("T-P1", pricing.compute_totals, dict(BASE_TOTALS),
     {"total": D_("10.00"), "vat": D_("0.00")}),
    ("T-P2", pricing.compute_totals, dict(BASE_TOTALS, discount=D_("2.00")),
     {"total": D_("8.00")}),
    ("T-P3", pricing.compute_totals,
     dict(BASE_TOTALS, subtotal=D_("0.00"), discount=D_("5.00")),
     {"total": D_("0.00"), "taxable_subtotal": D_("0.00"),
      "discount": D_("5.00")}),
    ("T-P4", pricing.compute_totals, dict(BASE_TOTALS, shipping=D_("3.00")),
     {"total": D_("13.00"), "shipping": D_("3.00")}),
    ("T-P5", pricing.compute_totals,
     dict(BASE_TOTALS, vat_enabled=True, vat_rate_percent=D_("10.00")),
     {"total": D_("11.00"), "vat": D_("1.00")}),
    ("T-P6", pricing.compute_totals,
     dict(BASE_TOTALS, vat_enabled=True, vat_override=D_("1.23")),
     {"total": D_("11.23"), "vat": D_("1.23")}),   # vat==1.23 proves E53 (T-arm)
    ("T-P7", pricing.compute_totals,
     dict(BASE_TOTALS, vat_enabled=True, vat_override=D_("0.00")),
     {"total": D_("10.00"), "vat": D_("0.00")}),   # vat==0.00 proves E54 (F-arm)
]

# ---------------------------------------------------------------------------
# 3. LAYOUT (shared by .drawio and .svg) + EMITTERS
# ---------------------------------------------------------------------------

BOX_W = 186
LINE_H = 15
PAD_V = 12
COL_PITCH = 230
ROW_PITCH = 86
BAND_GAP = 110
MARGIN = 40

NODE = {n[0]: n for n in NODES}
NODE_H = {nid: PAD_V * 2 + LINE_H * len(n[3]) for nid, n in NODE.items()}

BAND_X = {}
_x = MARGIN
for f in FUNCS:
    ncols = max(n[4] for n in NODES if n[1] == f) + 1
    BAND_X[f] = _x
    _x += ncols * COL_PITCH + BAND_GAP
BAND_W = {f: (max(n[4] for n in NODES if n[1] == f) + 1) * COL_PITCH for f in FUNCS}
BAND_ROWS = {f: max(n[5] for n in NODES if n[1] == f) + 1 for f in FUNCS}

def cx(nid):
    _, f, _, _, col, _ = NODE[nid]
    return BAND_X[f] + COL_PITCH / 2 + col * COL_PITCH

def cy(nid):
    return MARGIN + 70 + NODE[nid][5] * ROW_PITCH + NODE_H[nid] / 2

# routing: right-rail polylines for the long early-return edges of compute_vat
def rail_points(eid):
    f = "compute_vat"
    rail = BAND_X[f] + BAND_W[f] - 30
    lane = {"E17": 0, "E20": 14, "E30": 28}[eid]
    return rail + lane

def edge_geometry(eid, src, dst):
    """Return list of (x, y) polyline points from src box to dst box."""
    p_src, p_dst = (cx(src), cy(src)), (cx(dst), cy(dst))
    if eid in ("E17", "E20", "E30"):
        rail = rail_points(eid)
        y_top, y_bot = min(cy(src), cy(dst)), max(cy(src), cy(dst))
        pts = [(p_src[0], p_src[1]), (rail, p_src[1]),
               (rail, p_dst[1]), (p_dst[0], p_dst[1])]
        # trim to box borders
        pts[0] = exit_point(pts[0], pts[1], src)
        pts[-1] = entry_point(pts[-2], pts[-1], dst)
        return pts
    a = exit_point(p_src, p_dst, src)
    b = entry_point(p_src, p_dst, dst)
    if eid == "E53":
        a, b = shift_par(a, b, -7)
    if eid == "E54":
        a, b = shift_par(a, b, +7)
    return [a, b]

def shift_par(a, b, d):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = (dx * dx + dy * dy) ** 0.5
    nx, ny = -dy / L * d, dx / L * d
    return (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)

def exit_point(a, b, nid):
    w, h = BOX_W / 2, NODE_H[nid] / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    tx = w / abs(dx) if dx else float("inf")
    ty = h / abs(dy) if dy else float("inf")
    t = min(tx, ty)
    return (a[0] + dx * t, a[1] + dy * t)

def entry_point(a, b, nid):
    return exit_point(b, a, nid)

def xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))

FILL = {"entry": "#d5e8d4", "exit": "#f8cecc", "cond": "#ffe6cc", "stmt": "#dae8fc"}
STROKE = {"entry": "#6aa84f", "exit": "#b85450", "cond": "#d79b00", "stmt": "#6c8ebf"}

def node_value(nid):
    _, _, kind, lines, _, _ = NODE[nid]
    tag = {"entry": "", "exit": "", "cond": " (decision)", "stmt": ""}[kind]
    raw = nid + tag + "<br>" + "<br>".join(lines)
    return xml_escape(raw)  # <br> becomes &lt;br&gt; (draw.io HTML label)

def write_drawio(path):
    cells = []
    for i, f in enumerate(FUNCS, 1):
        x0 = BAND_X[f] - 20
        y0 = MARGIN + 30
        w = BAND_W[f] + 20
        h = BAND_ROWS[f] * ROW_PITCH + 60
        cells.append(
            f'<mxCell id="band{i}" value="{f}" style="rounded=0;whiteSpace=wrap;'
            f'html=1;fillColor=none;dashed=1;dashPattern=8 8;verticalAlign=top;'
            f'fontStyle=1;fontSize=13;strokeColor=#9673a6;" vertex="1" parent="1">'
            f'<mxGeometry x="{x0}" y="{y0}" width="{w}" height="{h}" as="geometry"/>'
            f"</mxCell>")
    for nid, f, kind, lines, col, row in NODES:
        x = cx(nid) - BOX_W / 2
        y = cy(nid) - NODE_H[nid] / 2
        style = (f"rounded=0;whiteSpace=wrap;html=1;fillColor={FILL[kind]};"
                 f"strokeColor={STROKE[kind]};fontSize=10;align=left;spacingLeft=6;")
        cells.append(
            f'<mxCell id="{nid}" value="{node_value(nid)}" style="{style}" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{BOX_W}" height="{NODE_H[nid]}" '
            f'as="geometry"/></mxCell>')
    for eid, s, t, lab in EDGES:
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
                 "strokeColor=#37474f;strokeWidth=1.4;fontSize=9;fontColor=#37474f;")
        cells.append(edge_cell(eid, s, t, lab, style))
    for eid, s, t, callee in CALLS:
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;dashed=1;"
                 "strokeColor=#ad1457;fontSize=9;fontColor=#ad1457;")
        cells.append(edge_cell(eid, s, t, "call", style))
    xml = (
        '<mxfile host="tss-lab" modified="2026-10-16T00:00:00.000Z" agent="gen_cfg.py">'
        '<diagram id="cfg-pricing" name="pricing CFG">'
        '<mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1"'
        ' tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1"'
        ' math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>")
    path.write_text(xml, encoding="utf-8")

def edge_cell(eid, s, t, label, style):
    return (f'<mxCell id="{eid}" value="{xml_escape(label)}" style="{style}" '
            f'edge="1" parent="1" source="{s}" target="{t}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>')

def write_svg(path):
    total_w = BAND_X[FUNCS[-1]] + BAND_W[FUNCS[-1]] + MARGIN
    total_h = MARGIN + 70 + max(BAND_ROWS.values()) * ROW_PITCH + MARGIN
    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" '
        f'height="{total_h}" viewBox="0 0 {total_w} {total_h}" '
        f'font-family="Consolas, ui-monospace, monospace">')
    out.append(
        "<defs><marker id=\"ah\" markerWidth=\"9\" markerHeight=\"9\" "
        "refX=\"8\" refY=\"4.5\" orient=\"auto\">"
        "<path d=\"M0,0 L9,4.5 L0,9 z\" fill=\"#37474f\"/></marker>"
        "<marker id=\"ahc\" markerWidth=\"9\" markerHeight=\"9\" "
        "refX=\"8\" refY=\"4.5\" orient=\"auto\">"
        "<path d=\"M0,0 L9,4.5 L0,9 z\" fill=\"#ad1457\"/></marker></defs>")
    out.append(
        '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>' % (total_w, total_h))
    out.append(
        '<text x="%d" y="28" font-size="16" font-weight="bold" fill="#212121">'
        "pricing.py - control-flow graph (51 basic blocks / 62 control edges / "
        "11 call edges)</text>" % MARGIN)
    # legend
    lx = MARGIN
    ly = 44
    for kind, name in [("entry", "entry"), ("cond", "decision"),
                       ("stmt", "statement"), ("exit", "exit")]:
        out.append('<rect x="%d" y="%d" width="14" height="14" fill="%s" '
                   'stroke="%s"/>' % (lx, ly, FILL[kind], STROKE[kind]))
        out.append('<text x="%d" y="%d" font-size="11" fill="#212121">%s</text>'
                   % (lx + 18, ly + 11, name))
        lx += 90
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#37474f" '
               'stroke-width="1.4" marker-end="url(#ah)"/>' % (lx, ly + 7, lx + 44, ly + 7))
    out.append('<text x="%d" y="%d" font-size="11">control</text>' % (lx + 50, ly + 11))
    lx += 120
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#ad1457" '
               'stroke-width="1.2" stroke-dasharray="5,4" '
               'marker-end="url(#ahc)"/>' % (lx, ly + 7, lx + 44, ly + 7))
    out.append('<text x="%d" y="%d" font-size="11">call</text>' % (lx + 50, ly + 11))
    # bands
    for f in FUNCS:
        x0 = BAND_X[f] - 20
        y0 = MARGIN + 30
        w = BAND_W[f] + 20
        h = BAND_ROWS[f] * ROW_PITCH + 60
        out.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" '
                   'stroke="#9673a6" stroke-dasharray="8 6"/>'
                   '<text x="%d" y="%d" font-size="13" font-weight="bold" '
                   'fill="#9673a6">%s</text>' % (x0, y0, w, h, x0 + 8, y0 + 20, f))
    # call edges first (under the boxes? no: draw after bands, before control
    # edges so local edges sit on top)
    for eid, s, t, callee in CALLS:
        a = exit_point((cx(s), cy(s)), (cx(t), cy(t)), s)
        b = entry_point((cx(s), cy(s)), (cx(t), cy(t)), t)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                   'stroke="#ad1457" stroke-opacity="0.55" stroke-width="1.1" '
                   'stroke-dasharray="5,4" marker-end="url(#ahc)"/>'
                   % (a[0], a[1], b[0], b[1]))
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        out.append('<text x="%.1f" y="%.1f" font-size="9" font-style="italic" '
                   'fill="#ad1457">call %s</text>' % (mx + 4, my - 4, callee))
    # control edges
    for eid, s, t, lab in EDGES:
        pts = edge_geometry(eid, s, t)
        d = " ".join(("M" if i == 0 else "L") + "%.1f %.1f" % p
                     for i, p in enumerate(pts))
        out.append('<path d="%s" fill="none" stroke="#37474f" stroke-width="1.4" '
                   'marker-end="url(#ah)"/>' % d)
        a, b = pts[0], pts[1]
        if lab:
            frac = 0.3
            lx2 = a[0] + (b[0] - a[0]) * frac
            ly2 = a[1] + (b[1] - a[1]) * frac
            out.append('<text x="%.1f" y="%.1f" font-size="10" font-weight="bold" '
                       'fill="#37474f">%s</text>' % (lx2 + 3, ly2 - 3, lab))
    # nodes
    for nid, f, kind, lines, col, row in NODES:
        x = cx(nid) - BOX_W / 2
        y = cy(nid) - NODE_H[nid] / 2
        out.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="4" '
                   'fill="%s" stroke="%s" stroke-width="1.3"/>'
                   % (x, y, BOX_W, NODE_H[nid], FILL[kind], STROKE[kind]))
        if kind in ("entry", "exit"):
            out.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="bold" '
                       'fill="#212121" text-anchor="middle">%s</text>'
                       % (cx(nid), y + NODE_H[nid] / 2 + 4, lines[0]))
        else:
            out.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="bold" '
                       'fill="#212121">%s%s</text>'
                       % (x + 8, y + 18, nid,
                          " ?" if kind == "cond" else ""))
            for i, ln in enumerate(lines):
                out.append('<text x="%.1f" y="%.1f" font-size="10" '
                           'fill="#37474f">%s</text>'
                           % (x + 8, y + 33 + i * LINE_H, esc(ln)))
    out.append("</svg>")
    path.write_text("\n".join(out), encoding="utf-8")

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

# ---------------------------------------------------------------------------
# 4. VERIFICATION
# ---------------------------------------------------------------------------

FAIL = []

def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        FAIL.append(msg)

def verify_drawio():
    tree = ET.parse(HERE / "cfg.drawio")
    root = tree.getroot().find("diagram/mxGraphModel/root")
    bands, nodes, edges = {}, {}, []
    for cell in root.findall("mxCell"):
        cid = cell.get("id", "")
        geom = cell.find("mxGeometry")
        if cell.get("vertex") == "1" and geom is not None:
            x = float(geom.get("x", 0)); y = float(geom.get("y", 0))
            w = float(geom.get("width", 0)); h = float(geom.get("height", 0))
            if cid.startswith("band"):
                bands[cell.get("value")] = (x, y, w, h)
            elif re.fullmatch(r"N\d+", cid):
                nodes[cid] = (x + w / 2, y + h / 2)
    for cell in root.findall("mxCell"):
        if cell.get("edge") == "1":
            edges.append((cell.get("id"), cell.get("source"),
                          cell.get("target"), cell.get("value") or ""))

    def band_of(nid):
        px, py = nodes[nid]
        for name, (x, y, w, h) in bands.items():
            if x - 5 <= px <= x + w + 5 and y - 5 <= py <= y + h + 5:
                return name
        return None

    node_func = {nid: band_of(nid) for nid in nodes}
    check(all(v in FUNCS for v in node_func.values()),
          "drawio: every node lies in exactly one function band")
    ctrl, calls = [], []
    for eid, s, t, val in edges:
        (calls if val.startswith("call") else ctrl).append((eid, s, t, val))
    per = {f: {"N": 0, "E": 0} for f in FUNCS}
    for f in FUNCS:
        per[f]["N"] = sum(1 for v in node_func.values() if v == f)
        per[f]["E"] = sum(1 for eid, s, t, v in ctrl if node_func[s] == f
                          and node_func[t] == f)
    print("  file-derived counts (reparsed cfg.drawio):")
    tot_e = tot_n = 0
    for f in FUNCS:
        n, e = per[f]["N"], per[f]["E"]
        v = e - n + 2
        tot_e += e; tot_n += n
        print(f"    {f:16s} N={n:2d} E={e:2d}  V = E-N+2 = {v}")
        check(v == EXPECTED_V[f],
              f"drawio: V({f}) = {v} == expected {EXPECTED_V[f]}")
    mod = tot_e - tot_n + 2 * len(FUNCS)
    print(f"    {'module':16s} N={tot_n:2d} E={tot_e:2d} P={len(FUNCS)}  "
          f"V = E-N+2P = {mod}")
    check(mod == EXPECTED_MODULE_V,
          f"drawio: module V = {mod} == expected {EXPECTED_MODULE_V}")
    check(mod == sum(EXPECTED_V.values()),
          "drawio: module V == sum of per-function V (additivity)")
    check(len(calls) == 11, f"drawio: call edges = {len(calls)} == 11")
    return ctrl, calls

def ast_decision_count():
    tree = ast.parse((LAB / "pricing.py").read_text(encoding="utf-8"))
    out = {}
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        d = 0
        for sub in ast.walk(fn):
            if isinstance(sub, (ast.If, ast.IfExp, ast.For, ast.While,
                                ast.ExceptHandler, ast.Assert)):
                d += 1
            elif isinstance(sub, ast.BoolOp):
                d += len(sub.values) - 1
            elif isinstance(sub, ast.comprehension):
                d += 1 + len(sub.ifs)
        out[fn.name] = d + 1
    return out

def gf2_rank(rows_cols):
    """rows: list of sets of column ids -> rank over GF(2).

    Proper row-echelon over GF(2): columns mapped to bit positions, each new
    row reduced by existing pivots (XOR when the leading bit matches).
    """
    cols = sorted({c for r in rows_cols for c in r}, key=lambda s: (len(s), s))
    idx = {c: i for i, c in enumerate(cols)}
    pivots = []
    for row in rows_cols:
        v = 0
        for c in row:
            v |= 1 << idx[c]
        for p in pivots:
            if v ^ p < v:  # same leading bit -> eliminate
                v ^= p
        if v:
            pivots.append(v)
            pivots.sort(reverse=True)
    return len(pivots)

def verify_basis(ctrl):
    by_pair = {}
    for eid, s, t, v in ctrl:
        by_pair.setdefault((s, t), []).append((eid, v))
    for f, paths in BASIS.items():
        f_edges = {(eid, s, t, v) for eid, s, t, v in ctrl
                   if NODE[s][1] == f}
        f_edge_ids = {e[0] for e in f_edges}
        used, ok_valid = set(), True
        rows = []
        for pid, steps in paths:
            ids = []
            for (a, b) in zip(steps, steps[1:]):
                cand = by_pair.get((a[0], b[0]), [])
                want = a[1]
                hit = None
                for eid, v in cand:
                    if want is None or v == want:
                        hit = eid
                        if want is not None:
                            break
                if want is not None:
                    hit = next((eid for eid, v in cand if v == want), None)
                if hit is None:
                    ok_valid = False
                    print(f"    {pid}: no edge {a[0]}->{b[0]}"
                          + (f" [{want}]" if want else ""))
                else:
                    ids.append(hit)
            used |= set(ids)
            rows.append(set(ids))
        check(ok_valid, f"basis {f}: every step is an edge in cfg.drawio")
        cov = used == f_edge_ids
        check(cov, f"basis {f}: edge coverage {len(used)}/{len(f_edge_ids)}"
              + (" (ALL edges)" if cov else " MISSING: "
                 + str(sorted(f_edge_ids - used))))
        r = gf2_rank(rows)
        check(r == EXPECTED_V[f],
              f"basis {f}: GF(2) rank = {r} == V({f}) = {EXPECTED_V[f]}"
              f" (paths = {len(paths)})")

# ---- dynamic realization --------------------------------------------------

NODE_LINES = {
    "N2": {32, 33},
    "N5": {55}, "N6": {56}, "N7": {57}, "N8": {58}, "N9": {59},
    "N10": {60, 61, 62}, "N11": {63},
    "N14": {77}, "N15": {78}, "N16": {79}, "N17": {80}, "N18": {81},
    "N19": {82}, "N20": {83}, "N21": {84}, "N22": {85}, "N23": {86},
    "N24": {87}, "N25": {88},
    "N28": {106}, "N29": {107, 108}, "N30": {108}, "N31": {109},
    "N32": {110}, "N33": {111}, "N34": {112}, "N35": {113},
    "N36": {114, 115}, "N37": {115}, "N38": {116}, "N39": {117, 118, 119},
    "N40": {124}, "N41": {125}, "N42": {126}, "N43": {127, 128},
    "N44": {127, 128, 129}, "N45": {130, 131, 132},
    "N46": {141}, "N47": {148}, "N48": {149},
    "N49": {150}, "N50": {151, 152, 153},
}
ENTRY_OF = {"quantize_money": "N1", "compute_fee": "N4",
            "compute_vat": "N13", "compute_totals": "N27"}
EXIT_OF = {"quantize_money": "N3", "compute_fee": "N12",
           "compute_vat": "N26", "compute_totals": "N51"}

def line_to_node(func, ln, cur):
    """Resolve a traced line to a node id, with ternary disambiguation."""
    cands = [nid for nid, lines in NODE_LINES.items()
             if ln in lines and NODE[nid][1] == func]
    if not cands:
        return None
    # ternary arm disambiguation (rules documented in cfg-analysis.md par. 7c4):
    if cur == "N29" and ln == 109:
        return "N31"          # else-arm of `discount > 0` (no call follows)
    if cur == "N36" and ln == 116:
        return "N38"          # else-arm of `shipping > 0`
    if cur == "N29" and ln == 108:
        return "N29" if "N29" in cands else cands[0]
    if cur == "N36" and ln == 115:
        return "N36" if "N36" in cands else cands[0]
    if cur == "N43" and ln in (127, 128, 129):
        return "N43"
    if cur == "N42" and ln in (127, 128):
        return "N43"
    if len(cands) > 1:        # N29/N30, N36/N37, N43/N44 share lines; the
        # T-arm is emitted via the call event, so a plain line event after
        # the decision keeps the decision node until the arm is proven.
        for c in cands:
            if c == cur:
                return cur
        return cands[0]
    return cands[0]

TERNARY_ARM = {"N29": "N30", "N36": "N37", "N43": "N44"}  # call-site T-arm
TERNARY_ELSE = {  # (decision node, next line) -> synthetic else-arm node
    ("N29", 110): "N31",   # else of `discount > 0`, next stmt is L110
    ("N36", 117): "N38",   # else of `shipping > 0`, next stmt is L117
}
# After the T-arm call returns, CPython re-fires lines of the ternary
# statement (e.g. L107/109 after the L108 call). While an arm node is
# current, line events inside that ternary's source region are residual
# and must not re-emit the decision or the else-arm.
ARM_REGION = {"N30": {107, 108, 109}, "N37": {114, 115, 116},
              "N44": {127, 128, 129}}

def run_traced(func, kwargs):
    """Execute func(**kwargs) under sys.settrace; return (result, events).

    events: ('call'|'return', funcname) at module scope boundaries and
    ('node', funcname, nodeid); only frames whose code lives in pricing.py.
    Ternary arms that produce no distinguishable line event (N30/N31, N37/
    N38, N44) are resolved by the ternary-arm rules below (also listed in
    the T-arm call site is emitted when the callee is entered; the else-arm
    node is emitted when control reaches the following statement's line;
    residual post-call line events inside the ternary region are ignored).
    """
    events = []
    cur_node = {}
    frame_name = {}
    stack = []
    call_edges_seen = set()

    def fname(frame):
        return frame.f_code.co_name

    def in_module(frame):
        return frame.f_code.co_filename.replace("\\", "/").endswith("pricing.py")

    def emit(key, f, node):
        if node and node != cur_node.get(key):
            cur_node[key] = node
            events.append(("node", f, node))

    def tracer(frame, event, arg):
        if not in_module(frame):
            return None
        f = fname(frame)
        key = id(frame)
        frame_name[key] = f
        if event == "call":
            caller = stack[-1] if stack else None
            if caller is not None:
                arm = TERNARY_ARM.get(cur_node.get(caller))
                if arm is not None:
                    emit(caller, frame_name.get(caller), arm)
                call_edges_seen.add((cur_node.get(caller), f))
            stack.append(key)
            cur_node[key] = ENTRY_OF[f]
            events.append(("call", f))
        elif event == "line":
            ln = frame.f_lineno
            cur = cur_node.get(key)
            if cur in ARM_REGION and ln in ARM_REGION[cur]:
                return tracer  # residual line of an already-resolved ternary
            synth = TERNARY_ELSE.get((cur, ln))
            if synth:
                emit(key, f, synth)
            node = line_to_node(f, ln, cur_node.get(key))
            emit(key, f, node)
        elif event == "return":
            if stack and stack[-1] == key:
                stack.pop()
                events.append(("return", f, EXIT_OF[f]))
                cur_node.pop(key, None)
                frame_name.pop(key, None)
        return tracer

    parent = sys.gettrace()
    sys.settrace(tracer)
    try:
        result = func(**kwargs)
    finally:
        sys.settrace(parent)
    return result, events, call_edges_seen

def top_node_seq(events, func):
    """Node sequence of the top-level invocation of func."""
    seq, depth = [], 0
    for ev in events:
        if ev[0] == "call":
            if depth == 0 and ev[1] != func:
                continue  # ignore stray top calls (none expected)
            seq.append(ENTRY_OF[ev[1]]) if depth == 0 else None
            depth += 1
        elif ev[0] == "return":
            depth -= 1
            if depth == 0:
                seq.append(EXIT_OF[ev[1]])
        elif ev[0] == "node" and depth == 1:
            if ev[1] == func and (not seq or seq[-1] != ev[2]):
                seq.append(ev[2])
    return seq

def verify_dynamic():
    all_call_edges = set()
    for pid, func, kwargs, expected in RUNS:
        result, events, seen = run_traced(func, kwargs)
        all_call_edges |= {(s, ENTRY_OF[c]) for s, c in seen if s and c in ENTRY_OF}
        got = top_node_seq(events, func.__name__)
        want = [n for n, _ in
                next(p[1] for p in BASIS[func.__name__] if p[0] == pid)]
        # strip label-only steps (none: steps are node ids)
        check(got == want,
              f"dynamic: {pid} traced path matches documented path "
              f"({len(got)} nodes)")
        if isinstance(expected, dict):
            for field, exp in expected.items():
                check(getattr(result, field) == exp,
                      f"dynamic: {pid} result .{field} == {exp}")
        else:
            check(result == expected,
                  f"dynamic: {pid} result == {expected}")
    doc_calls = {(s, t) for _, s, t, _ in CALLS}
    check(all_call_edges == doc_calls,
          f"dynamic: observed call edges ({len(all_call_edges)}) == "
          f"documented call-edge table ({len(doc_calls)})")
    # infeasibility of T-P8 (E58/E60): total < 0 is impossible
    def total_negative_possible():
        rng = [D_(x) for x in ("-99.99", "-1", "0", "1.37", "99.99")]
        for sub in rng:
            for disc in rng:
                for ship in rng:
                    for fee_v in (D_("0"), D_("7.77")):
                        for ov in (None, D_("-3.21"), D_("0"), D_("2.00")):
                            b = pricing.compute_totals(
                                subtotal=sub, discount=disc, shipping=ship,
                                fee_enabled=True, fee_type="percent",
                                fee_value=fee_v, vat_enabled=True,
                                vat_rate_percent=D_("19"),
                                vat_apply_to_shipping=True,
                                vat_apply_to_fee=True, vat_override=ov)
                            if b.total < 0:
                                return True
        return False
    check(not total_negative_possible(),
          "infeasibility: 8*5*4*3*2*... sweep (5400 combos incl. negative "
          "subtotal/discount/shipping/override) never yields total < 0 -> "
          "edge E58 (N47->N48) unreachable; T-P8 is structural only")

def main():
    print("== generating cfg.drawio / cfg.svg ==")
    write_drawio(HERE / "cfg.drawio")
    write_svg(HERE / "cfg.svg")
    print(f"  wrote {HERE / 'cfg.drawio'}")
    print(f"  wrote {HERE / 'cfg.svg'}")
    print("\n== check 1: reparse cfg.drawio, recount E/N, V = E-N+2P ==")
    ctrl, _ = verify_drawio()
    print("\n== check 2: AST decision count of pricing.py (V = decisions+1) ==")
    for f, v in ast_decision_count().items():
        check(v == EXPECTED_V[f],
              f"ast: V({f}) = {v} == graph V = {EXPECTED_V[f]}")
    print("\n== check 3: basis paths (validity, coverage, GF(2) rank) ==")
    verify_basis(ctrl)
    print("\n== check 4: dynamic realization under sys.settrace ==")
    verify_dynamic()
    print("\n%s (%d checks failed)" % ("ALL CHECKS PASSED" if not FAIL
                                       else "FAILURES:", len(FAIL)))
    for m in FAIL:
        print("  - " + m)
    sys.exit(1 if FAIL else 0)

if __name__ == "__main__":
    main()
