# Kuching Dispatch Advisor — Implementation Blueprint v2.2

**Date:** 10 October 2026 · **Supersedes:** v2.1 (drafted with Gemini) · **Basis:** Replit vision review (updated), prototype `kuching_advisor.py`

> **Vision:** free-flowing Kuching roads for everyone. **Way in:** delivery fleets, because a fleet can coordinate hundreds of vehicles from day one, while a public app needs thousands of users before coordination does anything.

This version keeps v2.1's good parts (two ledgers, penalty route search, departure bins, evidence gates) and fixes what Replit's review would reject.

---

## 1. What changed from v2.1, and why

| v2.1 said | v2.2 says | Why |
|---|---|---|
| City-wide coordination is "unviable"; drop the public vision | Public stays the **vision**; fleets are the **entry point** | Owner's decision. The new simulation also shows coordination value grows with the share of vehicles taking part (section 4) |
| Consumer apps balance load "silently via GNNs and path splitting"; no consumer accepts a 4-minute detour | Removed | No source. Google's GNN paper covers arrival-time prediction, not route allocation. Detour-tolerance figures are unsourced |
| Old detour cutoff was 1.15× | It was **1.25×** | Factual error about our own code |
| Raise detour budget to 1.35×; "Kuching bypasses are 25–35% longer" | Detour cap **stays at 1.25×** | Loosening constraints to force a result is what the review warned against; the 25–35% figure is unsourced |
| Gate 1 target: ">75% of OD pairs have 2–3 alternatives" | Report candidate availability and reasons; no target to hit | A target invites tuning until it is met |
| (missing) | **Fair comparison**: every routing method gets the same live view | Old results mixed the value of live information with the value of coordination |
| (missing) | **Bottleneck-aware diversity** replaces the 70% overlap filter | Short bypasses around a jam were being thrown away |
| "System optimum", "Wardrop equilibrium" for our method | **Congestion-aware greedy assignment** | Not a global optimum. Wardrop's first principle is user equilibrium; the second is system optimum |

## 2. Wording rules for the pitch and report

- The model is a **probabilistic simulation prototype** (BPR congestion + Monte Carlo), not a trained machine-learning model.
- Herding is **not** Braess's paradox (Braess = adding capacity makes equilibrium worse).
- "Live" inputs are **simulated observations** with sensor noise.
- Every number is **simulated** unless stated otherwise. The OSM run so far validates execution, not routing benefit.
- Differentiate on fleet load, deadlines and actions — not on claims that competitors lack coordination.
- Primary sources to cite: Nature Cities 2026 routing study (https://www.nature.com/articles/s44284-026-00443-x); Google Maps GNN ETA paper (https://arxiv.org/html/2108.11482v1).

## 3. Gate 1 — what was built (in `kuching_advisor.py`)

1. **Penalty route search.** Find the fastest route, make its roads 1.5× more expensive *in the search only*, search again. Real travel times are untouched. Detour cap 1.25×.
2. **Bottleneck-aware diversity.** A route counts as a real alternative if, against every kept route, it uses at least max(0.3 km, 10% of its length) of road the other doesn't. Short bypasses survive.
3. **Time-expanded loading.** Departures spread over the 15-minute wave; vehicles counted per 5-minute bin on each road using free-flow entry times (static approximation — no queues).
4. **Fair comparison**, same live view for all live methods:
   - *Static plan* — average conditions, no live info (measures the value of live information)
   - *Live independent* — typical navigation app
   - *Live random split* — tests whether simple spreading explains gains
   - *Live coordinated* — congestion-aware greedy assignment
5. **Two ledgers** — physical (on-time, vehicle-hours, P90, fuel, detours) and notices (precision/recall, ETA coverage, calibration, compensation at RM5/10/20).
6. **Separate random streams** for vehicles, scenario days and algorithm sampling; **paired differences with 95% CIs across days**; **3 seeds**; `--sweep` over fleet size × closure location × seed.
7. **Diagnostics** printed every run: routes per OD pair, vehicles with a choice, alternative length.

## 4. Gate 1 — results so far (approximate map, simulated)

*Section 4 was run before school traffic was added and matches **school-holiday** conditions. Section 4b adds school traffic.*

**Main run:** 400 vehicles, 60 days × 3 seeds, closure = 60% capacity loss on Padungan–Pending.

| Strategy | On time, normal | On time, closure | Vehicle-hours, closure |
|---|---|---|---|
| Static plan (average traffic) | 92.4% | 60.0% | 276 |
| Live independent (typical app) | 94.7% | 76.7% | 121 |
| Live random split | 76.5% | 60.7% | 170 |
| Live coordinated | 95.4% | 77.3% | 120 |

Paired difference, coordinated − independent: **+0.72 ± 0.24 pts** (normal), **+0.56 ± 0.32 pts** (closure).

**What this means**
- Most of the earlier "herd-aware" gain was the value of **live information** (static → live: +16.7 pts on closure days), not coordination.
- **Random spreading hurts** (−16 to −18 pts). Coordination is not just "spread vehicles out".
- **Coordination value depends on fleet size** (sweep, 3 seeds × 3 closure locations, 30 days each):

| Vehicles per wave | Coordinated gain (normal) | Coordinated gain (closure) | Setups clearly above zero |
|---|---|---|---|
| 100 | +0.1 pts | +0.1 pts | 0 of 18 |
| 200 | +0.1 pts | +0.2 pts | 2 of 18 |
| 400 | +0.6 pts | +0.9 pts | 10 of 18 |
| 800 | +4.3 pts | +3.7 pts | 18 of 18 |

This is the honest link between the fleet entry point and the public vision: **the more vehicles coordinate, the more it pays.**

**Warnings (ledger 2), threshold 0.5:** precision 62–64% / recall 81% on normal days; 92% / 96% on closure days; ETA coverage 81–91%. Calibration is **overconfident in the middle** (predicted 0.5–0.7 → observed 37% late; 0.7–0.9 → 59%). Needs calibration on real trips (Gate 2). Compensation savings depend entirely on the RM5/RM10 assumption; at RM20 they are zero.

**Route search check (dense, real-size test grid, ~2,500 junctions):** old method 279/400 vehicles with a choice in 42 s; new method 400/400 in 0.2 s. A full simulated day takes ~3.6 s, so a real-map run of 20 days × 3 seeds takes ~4 minutes.

**Still open:** the real Kuching OSM run with the new code (run `RUN-REAL-MAP.bat` on a PC; Claude's workspace cannot reach OpenStreetMap).


## 4b. School traffic (added 10 Oct, 13:15)

**What was added**
- **School zones.** Real map: roads within 300 m of an OpenStreetMap school (`amenity=school`, cached to `data/kuching_schools.csv`). Approximate map: secondary/tertiary roads touching residential areas *assumed* to contain schools.
- **School windows (assumptions to verify against the Ministry of Education calendar):** 06:45–07:30 drop-off and 12:30–13:30 session change. School-zone roads get extra traffic equal to 35% of capacity during a window.
- **Day types:** school term vs school holiday (holiday = no school spike; everything else equal, so the school effect is isolated).
- **Clock time:** the wave starts at 07:00 by default (`--wave HH:MM`), so departures and road entries are placed on the real clock.
- **School-safe coordination:** a soft planning penalty (RM3 per school-zone road during a window), not a ban. School zones are sometimes unavoidable, so passes are split into **unavoidable** (the destination, or every acceptable route, is in a school zone) and **avoidable**.

**Main run, 400 vehicles, wave 07:00 (60 days × 3 seeds)**

| Day, scenario | Typical app on time | Coordinated | Coordinated + school-safe | School passes: typical / coordinated / school-safe (avoidable) |
|---|---|---|---|---|
| Term, normal | 87.4% | +0.5 ± 0.2 pts | −0.1 ± 0.2 pts | 282 (21) / 310 (50) / 266 (6) |
| Term, closure | 59.4% | +1.3 ± 0.4 pts | **+3.5 ± 0.6 pts** (+6 vehicle-hours) | 491 (230) / 509 (249) / 419 (158) |
| Holiday, normal | 94.5% | +0.9 ± 0.3 pts | same as coordinated | 0 |
| Holiday, closure | 76.7% | +0.6 ± 0.3 pts | same as coordinated | 0 |

**What it shows**
- School term costs the typical app 7 points on normal days and 17 points on closure days at a 07:00 wave.
- **Plain coordination pushes more vehicles through school zones** (it spreads traffic onto side roads) — the neighbourhood spillover the review warned about.
- **School-safe coordination** cuts avoidable school passes sharply, and on closure days is also the best for on-time delivery. On normal term days it costs a little on-time. It should be a dispatcher setting that shows its cost, not a hidden default.
- Fleet-size sweep (20 days, 3 seeds × 3 closure locations): at 800 vehicles on term-day closures, school-safe gains **+3.6 pts (8/9 setups significant)** vs plain coordination +1.4 (3/9). On term normal days the reverse: coordination +3.3, school-safe +0.6. See `fleet_size_effect_approx.png`.

**Wave timing matters as much as routing** (term days, 400 vehicles, 20 days × 3 seeds):

| Wave starts | Typical app, normal | Typical app, closure |
|---|---|---|
| 06:30 | 93.9% | 73.2% |
| 07:00 | 88.0% | 60.2% |
| 07:30 or later (outside school windows) | 95.5% | 77.1% |
| 12:30 | 88.0% | 60.1% |

Holding a wave until drop-off ends is a simple dispatcher decision with a large effect. **Caveat:** in this model only school traffic varies with the clock; general commuter traffic is held at peak level all day. Real work traffic also peaks around 07:30–08:00, so the best start time must be confirmed with real data before it is claimed.

## 5. Evidence gates

| Gate | Do | Pass when (report either way) |
|---|---|---|
| 1. Prototype | Run `python kuching_advisor.py --osm` and `--osm --sweep` (`RUN-REAL-MAP.bat`); document route availability and changes | Route diagnostics explain choice availability on real roads; paired differences reported with CIs |
| 2. Data | One courier: consented GPS traces, dispatch and arrival times, promises, notification records, real costs; school session times and calendar | ETA and P(late) calibrated; RM20/RM5 replaced by real figures or shown as ranges |
| 3. Pilot | Shadow mode first (advice only), then wave-level randomised crossover | On-time, vehicle-minutes, overrides and detour fairness measured against comparable waves |
| 4. Expansion | Second fleet or one corridor; then the free public app | Road-level travel times and neighbourhood impact measured, not assumed |

## 6. Trust is part of the product

- **Driver fairness:** bound extra time and distance per driver, track cumulative detours, rotate who takes them.
- **Dispatcher control:** show risk change, ETA range and reason; allow and log overrides; start in shadow mode.
- **Road and data safeguards:** avoid unsuitable residential roads; agree GPS access, retention and aggregation before any city-level sharing.

## 7. Vision statement

> Free-flowing Kuching roads for everyone. We start with delivery fleets: coordinating their own vehicles to prevent avoidable delays, and turning uncertain travel times into clear dispatcher actions for the rest. Every vehicle that joins makes the roads better for all — which is why the public app follows once fleets prove it works.

## 8. Accounts, privacy and abuse (decided 10 Oct, 13:45)

**Design decision**
- **Public app: no accounts.** Saved places (home, work, school), school-run times and preferences stay on the phone. Phone changes are covered by Android's built-in app-data backup (through the user's own Google account, nothing held by us) or an "export settings" file / QR code.
- **Anonymous trips.** For coordination the server only needs "a trip from area A to area B around 07:10" — each trip gets a random, throwaway ID, deleted when the trip ends. No identity, less personal data, simpler compliance with Malaysia's Personal Data Protection Act (PDPA).
- **Fleets: a company account with individual staff logins** (decided 14:09). Dispatchers handle customer names, addresses and phone numbers, so each staff member gets their own login with a role (admin, dispatcher, view-only) and two-step sign-in. Overrides and actions are logged per person, and access is removed when someone leaves. **Drivers join with a code issued by their company**, no personal accounts.
- **Principle:** accounts where the responsibility and sensitive data are (businesses); no accounts where they would only add friction (the public).

**The risk this creates: fake trips.** Without accounts, someone could submit fake trip requests. Tested with `--fake-scan` (approximate map, school-term days, wave 07:00; fake trips are counted by the planner but never drive):

| Fake trips (share of real) | 400 vehicles: random / targeted, vs honest coordination | 800 vehicles: random / targeted, vs honest coordination (normal days) |
|---|---|---|
| 10% | ±0.0 / −0.05 pts | +0.1 / −0.5 pts |
| 30% | ±0.0 / −0.3 pts | +0.3 / **−1.7 pts** |
| 50% | +0.0 / −0.5 pts | +0.4 / **−4.7 pts** (worse than the typical app) |

- **Random spam is harmless**; on closure days it even helps slightly (the planner becomes more cautious).
- **Targeted abuse is the real risk:** flooding one corridor with fake trips steers real vehicles away from it. The damage grows with fleet size, because that is where coordination matters most.
- The typical app is unaffected by fake trips (it ignores other vehicles), so it is the floor; with protections in place, coordination should stay above it.

**Protections (to build; not yet tested in the simulation)**
1. One active trip per device; per-device rate limits.
2. Genuine-app check on every trip request (Android Play Integrity).
3. **Anomaly detection on trip requests**: flag sudden bursts of near-identical trips on one corridor, and count unverified trips at reduced weight in the planner. This is anomaly detection, one of the track's suggested applications.
4. Fleet trips come from logged-in company staff, so they are trusted; the risk applies to the public app.

Next simulation step (optional): test protection 3 by down-weighting suspicious trips and re-running `--fake-scan`.

## 9. Tools, not priority (decided 10 Oct, 14:11)

**The worry (Ming):** if accounts or payment buy better routes, everyone buys them, everyone is "first", and the system collapses back into everyone taking the same best road.

**Principle:** accounts and payment buy **tools** (dispatcher console, warnings, planning, reports), **never road priority**. Roads are allocated by the same neutral rule for every trip, whoever sends it. Across different fleets the coordinator must be neutral; for public trips, self-declared urgency must not change the order (use request time or rotation), and detours are shared so no one always loses.

**Test** (`--priority-scan`, approximate map, school-term days, 15 days × 3 seeds). The coordinated planner serves trips in an order; earlier trips get first pick. Claimed urgency changes only what the planner sees; results use true deadlines.

| Change vs honest tightest-deadline-first (on-time pts) | 400 vehicles, normal / closure | 800 vehicles, normal / closure |
|---|---|---|
| Neutral order (first come, first served) | +0.1 / −0.1 | +0.1 / −0.1 (no real difference) |
| Every trip claims maximum urgency | −0.3 / −0.1 | −0.6 / −0.4 |
| 30% falsely claim urgency: the cheaters themselves | −0.2 / −0.0 | −0.3 / **−1.0** |
| 30% falsely claim urgency: honest trips | +0.0 / +0.1 | −0.1 / +0.3 |
| For scale: typical app (no coordination) | −0.1 / −0.9 | −3.0 / +0.4 |

**What it shows**
- The gain comes from **counting where everyone is going**, not from who goes first: a neutral order loses nothing. So the public app can use a neutral order at no cost.
- Universal "urgent" claims dent the gain (−0.4 to −0.6 pts at 800) but do **not** return it to square one (the typical app is −3.0 on normal days).
- **Lying does not pay** in this planner: false urgency makes the planner treat that trip as late anyway, so it stops protecting its deadline. Honest trips are unaffected or slightly better off.
- Caveat: this holds for this planner's cost rule; a different planner could reward false claims, so the principle (no self-declared priority for public trips) stays regardless.
- (The +0.4 for the typical app on 800-vehicle term closures matches section 4b: on term days plain coordination needs the school-safe setting.)

## 10. Product shape: an advisor, not a map app (decided 10 Oct, 14:58)

**Plan here, drive there.** The app advises; Google Maps or Waze drives.

| Our app (the advisor) | The maps app the user already has |
|---|---|
| When to leave (e.g. hold the wave until 07:30) — the biggest effect in the simulation | Turn-by-turn directions and voice |
| Which corridor, counting everyone else's trips; avoids school zones | Live rerouting along the way |
| Chance of being late; early customer notice (fleets) | The map itself |
| Sends the trip anonymously so trips can be coordinated | |

**Handoff options**
- **Google Maps URL** with a destination and a waypoint on the chosen bypass, so Maps follows our corridor. Up to 3 waypoints on mobile browsers, up to 9 otherwise; not every Google Maps product honours waypoints ([Maps URLs](https://developers.google.com/maps/documentation/urls/guide)).
- **Google Navigation Connect** launches Google Maps or Waze and returns trip telemetry (useful for the dispatcher), but takes one destination and no waypoints, is driving-only, and is experimental ([Google docs](https://developers.google.com/maps/documentation/navigation/connect/launch-navigation-app)).
- Waze: destination only.

**Trade-off:** after the handoff the maps app optimises for that one driver and may reroute back onto the busy road; the bypass waypoint reduces this. **Timing advice survives any handoff** — the maps app cannot change when you left.

**Path:** hackathon and pilot = advisor + handoff (small build, familiar to drivers, no map licensing). Later, only if more control is needed = own in-app navigation / Android Auto.

**Pitch line:** "We don't replace Google Maps. We tell it when to leave and which way to go."

## 11. Kuching schools and session types (added 10 Oct, 15:40)

**Data:** `data/kuching_schools_sessions.csv` — 38 Kuching schools (secondary with postcodes; primary where the name gives the area) from the [Wikipedia list of schools in Sarawak](https://en.wikipedia.org/wiki/List_of_schools_in_Sarawak), each mapped to an approximate area of our map. Columns: name, level, area, postcode, session, session_source, location_source.

**Sessions are not verified.** No open government dataset found lists individual schools with session type (the DOSM dataset gives counts per district only: [schools_district](https://open.dosm.gov.my/data-catalogue/schools_district)). Every school is `unknown`, treated as **morning session** by default (`A["unknown_session_as"]`). Fill the `session` column (`morning` / `afternoon` / `both`) and `session_source` as sources are found — the engine uses them automatically, on both the approximate and the real map (real-map schools are matched by name).

**Session times (assumption):** morning 07:30–13:30, afternoon 13:30–18:30, as reported by a parents' association chairman in Kedah ([Kosmo, 5 Feb 2023](https://www.kosmo.com.my/2023/02/05/tidak-sesuai-bagi-sekolah-ada-dua-sesi/)) — typical, not Kuching-specific. Afternoon sessions in Sarawak can end as early as 17:00 in Ramadan ([The Rakyat Post](https://www.therakyatpost.com/trpbm/berita/2025/02/18/sekolah-sesi-petang-tamat-awal-pada-bulan-ramadan-kpm/)). Traffic windows used:

| Session | Windows |
|---|---|
| Morning | 06:45–07:30 arrival, 13:15–14:00 dismissal |
| Afternoon | 12:45–13:30 arrival, 18:15–19:00 dismissal |
| Both | 06:45–07:30, 12:45–14:00 changeover, 18:15–19:00 |

Each road's windows are the union of its nearby schools' windows; the extra traffic is half the boost with one school, full with two or more.

**Results (approximate map, 400 vehicles, wave 07:00, 60 days × 3 seeds)** — similar to section 4b: term-day closure, typical app 57.4% on time; coordinated +1.6 ± 0.4 pts; **school-safe +4.0 ± 0.6 pts** (+6.8 vehicle-hours). Normal term day: coordinated +0.4, school-safe −0.1.

**Wave timing (term days, 15 days × 3 seeds), typical app on time, normal / closure:**

| Wave starts | All schools morning-only (default) | Half of primary schools two-session (sensitivity) |
|---|---|---|
| 07:00 (drop-off) | 88.5% / 58.4% | 88.5% / 58.4% |
| 07:30–10:00 | 95.4% / 77.0% | 95.4% / 77.0% |
| 12:45 | 95.4% / 76.9% | **89.3% / 64.5%** (changeover) |
| 13:15 (dismissal) | 88.5% / 58.2% | 88.5% / 58.2% |
| 18:00 | 95.4% / 77.0% | **94.1% / 74.8%** (evening dismissal) |

**What it shows:** two daily problem windows (drop-off and dismissal), plus a midday and an evening one wherever schools run two sessions. Session type changes the advice for an area, so verifying it is worth the effort (Gate 2 data task). School-safe routing matters most when a closure overlaps a school window (+4.2 pts at 07:00 and 13:15).

**Run:** `python kuching_advisor.py --wave-scan --double-session 0.5` for the two-session sensitivity.


## 12. Traffic from outside Kuching (added 10 Oct, 16:20)

**Why:** much of Kuching's peak traffic starts outside the city (Samarahan incl. Asajaya and Moyan, Siburan on the Kuching–Serian road, Matang outer, Samariang, Sejingkat) and funnels in through a few entry roads, then merges onto city roads. The earlier model treated every road's traffic as local and the same in both directions.

**What changed (engine and advisor page):**
- Five outside areas with entry roads (`EXTERNAL` in `kuching_advisor.py`): Samarahan → Stutong (Kuching–Samarahan Expressway) and → Tabuan Jaya (FT 8302 Jalan Mambong–Sejingkat via Muara Tabuan / Pending); Siburan → Kota Sentosa (Kuching–Serian road / Penrissen); Matang outer → Matang; Samariang → Petra Jaya; Sejingkat → Bintawa (barrage road). Entry roads are from public sources; **volumes and capacities are assumed** (600 / 450 / 250 / 200 / 120 vehicles per 15 min inbound at the morning peak).
- Commuters go to assumed job areas (`JOBS`), assigned in 4 slices on the then-fastest path, so they spread over entry roads as those fill. Merging shows up where these flows meet city roads.
- **Tidal flow:** inbound peaks 07:20, outbound 17:45 (15% trickle off-peak). The same road can be jammed one way and clear the other.
- With commuters on, the old background level counts as 80% local traffic (`local_share`) to avoid double counting. Totals are not calibrated, so compare *where and when* roads jam, not absolute on-time levels between the two runs.
- Real map: the OpenStreetMap download now covers a Greater Kuching box (`GREATER_BBOX`, cache `data/greater_kuching_drive.graphml`). Each outside area starts at the junction nearest its centre.
- Option `--commuters X` scales the layer (0 = off).

**Results (approximate map, 60 days × 3 seeds, simulated, `outputs/v7/`):**

Busiest roads at the morning peak (incl. inflow): Stutong → Simpang Tiga (v/c 1.32, mostly Samarahan traffic), Simpang Tiga → Batu Lintang (1.19), Batu Lintang → Satok (1.14), Petra Jaya → Satok (1.14), Airport → Batu Lintang (1.12), Kota Sentosa → Airport (1.12, Siburan / Serian traffic).

| Term day, 400 vans at 07:00 | With outside commuters | Without |
|---|---|---|
| Coordinated vs typical app, normal day | +0.08 ± 0.16 pts | +0.56 ± 0.20 |
| Coordinated vs typical app, road closure | +1.67 ± 0.46 | +1.81 ± 0.43 |
| School-safe vs typical app, road closure | +2.89 ± 0.55 | +4.11 ± 0.67 |

**Reading:** when the jams sit on the few entry and merge roads, there are fewer genuine alternatives, so spreading trips helps less on a normal day; it still helps when a road is closed. The bigger lever for trips that cross these funnels is **when to leave** (wave scan: 06:30 and 07:30+ are much better than 07:00 and 13:15). This supports leading with leave-time advice and only rerouting when it is clearly worth it (section 13).

**To verify:** JKR / council traffic counts on the Samarahan expressway, Kuching–Serian road and Matang road; real job locations; school data for the outside areas (not yet included).

## 13. Sensible routes, not just fast ones (added 10 Oct, 16:20)

First phone test: Google Maps followed our extra stop but turned into a side street and back (the stop was an area's centre point, which can sit on a back lane). Rules now in the advisor page:
- **Only reroute when it's worth it:** keep the usual fastest road unless the other way lets you leave at least 3 minutes later or is clearly safer (5+ points less chance of being late).
- **Only add a stop when we reroute.** On the usual road, Google Maps picks the streets itself.
- Every rerouted plan also offers "Open without the extra stop".
- The test log records "Kept it, but made an odd detour".
- Real version: place the stop on a node of the chosen main road (trunk/primary) away from turns, from the OSM graph, never an area centre. Detour cap (25%) stays.
