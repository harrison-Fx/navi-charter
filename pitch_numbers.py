"""Print the PITCH_PACK.md "Numbers used" table from a results CSV.

    python pitch_numbers.py            # results_approx.csv (+ wave_scan_approx.csv if present)
    python pitch_numbers.py osm        # results_osm.csv
    python pitch_numbers.py osm outputs/real-map   # look in another folder

Only reads files written by kuching_advisor.py; changes nothing.
"""
import csv, os, sys
from statistics import mean

tag = sys.argv[1] if len(sys.argv) > 1 else "approx"
folder = sys.argv[2] if len(sys.argv) > 2 else "."
path = os.path.join(folder, f"results_{tag}.csv")
if not os.path.exists(path):
    sys.exit(f"Not found: {path}. Run: python kuching_advisor.py{' --osm' if tag.startswith('osm') else ''}")

rows = list(csv.DictReader(open(path, newline="")))
COLS = [("static", "Fixed routes"), ("independent", "Typical app"),
        ("coordinated", "Our advisor"), ("school_safe", "Our advisor + school-safe")]

def sel(strategy, scenario, daytype="term"):
    return [r for r in rows if r["strategy"] == strategy and r["scenario"] == scenario and r["daytype"] == daytype]

def avg(strategy, scenario, key):
    R = sel(strategy, scenario)
    return mean(float(r[key]) for r in R) if R else None

def warn(strategy, scenario):
    R = [r for r in sel(strategy, scenario) if r.get("tp") not in (None, "")]
    if not R:
        return None
    tp, fp, fn = (sum(float(r[k]) for r in R) for k in ("tp", "fp", "fn"))
    return tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0, mean(float(r["brier"]) for r in R)

def fmt(v, kind):
    if v is None:
        return ""
    return f"{v:.1f}%" if kind == "pct" else f"{v:,.0f}"

lines = [("On time, school day normal", "on_time", "normal", "pct"),
         ("On time, school day closure", "on_time", "closure", "pct"),
         ("Time+fuel RM/day, normal", "phys_rm", "normal", "rm"),
         ("Time+fuel RM/day, closure", "phys_rm", "closure", "rm")]

print(f"## Numbers used (from results_{tag}.csv, simulated)\n")
print("| | " + " | ".join(c[1] for c in COLS) + " |")
print("|---" * (len(COLS) + 1) + "|")
for label, key, sc, kind in lines:
    print(f"| {label} | " + " | ".join(fmt(avg(s, sc, key), kind) for s, _ in COLS) + " |")
for sc in ("normal", "closure"):
    cells = []
    for s, _ in COLS:
        w = warn(s, sc)
        cells.append(f"{w[0]:.0%} / {w[1]:.0%}" if w else "")
    print(f"| Warnings precision / recall, {sc} | " + " | ".join(cells) + " |")
for sc in ("normal", "closure"):
    cells = [f"{warn(s, sc)[2]:.3f}" if warn(s, sc) else "" for s, _ in COLS]
    print(f"| Brier, {sc} | " + " | ".join(cells) + " |")

st, ind = avg("static", "closure", "phys_rm"), avg("coordinated", "closure", "phys_rm")
if st and ind:
    print(f"\nSaved on a closure morning vs fixed routes: RM {st - ind:,.0f}")

wpath = os.path.join(folder, f"wave_scan_{tag}.csv")
if os.path.exists(wpath):
    W = {r["wave_start"]: r for r in csv.DictReader(open(wpath, newline="")) if r["scenario"] == "normal"}
    if "07:00" in W and "07:30" in W:
        print(f"Wave timing (typical app, school day, normal): 07:00 {float(W['07:00']['independent_on_time']):.1f}%"
              f" -> 07:30 {float(W['07:30']['independent_on_time']):.1f}%")
