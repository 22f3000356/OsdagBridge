# OsdagBridge — Report Generator Enhancements: Technical Changes

Branch: `feature/report-enhancements`
Scope: refactor and enhance the design-report generator under
`src/osdagbridge/core/reports/`.

---

## 0. Important note on PyLaTeX vs. the existing approach

The task brief refers to *PyLaTeX*. The existing OsdagBridge report generator
does **not** use the PyLaTeX object model — it builds the document as raw LaTeX
**string templates** in Python (one function per chapter, returning a LaTeX
string) and compiles the assembled document with `pdflatex` via `subprocess`
(see `report_generator.generate_report`). To keep the change set minimal,
reviewable, and consistent with the surrounding code, all enhancements follow
that **existing convention** (raw-string templates + `longtable`) rather than
introducing a parallel PyLaTeX dependency. The LaTeX concepts the brief asks
for — `longtable` with `\endhead`/`\endfirsthead`, `Figure`, geometry/footer
control — are implemented directly and are exactly what PyLaTeX would emit.

---

## 1. Files altered / added (all under the report generator)

| File | Status | Purpose |
|------|--------|---------|
| `reports/theme.py` | **new** | Centralized style config — single source of truth (scope 6). |
| `reports/charts.py` | **new** | Matplotlib UR + material charts returning PNG bytes (scope 4, 5). |
| `reports/report_generator.py` | modified | Consumes `theme` in the preamble; renders charts into the temp image dir and wires them through `fig_paths`. |
| `reports/chap3.py` | modified | Splits merged live loads into vehicle + footway tables with unit columns; repeated headers (scope 3, 1). |
| `reports/chap5.py` | modified | Embeds the UR chart in §5.5; repeated headers on summary tables (scope 4, 1). |
| `reports/chap7.py` | modified | Repeated headers on the BOM table; embeds material charts (scope 1, 5). |
| `tools/report_demo/` | **new** | Standalone harness that renders the charts and compiles before/after demo PDFs with mock data (no GUI needed). |

---

## 2. Scope item 1 — Repeated table headers across page breaks

**Problem:** multi-page tables split without repeating the column header.

**Change:** `theme.longtable_header(columns, caption, label, continued=True)`
emits a full `longtable` header block with:

* `\endfirsthead` — header shown on the first page (with caption),
* `\endhead` — the same header row re-emitted at the top of **every**
  continuation page, preceded by a *"Table continued from previous page"* strip,
* `\endfoot` / `\endlastfoot` — a *"Continued on next page"* strip at each break.

Applied to the tables most likely to span pages: the Overall Design Check
Summary (5.22) and Girder Design Summary (5.13) in `chap5.py`, the Bill of
Materials (7.1) in `chap7.py`, and the Load Combinations and live-load tables in
`chap3.py`. Any other table adopts the behaviour by calling the same helper, so
the pattern is reusable rather than copy-pasted.

## 3. Scope item 2 — Footer overlap / vertical spacing

**Change (centralized in `theme.py`):**

* `theme.pagebreak_guard_latex()` raises the pre-table `\needspace` guard from 5
  to **6** `\baselineskip` for both `table` and `longtable`, so a caption or
  first data row (e.g. the "G4" row called out in the brief) can no longer start
  so low on a page that it collides with the footer — if too little room
  remains, the table breaks to the next page first.
* Adds `\setlength{\footskip}{1.2cm}` to reserve breathing room above the footer
  rule.
* `theme.table_layout_latex()` sets a slightly larger `\arraystretch` (1.18) and
  `\extrarowheight` for consistent row height and padding.

## 4. Scope item 3 — Load & geometry table refactoring (live loads)

**Problem:** vehicle live loads and footway load were in one table with no unit
column, and the IRC-6 computed footway intensity was discarded.

**Change in `chap3.py`:** the single *Live Loads (LL)* table is replaced by two
tables, each a 3-column `|Parameter|Value|Unit|` `longtable` with repeated
headers:

* **Vehicle Live Loads (LL)** — vehicle classes (driven by the UI loading-tab
  selection, unchanged logic), impact/dynamic allowance factor (Cl. 208),
  longitudinal braking force split into a numeric **Value** + **Unit (kN)**, and
  a centrifugal-force row (shown `N/A` with the correct IRC note, since the
  backend has no curvature/radius input — a straight-bridge case).
* **Footway / Footpath Live Load (LL)** — pressure basis (automatic IRC 6 Cl.
  206.1 vs. user-specified) and the intensity value with its unit. The
  previously-unused IRC-6 computed value (`cl_206_1_footway_load`) is now
  surfaced in the Value column.

## 5. Scope item 4 — Utilization-ratio summary visualization

**Change:** `charts.utilization_ratio_chart(...)` produces a bar chart of
UR = Demand / Capacity for the primary elements — Steel Plate Girders, Concrete
Deck Slab, Cross Bracing, End Diaphragms — with:

* **Y-axis** = Utilization Ratio,
* a **red dashed threshold line at UR = 1.0**,
* green bars for UR ≤ 1.0 and red bars for UR > 1.0, value labels, and a legend.

`charts.collect_utilization_ratios(...)` extracts the governing UR per element
using the **same** data sources as Table 5.22 (`design_results["per_girder"]`
DCRs, `deck_report_values` demand/capacity pairs, and the `ReportDataBridge`
cross-bracing efficiency helpers), so the chart and the table always agree. The
figure is embedded in **§5.5 Overall Design Check Summary** (`chap5.py`).

## 6. Scope item 5 — Material quantity bar charts

**Change (`charts.py`, embedded by `chap7.py`):**

* `material_steel_chart(...)` — structural-steel tonnage (girders vs.
  cross-bracing / end-diaphragms).
* `material_concrete_rebar_chart(...)` — deck concrete volume (m³) vs.
  reinforcement steel weight (MT) on a twin axis (different units).

Both read the totals that `boq.boq_generator.calculate_material_quantities`
already injects into `payload.inputs` (`steel_girders_wt_total`,
`bracing_*_wt_total`, `concrete_deck_vol_total`, `rebar_deck_wt_total`). Plots
are rendered to PNG bytes, written to the compile temp dir, and embedded via the
existing `report_utils._fig_embed` (LaTeX `figure`).

## 7. Scope item 6 — Centralized formatting / style system

`reports/theme.py` is the single source of truth. Structure:

```
COLORS            dict  — every colour (brand, pass/fail, chart palette) as hex
PAGE              dict  — paper, margin, needspace lines, footskip
TABLE             dict  — colsep, arraystretch, rule widths, LT pre/post skips
CHART             dict  — dpi, figure sizes, font sizes, UR threshold (1.0)

color_definitions_latex()   -> every \definecolor
table_layout_latex()        -> global table/longtable spacing block
pagebreak_guard_latex()     -> \needspace guards + footskip (scope 2)
longtable_header(...)        -> repeated-header block (scope 1)
apply_chart_style()          -> shared matplotlib rcParams
ur_bar_color(ur)             -> pass/fail colour from one threshold
```

`report_generator.preamble()` now calls `table_layout_latex()`,
`pagebreak_guard_latex()` and `color_definitions_latex()` instead of carrying
hard-coded `\setlength` / `\definecolor` lines. To restyle the whole report
(colours, padding, row height, thresholds) you edit **`theme.py` only**.

---

## 8. Architecture & integration flow

The charts follow the **exact same lifecycle as the existing CAD / grillage
figures**, so nothing new had to be invented in the compile path:

```
generate_report()
  └─ (temp dir) write existing figure bytes -> fig_paths
  └─ calculate_material_quantities() -> payload.inputs
  └─ bridge = ReportDataBridge(...)
  └─ NEW: charts.* -> PNG bytes -> temp images -> fig_paths['ur_summary' | 'material_steel' | 'material_concrete']
  └─ ch5_design_checks(..., fig_paths)   # embeds ur_summary in §5.5
  └─ ch7_quantities(..., fig_paths)      # embeds material charts
  └─ pdflatex × 2
```

Chapter signatures gained an **optional** `fig_paths=None` parameter, so no
existing call site breaks. Every chart function is wrapped in `try/except` and
returns `None` on any failure; a missing chart simply does not render and can
never break report compilation.

---

## 9. Rationale for key choices

* **Raw-string templates, not PyLaTeX** — matches the existing generator;
  avoids a new dependency and a dual rendering model (see §0).
* **Charts as PNG bytes via `fig_paths`** — reuses the proven figure pipeline;
  no temp files leak next to the PDF (the generator already cleans its temp dir).
* **One UR-extraction routine shared by chart and table** — guarantees the §5.5
  chart cannot disagree with Table 5.22.
* **Defensive chart functions** — a report must still compile if a data key is
  missing; charts degrade to "absent" rather than raising.
* **Single theme module** — the brief's core maintainability requirement; all
  colour/spacing/threshold knobs live in one file.

---

## 10. Testing performed

* `python -m py_compile` passes for every module in `reports/`.
* `tools/report_demo/gen_charts.py` exercises the real `charts.py` code paths
  with mock design data (UR extraction correctly ignores end-beam `EB*` keys,
  picks governing URs, and flags UR > 1.0) and writes the three PNGs.
* `tools/report_demo/make_demo.py` compiles **`Report_Before_DEMO.pdf`** and
  **`Report_After_DEMO.pdf`** with `pdflatex`, using the real `theme.py`
  helpers, to visually verify: repeated longtable headers across a page break,
  split live-load tables with unit columns, the UR chart with the UR = 1.0 line,
  and the material charts.

### What still requires the GUI
The genuine **`Report_Before.pdf`** and **`Report_After.pdf`** must be generated
on a machine running OsdagBridge (conda env), by running a full bridge analysis
(**Design**) and then **Generate Report**, on the `dev` baseline vs. this
branch. The demo PDFs here prove the rendering changes with mock data; they are
**not** a substitute for a real design run.
