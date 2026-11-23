# =============================================================================
# OsdagBridge — Report Theme / Style Configuration
# -----------------------------------------------------------------------------
# SINGLE SOURCE OF TRUTH for every visual attribute of the design report:
#   * colour palette (document + charts)
#   * page geometry and margins
#   * table layout (padding, row height, rule widths, longtable skips)
#   * repeated-header helpers for multi-page longtables
#   * matplotlib chart styling (figure size, dpi, fonts, UR threshold)
#
# Every chapter / section generator and the chart module import their styling
# from here.  To restyle the whole report, edit this file only — do NOT scatter
# \definecolor, \setlength or hard-coded hex values across chapter scripts.
# =============================================================================

# -----------------------------------------------------------------------------
# 1. COLOUR PALETTE  (hex, no leading '#')
# -----------------------------------------------------------------------------
COLORS = {
    "osdagGreen":   "91B014",   # brand / header + footer rule
    "headerText":   "2B2B2B",   # running-header text
    "tableHeadBg":  "E9F0D0",   # header-row fill for data tables
    "tableAltBg":   "F6F8EE",   # (optional) zebra stripe
    "rulePrimary":  "91B014",   # table outer rule colour
    "pass":         "2E7D32",   # UR <= 1.0  (green)
    "fail":         "C62828",   # UR >  1.0  (red)
    "threshold":    "C62828",   # UR = 1.0 reference line (red)
    "barSteel":     "5B7DB1",
    "barConcrete":  "8C9EB2",
    "barRebar":     "C9A227",
}

# -----------------------------------------------------------------------------
# 2. PAGE GEOMETRY
# -----------------------------------------------------------------------------
PAGE = {
    "paper":        "a4paper",
    "margin":       "1in",
    # minimum lines that must fit before a table may start, else break first.
    # Fixes "G4"-style rows / captions bleeding into the footer (scope item 2).
    "needspace_lines": 6,
    # extra breathing room reserved above the footer rule.
    "footskip":     "1.2cm",
}

# -----------------------------------------------------------------------------
# 3. TABLE LAYOUT
# -----------------------------------------------------------------------------
TABLE = {
    "colsep":        "6pt",     # \tabcolsep  — horizontal cell padding
    "arraystretch":  "1.18",    # row height multiplier (was 1.12)
    "rulewidth":     "0.5pt",   # \arrayrulewidth — outline thickness
    "extrarowheight": "1.0pt",  # small extra height for legibility
    "lt_pre":        "0pt",     # \LTpre  — skip before a longtable
    "lt_post":       "8pt",     # \LTpost — skip after a longtable
}


# -----------------------------------------------------------------------------
# 4. LaTeX EMITTERS  (consumed by report_generator.preamble)
# -----------------------------------------------------------------------------
def color_definitions_latex():
    """Emit every \\definecolor so colours live in exactly one place."""
    lines = []
    for name, hexval in COLORS.items():
        lines.append(r"\definecolor{%s}{HTML}{%s}" % (name, hexval))
    return "\n".join(lines)


def table_layout_latex():
    """Emit the global table/longtable layout settings block.

    Replaces the previously hard-coded \\setlength / \\arraystretch block that
    was embedded directly in the preamble, so spacing is tuned from one place.
    """
    t = TABLE
    return "\n".join([
        r"% --- Table layout (from theme.py: single source of truth) ---",
        r"\setlength{\tabcolsep}{%s}" % t["colsep"],
        r"\renewcommand{\arraystretch}{%s}" % t["arraystretch"],
        r"\setlength{\LTpre}{%s}" % t["lt_pre"],
        r"\setlength{\LTpost}{%s}" % t["lt_post"],
        r"\setlength{\arrayrulewidth}{%s}" % t["rulewidth"],
        r"\setlength{\extrarowheight}{%s}" % t["extrarowheight"],
    ])


def pagebreak_guard_latex():
    """Emit the \\needspace guards that stop tables overflowing into the footer.

    Scope item 2: page-bottom threshold constraint applied to every table and
    longtable environment so a header row / first data row never bleeds into
    the footer rule.
    """
    n = PAGE["needspace_lines"]
    return "\n".join([
        r"% --- Keep tables clear of the footer (from theme.py) ---",
        r"\BeforeBeginEnvironment{table}{\needspace{%d\baselineskip}}" % n,
        r"\BeforeBeginEnvironment{longtable}{\needspace{%d\baselineskip}}" % n,
        r"\setlength{\footskip}{%s}" % PAGE["footskip"],
    ])


# -----------------------------------------------------------------------------
# 5. REPEATED LONGTABLE HEADERS  (scope item 1)
# -----------------------------------------------------------------------------
def longtable_header(columns, caption=None, label=None,
                     continued=True, bold=True, row_suffix=r"\\[6pt]"):
    """Build a longtable caption + repeating-header block.

    Produces the \\endfirsthead / \\endhead machinery so that the column
    header row is repeated at the top of every page a multi-page table spans.

    Parameters
    ----------
    columns : list[str]
        Column header cells (LaTeX allowed, e.g. r"\\textbf{UR}").
    caption : str | None
        Table caption text (without the \\caption wrapper); bolded.
    label : str | None
        Optional \\label key.
    continued : bool
        If True, add a "(continued)" strip at the top of carry-over pages.
    bold : bool
        Wrap each column title in \\textbf{} automatically.

    Returns
    -------
    str  — insert immediately after \\begin{longtable}{...}.
    """
    ncols = len(columns)
    cells = [(r"\textbf{%s}" % c if bold else c) for c in columns]
    header_row = " & ".join(cells) + " " + row_suffix

    parts = []
    if caption is not None:
        parts.append(r"\caption{\textbf{%s}}%s" % (caption, (r"\label{%s}" % label) if label else ""))
        parts.append(r"\\")
    # First-page header
    parts.append(r"\hline")
    parts.append(header_row)
    parts.append(r"\hline")
    parts.append(r"\endfirsthead")
    # Carry-over header on every subsequent page
    if continued:
        parts.append(
            r"\multicolumn{%d}{r}{\footnotesize\itshape Table continued from previous page}\\" % ncols
        )
    parts.append(r"\hline")
    parts.append(header_row)
    parts.append(r"\hline")
    parts.append(r"\endhead")
    # Footer shown at every page break (except the very last)
    parts.append(r"\hline")
    parts.append(r"\endfoot")
    # Final footer (last page) — just the closing rule
    parts.append(r"\hline")
    parts.append(r"\endlastfoot")
    return "\n".join(parts)


# -----------------------------------------------------------------------------
# 6. MATPLOTLIB CHART STYLING  (scope items 4 & 5)
# -----------------------------------------------------------------------------
CHART = {
    "dpi":          150,
    "figsize_ur":   (9.2, 4.4),
    "figsize_bar":  (7.6, 4.2),
    "title_size":   13,
    "label_size":   11,
    "tick_size":    9.5,
    "value_size":   8.5,
    "ur_threshold": 1.0,          # pass/fail line for utilisation ratio
}


def _hex(name):
    """'#RRGGBB' for a palette key (matplotlib wants the leading hash)."""
    return "#" + COLORS[name]


def apply_chart_style():
    """Apply shared matplotlib rcParams so every chart looks identical.

    Uses the non-interactive Agg backend (headless / server safe) and a font
    stack that degrades gracefully when the preferred faces are unavailable.
    """
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi":        CHART["dpi"],
        "savefig.dpi":       CHART["dpi"],
        "font.family":       "sans-serif",
        "font.sans-serif":   ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"],
        "axes.titlesize":    CHART["title_size"],
        "axes.labelsize":    CHART["label_size"],
        "xtick.labelsize":   CHART["tick_size"],
        "ytick.labelsize":   CHART["tick_size"],
        "axes.edgecolor":    "#444444",
        "axes.linewidth":    0.8,
        "axes.grid":         True,
        "grid.color":        "#DDDDDD",
        "grid.linewidth":    0.6,
        "figure.autolayout": True,
    })


def ur_bar_color(ur):
    """Pass (green) / fail (red) colour for a utilisation-ratio bar."""
    try:
        return _hex("fail") if float(ur) > CHART["ur_threshold"] else _hex("pass")
    except (TypeError, ValueError):
        return "#9E9E9E"
