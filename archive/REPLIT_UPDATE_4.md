# Update for Replit #4 — judging rubric and what we need before the pitch

**From:** Claude · **Owner:** Ming · **Date:** 10 Oct 2026, ~23:50 Kuching time
**Applies on top of:** `kuching-dispatch-v8.zip` and `REPLIT_UPDATE_3.md` (those runs still stand). Context: `PITCH_PACK.md`.

## Why this matters
Track 1 is scored on five criteria (20 points each): problem & value, **predictive rigor & robustness**, decision support, explainability, live demo & pitch. Our weakest is **rigor**: all current numbers come from the approximate 16-area map with assumed volumes. The real-map run is the single biggest improvement we can make.

## What changed since v8 (FYI)
- App (`mobile/App.js`): risk level (Low / Medium / High) and a ranked **"Why this advice"** box (school rush, traffic from outside Kuching, closure, reported jam, crowding by planned trips, peak traffic). Bundle builds.
- New 3-minute pitch deck (6 slides) and `PITCH_PACK.md` (demo script, Q&A sheet, numbers table).

## Please run (priority order)
1. **Real map, main results:** `python kuching_advisor.py --osm` (Greater Kuching download; caches `data/greater_kuching_drive.graphml`). Send back `main_osm.txt`, `results_osm.csv`, `warnings_osm.csv`, `ledger1_osm.png`, and the two data files.
2. **Commuter comparison:** `python kuching_advisor.py --osm --commuters 0` → send the text output.
3. **Wave timing:** `python kuching_advisor.py --osm --wave-scan` → `wave_scan_osm.csv` + text.
4. **Robustness (pick what time allows):** `--osm --fake-scan`, `--osm --priority-scan`, `--osm --double-session 0.5 --wave-scan`.
5. **Sanity check the funnel:** does the printed "Busiest roads in the morning commuter peak" list on the real map match where Kuching actually jams (Samarahan expressway end, Kuching–Serian/Penrissen, Matang road, Petra Jaya→Satok)? Note mismatches.

If a full run is too slow on Replit: `--days 20 --seeds 2` is acceptable; say which settings you used.

## Please add (small code tasks)
1. **Calibration chart** (`plot_calibration(rows, fname)`): reliability diagram of predicted P(late) bins vs observed late share, for "typical app" and "coordinated", from the existing `_p` fields used by `calibration_table`. Save `calibration_<tag>.png`. This answers "low false alarms / resilient to noise" visually.
2. **Noise sweep** (`--noise-scan`): run term-day results for `noise_sigma` in 0.10, 0.25, 0.40 and `sensor_sigma` in 0.05, 0.10, 0.20; table of on-time (typical app vs coordinated) and warning precision/recall/Brier. Shows robustness to noisy and missing data.
3. **Pitch numbers export** (`pitch_numbers.py`): read the results CSVs and print exactly the table in `PITCH_PACK.md` → "Numbers used", for whichever tag is given (`approx` / `osm`), so the slides can be updated in one go.

Keep the existing outputs and CSV formats unchanged; add new files only.

## Please look for (sources; send links, don't guess)
- **Traffic counts** for the Kuching–Samarahan Expressway, Kuching–Serian road (Penrissen), Jalan Matang: JKR "Road Traffic Volume Malaysia" reports, JKR Sarawak, Ministry of Transport Sarawak, DBKU / MBKS / MPP.
- **School session types** (morning / afternoon / both) for Kuching schools: Sarawak Education Department or district education office lists.
- **Waze for Cities** eligibility for Malaysian councils (to support the "live data via councils" roadmap line).

## Facts to verify before the slides go out
- 38 schools figure and that they are in Kuching (from `data/kuching_schools_sessions.csv`).
- Entry-road descriptions (Samarahan Expressway into Stutong; FT 8302 via Muara Tabuan / Pending; Kuching–Serian via Penrissen; Sejingkat via the barrage road).
- Fuel price used (`fuel_rm_per_l` 2.15, diesel) is still current in Sarawak.

Send results as a zip named `replit-results-<date>.zip` with a short note of what ran and any errors.
