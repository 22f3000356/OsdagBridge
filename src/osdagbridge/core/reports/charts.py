# =============================================================================
# OsdagBridge — Report Charts
# -----------------------------------------------------------------------------
# Programmatic data-visualisation for the design report.
#
#   * utilization_ratio_chart()        -> scope item 4  (UR = Demand/Capacity)
#   * material_steel_chart()           -> scope item 5  (steel tonnage)
#   * material_concrete_rebar_chart()  -> scope item 5  (concrete vs rebar)
#
# All functions:
#   - render with the headless Agg backend (safe on a build server / no DISPLAY)
#   - return PNG *bytes* (so report_generator writes them into its tmp image
#     dir exactly like the existing CAD / grillage figures), or None on any
#     failure — a missing chart must never break report compilation.
#   - take styling exclusively from theme.py (single source of truth).
# =============================================================================

import io
import logging

from osdagbridge.core.reports import theme

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# small helpers
# -----------------------------------------------------------------------------
def _num(value):
    """Best-effort float; None when not convertible."""
    try:
        if value in (None, "", "N.A.", "N/A", "---"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fig_to_png_bytes(fig):
    """Serialise a matplotlib figure to PNG bytes and close it."""
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# =============================================================================
# 1. UTILISATION-RATIO EXTRACTION  (mirrors chap5 Table 5.22 logic)
# =============================================================================
def _girder_max_ur(output_dict):
    """Max DCR across every per-girder check (excludes end-beam 'EB*' keys)."""
    per_g = (output_dict.get("design_results", {}) or {}).get("per_girder", {}) or {}
    best = None
    for gkey, gdata in per_g.items():
        if str(gkey).startswith("EB"):
            continue
        for chk in (gdata.get("checks") or []):
            d = _num(chk.get("dcr"))
            if d is not None and (best is None or d > best):
                best = d
    return best


def _deck_max_ur(output_dict):
    """Max UR over the deck-slab checks, computed as Demand/Capacity.

    Uses output_dict['deck_report_values'] with the same KEY_DD_* demand/
    capacity pairs that chap5 Table 5.22 uses, so the bar matches the table.
    """
    deck = output_dict.get("deck_report_values", {}) or {}
    if not deck:
        return None
    try:
        from osdagbridge.core.utils.common import (
            KEY_DD_M_ULS_SAG, KEY_DD_MU_BOT,
            KEY_DD_M_ULS_HOG, KEY_DD_MU_TOP,
            KEY_DD_M_ULS_OH,  KEY_DD_MU_OH,
            KEY_DD_PUNCH_VED, KEY_DD_VRD_C_MPA,
            KEY_DD_SHEAR_VED, KEY_DD_SHEAR_VRDC,
            KEY_DD_HAS_OVERHANG,
        )
    except Exception:
        return None

    pairs = [
        (KEY_DD_M_ULS_SAG, KEY_DD_MU_BOT),
        (KEY_DD_M_ULS_HOG, KEY_DD_MU_TOP),
        (KEY_DD_PUNCH_VED, KEY_DD_VRD_C_MPA),
        (KEY_DD_SHEAR_VED, KEY_DD_SHEAR_VRDC),
    ]
    if deck.get(KEY_DD_HAS_OVERHANG):
        pairs.append((KEY_DD_M_ULS_OH, KEY_DD_MU_OH))

    best = None
    for dem_key, cap_key in pairs:
        dem = _num(deck.get(dem_key))
        cap = _num(deck.get(cap_key))
        if dem is not None and cap not in (None, 0):
            ur = dem / cap
            if best is None or ur > best:
                best = ur
    return best


def _cross_bracing_max_ur(bridge):
    """Max cross-bracing efficiency (UR) via the ReportDataBridge helpers."""
    if bridge is None:
        return None
    try:
        pairs = bridge.get_cb_pairs()
    except Exception:
        return None
    best = None
    for pair in pairs:
        for member in ("diagonal", "chord"):
            for ft in ("compression", "tension"):
                ur = _num(bridge.get_cb_efficiency(pair, member, ft))
                if ur is not None and (best is None or ur > best):
                    best = ur
    return best


def _end_diaphragm_ur(output_dict, input_dict, bridge):
    """End-diaphragm UR.

    When the ED is configured as a cross-bracing member the current report
    designs it with the cross-bracing engine, so its governing UR equals the
    cross-bracing UR.  For rolled/welded ED sections the moment/shear design is
    not yet implemented, so return None (bar omitted).
    """
    try:
        from osdagbridge.core.utils.common import KEY_MP_ED_TYPE
    except Exception:
        return None
    ed_type = ""
    for k, v in (input_dict or {}).items():
        if str(k).startswith(KEY_MP_ED_TYPE) and v:
            ed_type = str(v)
            break
    if "brac" in ed_type.strip().lower():
        return _cross_bracing_max_ur(bridge)
    return None


def collect_utilization_ratios(output_dict, input_dict=None, bridge=None):
    """Return an ordered list of (element_label, UR_float) for primary elements.

    Elements with no available data are omitted so the chart only shows real
    results.  Order follows the scope document.
    """
    input_dict = input_dict or {}
    candidates = [
        ("Steel Plate\nGirders",  _girder_max_ur(output_dict)),
        ("Concrete\nDeck Slab",   _deck_max_ur(output_dict)),
        ("Cross\nBracing",        _cross_bracing_max_ur(bridge)),
        ("End\nDiaphragms",       _end_diaphragm_ur(output_dict, input_dict, bridge)),
    ]
    return [(lbl, ur) for lbl, ur in candidates if ur is not None]


# =============================================================================
# 2. UTILISATION-RATIO BAR CHART  (scope item 4)
# =============================================================================
def utilization_ratio_chart(output_dict, input_dict=None, bridge=None,
                            precomputed=None):
    """Bar chart of UR per primary element with a red dashed UR=1.0 line.

    `precomputed`, if given, is a list of (label, ur) and bypasses extraction
    (lets chap5 pass the exact same numbers it tabulates).

    Returns PNG bytes, or None if there is nothing to plot / on error.
    """
    try:
        theme.apply_chart_style()
        import matplotlib.pyplot as plt

        data = precomputed if precomputed is not None else \
            collect_utilization_ratios(output_dict, input_dict, bridge)
        if not data:
            return None

        labels = [d[0] for d in data]
        urs = [float(d[1]) for d in data]
        colors = [theme.ur_bar_color(u) for u in urs]
        thr = theme.CHART["ur_threshold"]

        fig, ax = plt.subplots(figsize=theme.CHART["figsize_ur"])
        x = range(len(labels))
        bars = ax.bar(x, urs, color=colors, width=0.6,
                      edgecolor="#333333", linewidth=0.7, zorder=3)

        # UR = 1.0 pass/fail threshold
        ax.axhline(thr, color=theme._hex("threshold"), linestyle="--",
                   linewidth=1.6, zorder=4,
                   label="Limit (UR = %.1f)" % thr)

        # value labels above each bar
        for rect, u in zip(bars, urs):
            ax.annotate("%.2f" % u,
                        xy=(rect.get_x() + rect.get_width() / 2, rect.get_height()),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom",
                        fontsize=theme.CHART["value_size"], fontweight="bold",
                        color=theme._hex("fail") if u > thr else theme._hex("pass"))

        top = max(max(urs), thr) * 1.25
        ax.set_ylim(0, top)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel("Utilization Ratio (Demand / Capacity)")
        ax.set_title("Overall Utilization Ratio Summary — Primary Elements",
                     fontweight="bold")
        ax.set_axisbelow(True)
        ax.yaxis.grid(True)
        ax.xaxis.grid(False)

        # legend proxies for pass / fail
        from matplotlib.patches import Patch
        handles = [
            Patch(facecolor=theme._hex("pass"), edgecolor="#333333", label="Pass (UR \u2264 1.0)"),
            Patch(facecolor=theme._hex("fail"), edgecolor="#333333", label="Fail (UR > 1.0)"),
        ]
        thr_handle = ax.get_legend_handles_labels()[0]
        ax.legend(handles=handles + thr_handle, loc="upper right",
                  fontsize=8.5, framealpha=0.9)

        return _fig_to_png_bytes(fig)
    except Exception as exc:
        logger.warning("utilization_ratio_chart failed: %s", exc)
        return None


# =============================================================================
# 3. MATERIAL QUANTITY CHARTS  (scope item 5)
# =============================================================================
def collect_material_quantities(inputs):
    """Pull the Chapter-7 BOM totals that calculate_material_quantities writes.

    Returns a dict of floats (missing / 'N.A.' values are dropped).
    """
    keys = {
        "girders":   "steel_girders_wt_total",
        "brace_top": "bracing_top_wt_total",
        "brace_bot": "bracing_bot_wt_total",
        "brace_dia": "bracing_diag_wt_total",
        "concrete":  "concrete_deck_vol_total",   # m^3
        "rebar":     "rebar_deck_wt_total",       # MT
    }
    out = {}
    for name, key in keys.items():
        v = _num(inputs.get(key))
        if v is not None:
            out[name] = v
    return out


def material_steel_chart(inputs):
    """Bar chart: structural-steel tonnage by element (girders, bracing, ED).

    End-diaphragm steel is reported together with cross-bracing in the current
    BOM, so the three cross-bracing chords are summed into one 'Cross Bracing /
    End Diaphragm' bar alongside the girders.
    Returns PNG bytes or None.
    """
    try:
        q = collect_material_quantities(inputs)
        girders = q.get("girders")
        bracing = sum(q[k] for k in ("brace_top", "brace_bot", "brace_dia") if k in q) \
            if any(k in q for k in ("brace_top", "brace_bot", "brace_dia")) else None
        series = [("Plate Girders", girders),
                  ("Cross Bracing /\nEnd Diaphragms", bracing)]
        series = [(l, v) for l, v in series if v is not None]
        if not series:
            return None

        theme.apply_chart_style()
        import matplotlib.pyplot as plt
        labels = [s[0] for s in series]
        vals = [s[1] for s in series]

        fig, ax = plt.subplots(figsize=theme.CHART["figsize_bar"])
        x = range(len(labels))
        bars = ax.bar(x, vals, width=0.55, color=theme._hex("barSteel"),
                      edgecolor="#333333", linewidth=0.7, zorder=3)
        for rect, v in zip(bars, vals):
            ax.annotate("%.2f" % v,
                        xy=(rect.get_x() + rect.get_width() / 2, rect.get_height()),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom",
                        fontsize=theme.CHART["value_size"], fontweight="bold")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel("Structural Steel (MT)")
        ax.set_title("Structural Steel Tonnage by Element", fontweight="bold")
        ax.set_ylim(0, max(vals) * 1.25)
        ax.set_axisbelow(True)
        ax.yaxis.grid(True)
        ax.xaxis.grid(False)
        return _fig_to_png_bytes(fig)
    except Exception as exc:
        logger.warning("material_steel_chart failed: %s", exc)
        return None


def material_concrete_rebar_chart(inputs):
    """Grouped twin-axis chart: deck concrete volume (m3) vs rebar weight (MT).

    The two quantities use different units, so each gets its own y-axis.
    Returns PNG bytes or None.
    """
    try:
        q = collect_material_quantities(inputs)
        concrete = q.get("concrete")
        rebar = q.get("rebar")
        if concrete is None and rebar is None:
            return None

        theme.apply_chart_style()
        import matplotlib.pyplot as plt
        fig, ax1 = plt.subplots(figsize=theme.CHART["figsize_bar"])
        ax2 = ax1.twinx()

        xpos_c, xpos_r = 0.0, 1.0
        drawn = []
        if concrete is not None:
            b1 = ax1.bar([xpos_c], [concrete], width=0.5,
                         color=theme._hex("barConcrete"), edgecolor="#333333",
                         linewidth=0.7, zorder=3, label="Concrete (m\u00b3)")
            ax1.annotate("%.2f" % concrete, xy=(xpos_c, concrete),
                         xytext=(0, 3), textcoords="offset points", ha="center",
                         va="bottom", fontsize=theme.CHART["value_size"], fontweight="bold")
            drawn.append(b1)
        if rebar is not None:
            b2 = ax2.bar([xpos_r], [rebar], width=0.5,
                         color=theme._hex("barRebar"), edgecolor="#333333",
                         linewidth=0.7, zorder=3, label="Reinforcement (MT)")
            ax2.annotate("%.2f" % rebar, xy=(xpos_r, rebar),
                         xytext=(0, 3), textcoords="offset points", ha="center",
                         va="bottom", fontsize=theme.CHART["value_size"], fontweight="bold")
            drawn.append(b2)

        ax1.set_ylabel("Concrete Volume (m\u00b3)", color=theme._hex("barConcrete"))
        ax2.set_ylabel("Reinforcement Steel (MT)", color=theme._hex("barRebar"))
        ax1.tick_params(axis="y", labelcolor=theme._hex("barConcrete"))
        ax2.tick_params(axis="y", labelcolor=theme._hex("barRebar"))
        if concrete is not None:
            ax1.set_ylim(0, concrete * 1.3)
        if rebar is not None:
            ax2.set_ylim(0, rebar * 1.3)
        ax1.set_xticks([xpos_c, xpos_r])
        ax1.set_xticklabels(["Deck Concrete", "Deck Reinforcement"])
        ax1.set_title("Deck Concrete Volume vs Reinforcement Weight", fontweight="bold")
        ax1.set_axisbelow(True)
        ax1.yaxis.grid(True)
        ax1.xaxis.grid(False)
        return _fig_to_png_bytes(fig)
    except Exception as exc:
        logger.warning("material_concrete_rebar_chart failed: %s", exc)
        return None
