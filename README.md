# Kuching Dispatch Advisor — Handoff (v2)

**Vision:** free-flowing Kuching roads for everyone. **Way in:** delivery fleets, which can coordinate hundreds of vehicles from day one.

The prototype tests one question: *does accounting for a fleet's own planned road usage improve delivery outcomes, compared with routing each vehicle independently using the same live traffic information?* It also measures, separately, how useful early lateness warnings are.

Everything is a **simulation** (BPR congestion + Monte Carlo). Nothing here is a field trial.

- Plan, corrections and results: **`BLUEPRINT.md`** (start here)
- History of decisions: `JOURNAL.md`
- Report (Claude Doc): https://claude.ai/code/artifact/f55f6f6c-977a-48b8-8a15-600f5fa565a0 — still describes v1 results; to be updated

---

## Quick start

```
pip install -r requirements.txt
python kuching_advisor.py                 # approximate map, 400 vehicles, 60 days x 3 seeds (~1 min)
python kuching_advisor.py --sweep --days 30   # fleet size 100-800 x 3 closure locations x 3 seeds (~30 s)
```

**Real Greater Kuching roads (needs internet once):** on Windows, double-click `RUN-REAL-MAP.bat`. It installs the packages, runs the main, no-outside-traffic, leave-time and noise runs, and zips everything into `real-map-results.zip`. By hand:

```
python kuching_advisor.py --osm           # downloads OSM, saves data/greater_kuching_drive.graphml
python kuching_advisor.py --osm --sweep   # slower: allow ~15-30 min
python kuching_advisor.py --osm --routes=yen   # old route search, reproduces the 1-route finding
```

After the first `--osm` run, `data/greater_kuching_drive.graphml` lets later runs work offline.

Options: `--days N`, `--seeds N`, `--vehicles N`, `--graph path.graphml`, `--wave HH:MM` (wave start, default 07:00), `--wave-scan` (term-day results for several start times), `--fake-scan` (robustness to fake trip requests), `--priority-scan` (does claiming urgency pay?), `--noise-scan` (robustness to day-to-day traffic noise and live-data error), `--double-session X` (share of unverified primary schools treated as two-session), `--commuters X` (scale on traffic from outside Kuching; 0 = off).

School list with session types: `data/kuching_schools_sessions.csv` (sessions unverified — fill them in as sources are found; see BLUEPRINT.md section 11).

The first `--osm` run also downloads school locations to `data/kuching_schools.csv`.

Pitch numbers: `python pitch_numbers.py approx` (or `osm`, plus an optional folder) prints the PITCH_PACK table from `results_<tag>.csv`. The main run also saves `calibration_<tag>.png` (predicted vs actual chance of being late).

## Outputs (tag = `approx`, `osm`, or `osm_yen`)

| File | What it shows |
|---|---|
| console | Route diagnostics, ledger 1 (physical), paired differences with 95% CIs, ledger 2 (warnings), calibration |
| `results_<tag>.csv` | Every strategy × day × scenario × seed |
| `ledger1_<tag>.png` | On-time % and vehicle-hours for the four strategies |
| `warnings_<tag>.csv` | One closure day's warning list (notify actions) |
| `sweep_<tag>.csv`, `fleet_size_effect_<tag>.png` | Coordination gain by fleet size, term vs holiday |
| `wave_scan_<tag>.csv` | Term-day results by wave start time |
| `fake_scan_<tag>.csv` | Effect of random and targeted fake trips on coordination |
| `priority_scan_<n>_<tag>.csv` | Neutral vs deadline-first order; effect of false urgency claims |

Latest approximate-map outputs are in `outputs/v3/` (with school traffic) and `outputs/v4/` (fake-trip test), `outputs/v5/` (priority test), `outputs/v6/` (school sessions), `outputs/v7/` (traffic from outside Kuching); mobile app in `mobile/` (see `mobile/README.md`); `outputs/v2/` = before school traffic.

## Strategies

| Name | Uses live traffic? | Counts the fleet's own vehicles? |
|---|---|---|
| Static plan | No (averages) | No |
| Live independent (typical app) | Yes | No |
| Live random split | Yes | No (random spreading) |
| Live coordinated (herd-aware) | Yes | Yes — congestion-aware greedy assignment |
| Live coordinated + school-safe | Yes | Yes, plus a soft penalty on school-zone roads during school windows |

## Results so far (approximate map)

School traffic is now modelled (term vs holiday, school windows, school zones) — see BLUEPRINT.md section 4b. Headline: at a 07:00 wave, school term cuts the typical app's on-time rate by 7–17 points; school-safe coordination helps most on closure days; starting the wave after drop-off helps more than any routing change (caveat in 4b).

Before school traffic (holiday conditions):

- Coordinated vs typical app, 400 vehicles: **+0.7 pts** on time (normal), **+0.6 pts** (closure) — small but consistent.
- Gain grows with fleet size: +0.1 at 100 vehicles, **+3.7 to +4.3 pts at 800** (all 18 setups significant).
- Most of v1's big gain was **live information** (static → live: +16.7 pts on closure days).
- Random spreading is much worse (−16 to −18 pts).
- Warnings: precision ~63% / recall 81% (normal), 92% / 96% (closure); probabilities overconfident in the middle range.

## Known limits

- Approximate map until the `--osm` run is redone with v2.
- Simulated traffic, demand, closures and costs; RM20/RM5 compensation is an assumption.
- Free-flow entry times, no queues; one 15-minute wave; single-stop trips.
- Driver fairness is measured (detours) but rotation across shifts is not simulated.

## Files

| File | Notes |
|---|---|
| `kuching_advisor.py` | **v2 engine** (use this) |
| `kuching_fleet.py` | v1 script, kept so v1 numbers can be reproduced |
| `prototype/fleet_sim.py` | First toy-grid prototype |
| `outputs/` | v1 outputs; `outputs/v2/` = v2 outputs |

## Design decision: no accounts for the public app

Public app = no accounts (settings on the phone, anonymous throwaway trip IDs). Fleets = company account with individual staff logins, roles and two-step sign-in (dispatchers handle customer data; actions are logged per person); drivers join with a company-issued code. The resulting risk, fake trips, is tested with `--fake-scan` — see BLUEPRINT.md section 8. **Do not add personal sign-up flows.**

## Design principle: tools, not priority

Accounts and payment buy tools, never road priority; every trip is allocated by the same neutral rule. Tested with `--priority-scan` — see BLUEPRINT.md section 9.

## For whoever picks this up (human or AI)

- Owner: Ming, Kuching time (UTC+8). Hackathon: Hackerdorm Track 1, "Predict Early, Decide Better".
- Judges ask: does the model help someone make a better decision, and can you prove it? Keep every claim tied to a measured comparison.
- Do not loosen the detour cap or tune parameters to manufacture a gain. If real-map coordination shows no benefit, report it and explain why (see the fleet-size result).
- Wording: "congestion-aware greedy assignment", "probabilistic simulation prototype", "simulated". Not "system optimum", not "machine learning".


## Advisor page (proof of concept)
`poc/advisor.html` is the web demo and practical-test tool (published as an artifact; needs the artifact runtime for the shared test log and road reports, planning works without it). It mirrors the approximate model in JavaScript, including traffic from outside Kuching. The real-map download (`--osm`) now covers Greater Kuching and caches to `data/greater_kuching_drive.graphml`.
