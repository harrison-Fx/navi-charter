# Brief for Replit — Kuching Dispatch Advisor, progress since your review

**From:** Claude (backup developer) · **Owner:** Ming · **Date:** 10 Oct 2026, 13:30 Kuching time
**Read with:** `README.md` (how to run), `BLUEPRINT.md` (plan + full results), `JOURNAL.md` (decision history)

Thank you for both reviews. They were right, and the main points are now in the code. This brief covers what changed, why, what we found, and what we need you to run and check.

---

## 1. Decisions since your review

| Decision | Rationale |
|---|---|
| **Public is the vision; fleets are the way in** (owner's call) | Coordination only works when many vehicles take part at once. One fleet provides that on day one; a public app needs thousands of users first. The simulation now backs this (section 3). |
| Kept your technical wording | "Congestion-aware greedy assignment", not system optimum. Wardrop's first principle = user equilibrium. Results are a "probabilistic simulation prototype", not machine learning. Herding is not Braess's paradox. |
| Rejected parts of a Gemini draft (v2.1) | It dropped the public vision, reintroduced unsourced claims (detour tolerance, how consumer apps balance load), misstated our old detour cap (said 1.15×, was 1.25×) and proposed loosening detours to 1.35×. Corrected version: `BLUEPRINT.md` (v2.2). |
| **Detour cap stays at 1.25×** | Your warning: don't loosen constraints to manufacture a result. |
| **Public app has no accounts** (owner's call) | Settings stay on the phone; trips use anonymous throwaway IDs; fleets use a company account with individual staff logins (roles, two-step sign-in, per-person action log) and driver join codes. Please don't add personal sign-up flows. The resulting fake-trip risk is tested with `--fake-scan` (BLUEPRINT section 8). |
| **Tools, not priority** (owner's concern) | Accounts and payment buy tools, never road priority; public trips use a neutral order (no self-declared urgency). Tested with `--priority-scan` (BLUEPRINT section 9): neutral order loses nothing, false urgency does not pay. Please keep the planner neutral. |
| **School traffic added** (owner's request) | Kuching's school drop-off and session change create sharp local jams; school zones should be avoided where possible but are sometimes unavoidable. |

## 2. What changed in the code — `kuching_advisor.py` (new; `kuching_fleet.py` kept as v1)

1. **Route choice (your Gate 1).** Yen's k-shortest paths replaced by a **penalty method**: find the fastest route, make its roads 1.5× more expensive *in the search only*, search again. The 70%-overlap filter is replaced by **bottleneck-aware diversity**: a route is a real alternative if it uses at least max(0.3 km, 10% of its length) of road the others don't, so short bypasses survive. `--routes=yen` keeps the old method for comparison.
2. **Fair comparison (your updated review).** All live methods get the **same simulated live view**:
   - static plan (average conditions — measures the value of live information)
   - live independent (typical navigation app)
   - live random split (does simple spreading explain gains?)
   - live coordinated (counts the fleet's own vehicles)
   - live coordinated + school-safe (new)
3. **Time-expanded loading.** Departures spread over the 15-minute wave; vehicles counted per 5-minute bin on each road, using free-flow entry times on the real clock (static approximation, no queues).
4. **Two ledgers.** Physical (on-time, vehicle-hours, P90, fuel, detours, school-zone passes) vs warnings (precision/recall, ETA coverage, Brier score, calibration table, compensation at RM5/RM10/RM20).
5. **Evaluation.** Separate random streams for vehicles, scenario days and algorithm sampling; paired differences with 95% CIs across days; 3 seeds; `--sweep` (fleet size 100–800 × 3 closure locations × seeds × term/holiday); `--wave-scan` (wave start times).
6. **School traffic.** School zones = roads within 300 m of OSM `amenity=school` (real map; cached to `data/kuching_schools.csv`) or *assumed* residential areas (approximate map). Extra traffic of 35% of capacity during assumed windows 06:45–07:30 and 12:30–13:30. Term vs holiday days. School-safe = soft penalty, not a ban. Passes are split into **avoidable** and **unavoidable** (the destination, or every acceptable route, is in a school zone).
7. **Real map.** `--osm` downloads once and caches `data/kuching_drive.graphml`; later runs work offline.

## 3. What we found (approximate map, simulated — not yet confirmed on real roads)

- **Most of v1's "herd-aware" gain was live information, not coordination.** Static → live: +16.7 pts on time on (holiday) closure days.
- **Coordination's gain grows with fleet size.** Holiday days, coordinated vs typical app: +0.1 pts at 100 vehicles; +0.6 to +0.9 at 400; **+3.5 to +4.5 at 800** (9/9 setups significant).
- **Random spreading hurts** (−15 to −30 pts).
- **School term** at a 07:00 wave cuts the typical app's on-time rate from 94.5% to 87.4% (normal) and 76.7% to 59.4% (closure).
- **Plain coordination pushes more vehicles through school zones** (it spreads traffic onto side roads). **School-safe coordination** cuts avoidable school passes (term closure: 230 → 158) and is best on term closure days: +3.5 pts at 400 vehicles; +3.6 at 800 (8/9 setups) vs +1.4 (3/9) for plain coordination. On normal term days it costs a little on-time.
- **Wave timing beats routing in this model:** typical app on time, term day, wave at 07:00 vs 07:30: 88.0% → 95.5% (normal), 60.2% → 77.1% (closure). **Caveat:** only school traffic varies with the clock; commuter traffic is held at peak level all day.
- **Warnings:** precision ~63–75% / recall ~80% on normal days; 90–93% / 95% on closure days. P(late) is **overconfident in the middle** (predicted 0.5–0.7 → observed 43% late; 0.7–0.9 → 65%).
- **Route-search check** on a dense synthetic grid (~2,500 junctions): Yen 279/400 vehicles with a choice in 42 s; penalty method 400/400 in 0.2 s. Not the real map — real Kuching (river, bridges) was harsher for Yen in your run.

Full tables: `BLUEPRINT.md` sections 4 and 4b; raw outputs in `outputs/v3/`.

## 4. What we need you to run (in order)

Please run from the project root and keep the console output of each.

1. `pip install -r requirements.txt`
2. `python kuching_advisor.py --osm --routes=yen --days 5 --seeds 1`
   → Reproduces your single-route finding with the new code, as a baseline.
3. `python kuching_advisor.py --osm`
   → Main real-road run (20 days × 3 seeds; est. ~10 minutes with school traffic).
4. `python kuching_advisor.py --osm --wave-scan --days 10 --seeds 2`
5. `python kuching_advisor.py --osm --sweep --days 10 --seeds 2`
   → Slowest; skip or cut further if time is short.
6. (Optional) `python kuching_advisor.py --osm --fake-scan --days 10 --seeds 2`
   → Fake-trip robustness on real roads.
7. (Optional) `python kuching_advisor.py --osm --priority-scan --days 10 --seeds 2`
   → Does neutral ordering still cost nothing on real roads? On the approximate map, targeted fake trips (30–50% of trips) erode the coordination gain at 800 vehicles.

**Send back:** the console logs; `fake_scan_osm.csv` if run; `results_osm.csv`, `ledger1_osm.png`, `warnings_osm.csv`, `wave_scan_osm.csv`, `sweep_osm.csv`, `fleet_size_effect_osm.png`; and **`data/kuching_drive.graphml` + `data/kuching_schools.csv`** (so Claude can rerun offline).

## 5. What we want you to check

**On the real-road results**
1. **Route diagnostics:** routes per OD pair, vehicles with a choice, how much longer alternatives are. If many pairs still have one route, say why (e.g. river crossings) — do **not** loosen the detour cap to fix it.
2. **Does coordination beat live independent on real roads**, with CIs? A null result is acceptable and should be reported as is.
3. **School zones:** how many schools were downloaded and how many road segments are flagged? Spot-check a few on a map — are the flagged roads plausible?
4. **Unavoidable school passes:** are they mostly vehicles whose *destination* is near a school (expected), or something odd?

**On the code** (please review, not rewrite)
5. `Model.bins` / `Model.trip`: is placing vehicles in 5-minute bins by free-flow entry time reasonable for a prototype, and is the conversion of per-bin counts to a 15-minute rate (`scale`) correct?
6. `run()`: is the comparison fair? All live strategies share the same `live` view per day/scenario; the static plan uses expected conditions incl. the school calendar but no daily noise or closure.
7. `warnings_for`: the calibration table shows overconfidence in the middle. Is the cause the sampling (samples drawn around the noisy observation), or something else?
8. `plan_coordinated`: the school penalty is RM3 per school-zone road per window. Any better way to express "avoid if possible" than a flat cost?

**Facts to verify from primary sources** (we have not checked these)
9. Malaysian school session times (morning session start, session change/afternoon start, dismissal) and the **2026 school term calendar** — official Ministry of Education source. Our windows (06:45–07:30, 12:30–13:30) are placeholders.
10. Any public source on typical **Kuching commuter peak times**, so we can add a time-of-day profile for general traffic before claiming a best wave start time.

## 6. Ground rules (same as your review)

- Label everything simulated as simulated; the OSM run validates execution, not real-world savings.
- Keep routing value, warning value and their combination separate.
- Don't tune parameters to produce a positive result. If something doesn't work on real roads, report it and explain why.
- Don't add unsourced statistics or claims about other companies' systems.

## 7. Still open on our side

- Report (Claude Doc) still shows v1 numbers; it will be updated once your real-road results are in.
- Commuter time-of-day profile (needs item 10).
- Pitch mockup of a driver screen (Android Auto style) — vision only, not built.
