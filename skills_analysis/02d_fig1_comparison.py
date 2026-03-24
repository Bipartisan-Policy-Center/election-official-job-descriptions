"""
02d_fig1_comparison.py
----------------------
Recreates fig1.png (salary trends by job level over time) as a 4-line
comparison chart overlaying the original dataset.csv against the new
dataset_final.csv.

Lines:
  Old Chief officials  — solid dark blue
  New Chief officials  — dashed lighter blue
  Old Staff            — solid dark red
  New Staff            — dashed lighter red

Both datasets are filtered to election_official + top_election_official rows
(excluding not_election_official) and to salary_mean > $20,000 to remove
obvious data-entry errors in the original dataset (e.g. $0 and $20.8M values).
Years 2011–2025 are shown; 2026 is excluded as a partial year.

REPLICATION
-----------
  python3 skills_analysis/02d_fig1_comparison.py

Input:  dataset.csv
        skills_analysis/dataset_final.csv
Output: skills_analysis/fig1_comparison.png
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib import font_manager

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Fonts — try StyreneA (Will's machine), fall back gracefully in other envs
# ---------------------------------------------------------------------------

def try_load_font(path, name):
    if os.path.exists(path):
        fe = font_manager.FontEntry(fname=path, name=name)
        font_manager.fontManager.ttflist.insert(0, fe)
        return True
    return False

font_dir = os.path.expanduser("~/Library/Fonts")
has_styrene = all([
    try_load_font(os.path.join(font_dir, "StyreneA-Black.otf"),   "StyreneABlack"),
    try_load_font(os.path.join(font_dir, "StyreneA-Medium.otf"),  "StyreneAMedium"),
    try_load_font(os.path.join(font_dir, "StyreneA-Regular.otf"), "StyreneARegular"),
])

if has_styrene:
    matplotlib.rcParams["font.family"] = "StyreneARegular"
    FONT_REG    = "StyreneARegular"
    FONT_MED    = "StyreneAMedium"
    FONT_BLACK  = "StyreneABlack"
else:
    FONT_REG    = "DejaVu Sans"
    FONT_MED    = "DejaVu Sans"
    FONT_BLACK  = "DejaVu Sans"

# ---------------------------------------------------------------------------
# Colours — match fig1 palette; lighter shades for new dataset
# ---------------------------------------------------------------------------

BLUE_OLD   = "#3c608a"
BLUE_NEW   = "#3687e7"
RED_OLD    = "#e43e47"
RED_NEW    = "#f2999e"   # lighter red for new dataset

SALARY_FLOOR = 20_000
SALARY_CAP   = 400_000   # removes obvious data-entry errors in old dataset (e.g. $20.8M)
YEAR_MIN     = 2011
YEAR_MAX     = 2025

# ---------------------------------------------------------------------------
# Load and prep
# ---------------------------------------------------------------------------

old = pd.read_csv(os.path.join(REPO_ROOT, "dataset.csv"))
new = pd.read_csv(os.path.join(SKILLS_DIR, "dataset_final.csv"))

def prep(df, class_col):
    """Filter to election officials, apply salary floor, restrict years."""
    df = df[df[class_col] != "not_election_official"].copy()
    df = df[(df["salary_mean"] > SALARY_FLOOR) & (df["salary_mean"] < SALARY_CAP)]
    df = df[(df["year"] >= YEAR_MIN) & (df["year"] <= YEAR_MAX)]
    return df

old = prep(old, "classification_experimental")
new = prep(new, "job_classification")

def summarise(df, class_col, top_label):
    """Return (mean_salary_by_year, n_by_year) for top and non-top groups."""
    top  = df[df[class_col] == top_label]
    rest = df[df[class_col] != top_label]
    return (
        top.groupby("year")["salary_mean"].mean(),
        top.groupby("year").size(),
        rest.groupby("year")["salary_mean"].mean(),
        rest.groupby("year").size(),
    )

top_old, n_top_old, staff_old, n_staff_old = summarise(old, "classification_experimental", "top_election_official")
top_new, n_top_new, staff_new, n_staff_new = summarise(new, "job_classification",          "top_election_official")

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

import seaborn as sns
sns.set_style("whitegrid", {"grid.color": ".9"})

fig, ax = plt.subplots(figsize=(9, 5.5))

years = range(YEAR_MIN, YEAR_MAX + 1)

def plot_line(series, counts, color, linestyle, label, annotate=True, ann_offset=10):
    series.plot(ax=ax, kind="line", marker="o", color=color,
                linestyle=linestyle, linewidth=2, markersize=5, label=label)
    if annotate:
        for year, (mean, n) in zip(series.index, zip(series, counts.reindex(series.index).fillna(0))):
            ax.annotate(str(int(n)),
                        xy=(year, mean),
                        textcoords="offset points",
                        xytext=(0, ann_offset),
                        ha="center", color=color, fontsize=8,
                        fontname=FONT_REG)

# Old dataset — solid lines, n above
plot_line(top_old,   n_top_old,   BLUE_OLD, "-",  "Old — Chief officials", annotate=True,  ann_offset=10)
plot_line(staff_old, n_staff_old, RED_OLD,  "-",  "Old — Staff",           annotate=True,  ann_offset=-14)

# New dataset — dashed lines, n below (offset opposite direction to reduce overlap)
plot_line(top_new,   n_top_new,   BLUE_NEW, "--", "New — Chief officials", annotate=True,  ann_offset=-14)
plot_line(staff_new, n_staff_new, RED_NEW,  "--", "New — Staff",           annotate=True,  ann_offset=10)

# ---------------------------------------------------------------------------
# Axes / labels
# ---------------------------------------------------------------------------

def currency_fmt(x, pos):
    return "${:,.0f}".format(x)

def year_fmt(x, pos):
    return str(int(x)) if x == YEAR_MIN else f"'{str(int(x))[2:]}"

ax.yaxis.set_major_formatter(FuncFormatter(currency_fmt))
ax.xaxis.set_major_formatter(FuncFormatter(year_fmt))

ax.set_title("Old vs new dataset: salary trends by job level",
             fontname=FONT_BLACK, fontsize=13, pad=12)
ax.set_ylabel("Average salary", fontname=FONT_MED)
ax.set_xlabel("Year of job posting", fontname=FONT_MED)
ax.set_ylim([0, 200_000])
ax.set_xlim([YEAR_MIN - 0.3, YEAR_MAX + 0.3])
ax.grid(False, axis="x")
ax.set_xticks(list(years))
ax.tick_params(labelsize=9)

# Legend
leg = ax.legend(
    loc="upper left", fontsize=9,
    framealpha=0.85, edgecolor="#cccccc",
)

sns.despine()
plt.tight_layout()

out_path = os.path.join(SKILLS_DIR, "fig1_comparison.png")
plt.savefig(out_path, dpi=200, bbox_inches="tight")
print(f"Saved -> {out_path}")
