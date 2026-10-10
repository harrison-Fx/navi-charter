# Update for Replit #3 — Kuching Dispatch Advisor

**From:** Claude · **Owner:** Ming · **Date:** 10 Oct 2026, ~16:20 Kuching time
**Applies on top of:** `kuching-dispatch-v7.zip`. Details: `BLUEPRINT.md` sections 12–13, `JOURNAL.md`.

## What changed
1. **Traffic from outside Kuching.** Samarahan (incl. Asajaya, Moyan), Siburan, Matang outer, Samariang and Sejingkat now send commuters in through their entry roads in the morning and back out in the evening. Volumes are assumptions (`EXTERNAL`, `JOBS`, `A["commuters"]`). New option `--commuters X` (0 = off).
2. **Real map covers Greater Kuching.** `--osm` now downloads a bounding box (`GREATER_BBOX`) instead of the Kuching place boundary and caches to `data/greater_kuching_drive.graphml`. The old `kuching_drive.graphml` is no longer used.
3. **Advisor page rules** (`poc/advisor.html`): only reroute when it saves ≥3 minutes or is clearly safer; only add a Maps stop when rerouting. Ming's phone test showed a stop at an area centre can send Maps into a side street.

## Please run
1. `python kuching_advisor.py --osm` (first run downloads Greater Kuching; send back `data/greater_kuching_drive.graphml` and `data/kuching_schools.csv`).
2. `python kuching_advisor.py --osm --commuters 0` for the comparison.
3. `python kuching_advisor.py --osm --wave-scan`.
4. Check the printed "Busiest roads in the morning commuter peak" list: do the top roads match where Kuching actually jams (Samarahan expressway end, Kuching–Serian / Penrissen, Matang road)?

## Please look for
- Traffic counts (JKR, DBKU, MBKS, MPP, Sarawak Ministry of Transport) for the Kuching–Samarahan Expressway, Kuching–Serian road and Jalan Matang, to replace the assumed volumes.
- On the real map: pick the waypoint as a node on the chosen trunk/primary road, away from junction turns (not an area centre).
