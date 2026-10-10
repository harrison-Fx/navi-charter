# Project Journal — Kuching Herd-Aware Dispatch Advisor

Hackathon: Hackerdorm × BuilderX, Track 1 "Predictive Model Track: Predict Early, Decide Better"
Owner: Ming · Started: Sat 10 Oct 2026 (Kuching time, UTC+8)

Track theme: *How can AI spot problems before they become expensive, and help someone decide what to do about them?*
Core judging question: *Does your model help someone make a better decision, and can you prove it?*

---

## 10 Oct 2026

### 09:52 — Idea search
- Wanted something doable in a day or a week.
- Ideas considered: machine failure (AI4I dataset), late invoices, at-risk students, flood alerts, dengue hotspots, hiking risk.
- **Reminder noted:** Kiro credits had to be claimed **before Oct 10** — check whether this was done.

### 09:53 — Haze alert considered
- Feasible: NASA FIRMS hotspots + Open-Meteo air quality/weather → predict next-48h air-quality band.
- Key tip kept for later: always beat the "tomorrow = today" baseline.
- Not chosen.

### 09:55 — Business ideas considered
- Bakery food waste (1-day), late delivery risk (DataCo), churn with retention budget, SME cash-flow crunch (1-week), stock-out advisor.

### 09:57 — Traffic jam idea (chosen direction)
- Ming's insight: a shortcut stops being good once everyone takes it ("herd effect").
- Framed as user-optimal vs system-optimal routing (Wardrop equilibrium).
- Data problem: no free live traffic for Malaysia → **simulate** (networkx toy, later SUMO/OSM).

### 09:59 — Pivot to business user
- Reframed from commuters to **delivery fleets / dispatchers**: a platform controls many vehicles, so it can plan them together.
- Adds "decide better": late-delivery warnings with recommended actions and ringgit cost.

### 10:02 — Method agreed (Ming's framing)
- Group vehicles dispatched in a short window, assign routes as a group, cap the detour, include fuel cost.
- Refinements adopted: predict travel time at arrival (counting already-assigned vehicles), idle fuel in jams, tight-deadline vehicles first, driver fairness noted for later.
- Implementation path: greedy incremental assignment first; optimiser (PuLP/min-cost flow) only if time allows.

### 10:30 — Judging slides received → build started
- Strong-solution checklist: specific problem, clear user, decision support, robust on noisy/unfamiliar data, minimise false alarms, explain recommendations, measurable impact with realistic assumptions.
- Track's suggested areas include "supply chain anomaly detection" — project fits there.
- Built `prototype/fleet_sim.py` (6×6 grid toy city, 150 vans).
  - First run: no herd effect (vans spread over too many depots) → concentrated vans into 2 hubs.
  - Result: naive 50% on time → herd-aware 87%.
  - Weakness found: surprise closure hurt the plan badly (no re-planning).

### 10:34 — Focused on Kuching
- OpenStreetMap download blocked in the Claude workspace → built an **approximate Kuching corridor model** (16 real area names, rough coordinates, 30 simplified two-way links). Real map supported via `--osm` (works on a normal machine).
- Run 1: nothing jammed (too few route alternatives, light traffic) → added 6 neighbourhood back-roads, heavier peak traffic, detour cap 25%.
- Run 2: herd-aware helped, but pre-departure warnings almost never fired (random day-to-day noise can't be predicted in advance).
- **Key design change:** warnings moved to a **live check at dispatch** using today's traffic (with sensor error). This also lets the advisor see the closure and react.
- Tested the `--osm` code path with a mock OSM graph (passes). Added route de-duplication + speedups for big real maps.

### Final results (200 held-out simulated days, 400 vehicles, one 15-min peak window)

| Strategy | On time (normal) | On time (closure) | Cost normal | Cost closure | Unwarned late (closure) |
|---|---|---|---|---|---|
| Typical app | 92% | 61% | RM3,146 | RM9,010 | 157 |
| Herd-aware batch | 94% | 74% | RM2,902 | RM6,114 | 102 |
| + live early warnings | 95% | 81% | RM2,598 | RM3,811 | 5 |

Warning quality at threshold 0.5: precision 63% / recall 83% (normal), 93% / 97% (closure).
Threshold trade-off: 0.3 → 46%/91% · 0.5 → 63%/83% · 0.7 → 73%/69%.

### 10:45 — Report drafted
- Claude Doc: https://claude.ai/code/artifact/f55f6f6c-977a-48b8-8a15-600f5fa565a0
- Sections: problem statement, background, objectives, target users, scope & assumptions, proposed solution (with flow diagram), evaluation & results, judging-criteria alignment, limitations & future work.
- Open comment in the doc: keep the RM20 late-delivery cost or replace it with a real courier's refund figure?

### 10:52 — Google Maps comparison
- Standard Google Maps routes each driver individually (not herd-aware).
- Google ran a ~6-month experiment in 10 US cities nudging a small share of drivers off ~100 congested segments per city; ~2% speed gain on targeted segments; published in *Nature Cities*, June 2026; research, not confirmed as a feature.
- Pitch angle: Google can only *nudge* the public; a fleet *controls* its vehicles, and we optimise deliveries (deadlines, RM, customer warnings), not just road speed.
- Sources: https://zeli.app/story/48881967 · https://pbxscience.com/?p=22825

### 11:21 — Handoff to Replit
- Moving development to Replit; Claude is backup. This package = code + outputs + journal + handoff notes.

---

## Decisions log (quick reference)

| Decision | Why |
|---|---|
| Fleet dispatch, not commuter app | Platform controls its vehicles → can actually coordinate; clearer user and ringgit impact |
| Simulation, not real traffic | No public live traffic for Kuching; be upfront with judges |
| Greedy batch assignment | Fast, simple, already prevents herding; optimiser optional |
| Detour cap 25% | Keeps suggested routes acceptable to drivers |
| Live check at dispatch for warnings | Pre-departure warnings can't see day-to-day noise; live check also handles closures |
| Hubs: Pending, Kota Sentosa | Plausible logistics locations; not verified against a real courier |

## Open questions
- [ ] Were the Kiro credits claimed before Oct 10?
- [ ] Keep RM20 late cost, or use a real courier refund figure?
- [ ] Do the hub locations match a real Kuching courier?
- [ ] Run `--osm` on a real machine and re-check results on the real road network.

---

## 10 Oct 2026 (afternoon)

### 11:59–12:06 — Report expanded (hackathon framing)
- Added stakes, investment case, conventional maps comparison, competitors, key technology, dataset rationale; general public added as second audience (their stake = time).

### 12:26 — Replit vision review received
- OSM run (1,985 junctions): 371/400 vehicles had only one route → herd-aware = typical app; cost drop came only from the RM20→RM5 warning assumption.
- Corrections accepted: "congestion-aware greedy assignment" (not system optimum); Wardrop 1st principle = user equilibrium; separate routing vs notification value.

### 12:28 — Decision: public as vision, fleets as the way in
- Reason: coordination needs many vehicles at once; one fleet provides that on day one, a public app needs thousands of users first.

### 12:38–12:48 — Replit updated review + Gemini blueprint v2.1
- Updated review: old comparison mixed live information with coordination → fair comparison needed; 70% overlap filter may discard useful short bypasses.
- Gemini blueprint: good structure (two ledgers, penalty search, 5-min bins, gates) but dropped the public vision, re-introduced unsourced claims, misstated old detour cap (said 1.15×, was 1.25×), proposed loosening detours to 1.35×. Corrected in BLUEPRINT.md (v2.2).

### 12:53–13:30 — Gate 1 built: `kuching_advisor.py` (v2)
- Penalty route search + bottleneck-aware diversity; 5-minute departure bins; fair four-way comparison with the same live view; two ledgers; paired CIs; 3 seeds; fleet-size sweep.
- Dense real-size test grid: old search 279/400 vehicles with a choice (42 s); new 400/400 (0.2 s).
- **Key finding:** at 400 vehicles coordination adds only +0.6 to +0.7 pts on time; at 800 it adds +3.7 to +4.3 pts (18/18 setups significant). Most of v1's gain was live information, not coordination. Random spreading hurts.
- Supports the vision honestly: coordination pays off as more vehicles take part.

### Open
- [ ] Run the real map: `RUN-REAL-MAP.bat` on Ming's PC (Replit dropped 11 Oct).
- [ ] Update the report (Claude Doc) to v2 framing and results.
- [ ] Warnings calibration is overconfident mid-range; needs real trip data (Gate 2).

### 13:14–13:40 — School traffic added
- Ming: school traffic was not considered; school zones should be avoided where possible but are sometimes unavoidable.
- Added school zones (OSM schools on the real map; assumed residential areas on the approximate map), school windows on the real clock (assumed 06:45–07:30 and 12:30–13:30, to verify), term vs holiday days, school-safe coordination as a soft penalty, and avoidable vs unavoidable school-zone passes.
- Findings (approximate map, simulated): term days cut on-time by 7–17 pts at a 07:00 wave; plain coordination pushes more vehicles through school zones; school-safe coordination cuts avoidable passes and is best on term closure days (+3.5 pts at 400 vehicles; +3.6 at 800) but costs a little on normal term days; starting the wave after drop-off (07:30) beats any routing change in this model (caveat: commuter traffic held flat across the day).
- Ming asked about an Android Auto version — answered in chat.

### Open (added)
- [ ] Verify school session times and term calendar (Ministry of Education).
- [ ] Add a time-of-day profile for general commuter traffic before claiming a best wave start time.

### 13:41–14:00 — Accounts, privacy and fake trips
- Ming: account management is a hassle; prefer not to need accounts to save settings.
- Decision: public app with no accounts (settings on the phone, anonymous throwaway trip IDs; simpler PDPA compliance); fleets use one company login, drivers join by code/QR.
- Risk identified: fake trip requests. Added `--fake-scan`.
- Findings (approximate map, term days): random fake trips are harmless; **targeted** fake trips on one corridor erode coordination — at 800 vehicles, 30% fakes cut the gain from +3.0 to +1.3 pts and 50% make coordination worse than the typical app. Protections: one active trip per device, Play Integrity check, anomaly detection on bursts of identical trips (fits the track's anomaly-detection theme), down-weighting unverified trips.

### Open (added)
- [ ] Optional: simulate the anomaly-detection protection (down-weight suspicious trips) and re-run `--fake-scan`.
- [ ] Report: add privacy-by-design and abuse-resistance points at the next sync.

### 14:09 — Dispatcher accounts
- Ming: dispatchers should have accounts for security.
- Decision: company account with individual staff logins (roles: admin / dispatcher / view-only; two-step sign-in; overrides logged per person; access removed when staff leave). Drivers still join by company-issued code; public app stays account-free.
- Principle for the pitch: accounts where responsibility and sensitive data are; none where they only add friction.

### 14:10–14:20 — Tools, not priority
- Ming: if accounts get routing priority, everyone will want it, everyone is prioritised, and we are back to square one.
- Principle adopted: accounts/payment buy tools, never road priority; neutral order for public trips (no self-declared urgency); neutral coordinator across fleets; shared detours.
- Added `--priority-scan`. Findings (approximate map, term days): neutral first-come-first-served order loses nothing vs deadline-first; everyone claiming urgency costs only 0.4–0.6 pts at 800 vehicles (typical app is −3.0) — no return to square one; false urgency claims make the cheaters worse off (−1.0 pts on 800-vehicle closure days).
- Public settings wireframe: added "every trip counts the same — no paid priority".

### 14:57 — Advisor, not a map app
- Ming: could the algorithm be its own app that links to the maps app? — "like an advisor".
- Decision: plan here, drive there. Our app advises (when to leave, which corridor, chance of being late, customer notices); Google Maps or Waze does turn-by-turn. Handoff via Maps URL with a bypass waypoint, or Google Navigation Connect (experimental, one destination, returns telemetry). Own navigation only later if needed.
- Wireframes: "Start" buttons now open the user's maps app.

### 15:25–15:45 — Kuching schools and sessions
- Ming: list Kuching schools along routes and track their session (morning / afternoon / both); use it in the project.
- Built `data/kuching_schools_sessions.csv` (38 schools from the Wikipedia list of schools in Sarawak, mapped to map areas). No open dataset gives per-school session type, so all are `unknown` → treated as morning; typical session times from Kosmo 2023 (Kedah). Engine now gives each road its own school windows from nearby schools; real-map schools matched by name.
- Findings: two daily problem windows (07:00 drop-off and 13:15 dismissal, both ~88.5% vs 95.4% on time); if half of primary schools run two sessions, extra windows at 12:45 and 18:00. School-safe routing +4.0 pts on term closure days.
- Also sent REPLIT_UPDATE_2.md (decisions since v5).

### Open (added)
- [ ] Verify session type per school (school websites, district education office, or ask parents); fill the CSV.


## 16:30 — Proof-of-concept advisor page (task 17)
- `poc/advisor.html`, published as an artifact ("Kuching Trip Advisor") with a shared `trips` test log (no accounts; tester nickname only).
- JS port of the approximate-map engine: 30 corridors, BPR, penalty-method routes, school windows from `data/kuching_schools_sessions.csv` (counts per area), 400-trip fleet wave at 07:00 assigned congestion-aware, Monte Carlo P(late) (300 runs), leave-time search in 1-minute steps for a chosen confidence (80/90/95%).
- Output: leave-by time, corridor, arrival range (P10–P90), school and busy-road notes, fleet trips sharing the route, Google Maps link with a corridor waypoint, WhatsApp/SMS-style message.
- Practical test tab: save plan (follow advice / usual way), fill in actual leave/arrive, waypoint kept, app used; summary of on-time rate follow vs usual, median time error, % inside range, waypoint kept %.
- Traffic is simulated: tests the process, not accuracy.

## 16:10 — Advisor page v2 (Ming's UI feedback)
- Start can be "My current location": the Maps link leaves out the origin so Google Maps uses the phone's position (documented behaviour); the user picks the nearby area for the advice. The web page itself can't read GPS (artifact pages are refused location); the real app would.
- Drop a start or destination pin on the corridor map; paste coordinates or a full Google Maps link (short share links can't be read). Advice snaps to the nearest area; the Maps link uses the exact point.
- Saved places (Home, Office…) kept on the device only (no account).
- Road reports: one-tap "closed / jam" per corridor, shared through the page's `reports` collection, expire after 2 hours; closures are avoided and jams slow the road straight away.
- Live Waze/Google traffic can't be pulled into this page (no outside network access, no public Waze incident API). Product route: Waze for Cities data feed (free, for government partners such as DBKU/MBKS), paid traffic APIs (Google Routes, TomTom, HERE), official notices; crowdsourced reports meanwhile.

## 16:20 — Traffic from outside Kuching, plain wording, odd detours
- Ming: much traffic comes from Samarahan, Siburan, Moyan, Matang, Samariang, Sejingkat and funnels/merges into Kuching. Added an outside-commuter layer (entry roads from public sources, volumes assumed), tidal in/out flows, Greater Kuching OSM download box. Results in BLUEPRINT §12, `outputs/v7/`.
- Finding: with jams concentrated on the few entry/merge roads, route-spreading helps less on normal days (+0.08 pts vs +0.56 without), still helps on closures (+1.7); leave-time advice matters more.
- Ming's phone test: Maps kept our stop but looped into a side street (stop at an area centre). Added "only reroute when worth it" (≥3 min or ≥5 pts safer), stop only when rerouting, "Open without the extra stop", and an "odd detour" answer in the test log. BLUEPRINT §13.
- Page wording made plain (no "fleet wave", "corridor", "P(late)", "waypoint"). Map has Kuching / Greater Kuching views; outside areas selectable as start/destination.

## 16:45 — Mobile prototype (Expo / React Native, SDK 57)
- `mobile/`: real Android app run through Expo Go (scan QR). Plan (GPS "My location", saved places, areas incl. around Kuching), advice with route map, Google Maps hand-off (stop only when advice differs from Maps' usual road), 5-minute leave reminder (local notification), share-as-message, road reports (2 h, on phone), test trips with one-tap "I'm leaving" / "I've arrived" timing and CSV export, large-text mode. No accounts.
- Checked: Android bundle builds (`expo export`), engine runs in Node (~0.1 s per advice), web copy renders at phone size. Not yet run on a real phone.

## 19:45 — Phone launcher (CustomTkinter)
- Ming hit "Failed to download remote update" (phone couldn't reach the PC over Wi-Fi). Added `mobile/launcher.py` + `OPEN-LAUNCHER.bat`: checks/installs Node.js, packages and the tunnel helper; Same Wi-Fi (pick the PC's address, avoids Expo choosing a virtual adapter) or Tunnel; shows the QR code; one-click switch to tunnel; Windows Firewall rule button. Tested Wi-Fi mode here (QR shown); tunnel mode untested here (tunnel service blocked from this workspace).

## 20:00 — Installable APK setup
- Added `eas.json` (preview = APK, internal distribution), `BUILD-APK.bat` and a launcher button; app version 0.1.0 / versionCode 1; custom icon and splash; `expo-system-ui` for dark mode in the installed app. Checked here: Android project generates (prebuild) and the bundle builds. The cloud build itself needs Ming's free Expo account (Expo's servers are blocked from this workspace).

## 23:50 — Judging rubric alignment
- Rubric: Track 1, five criteria × 20 (problem & value, rigor & robustness, decision support, explainability, live demo & pitch); Phase 1 = 3-min pitch, Phase 2 = 4-min demo.
- App: risk level (Low/Medium/High) and ranked "Why this advice" causes (closure, reported jam, school rush, traffic from outside Kuching, crowding, peak traffic).
- New 6-slide "3-Minute Pitch" deck (timed notes), `PITCH_PACK.md` (rubric map, demo script, Q&A sheet, numbers), `REPLIT_UPDATE_4.md` (real-map runs, calibration chart, noise sweep, pitch-number export, sources to find).

## 11 Oct, 01:30 — Replit dropped; Claude takes over its tasks
- Ming: no more Replit, all Claude from here. Old Replit briefs moved to `archive/`.
- Added `plot_calibration()` → `calibration_<tag>.png` (predicted vs actual chance of being late, typical app vs our advisor), `--noise-scan` (traffic noise 0.10/0.25/0.40, live-data error 0.05/0.10/0.20, one at a time), and `pitch_numbers.py` (prints the PITCH_PACK numbers table from any results CSV; checked: reproduces the v7 table exactly).
- Real-map runs can't happen here (OpenStreetMap blocked): `RUN-REAL-MAP.bat` does them on Ming's PC and zips the results.
- Approximate-map rerun (`outputs/v9/`): same story as v7, numbers within about 1.5 points (closure: typical app 63.8%, advisor 65.4%, school-safe 66.5%; fixed routes 54.0%). Slides keep the v7 numbers until the real-map run replaces both.
- Calibration chart: estimates lean cautious in the middle (says 60% → ~45% late), not overconfident as earlier notes said.
- Noise scan: closure-day gain holds at every noise level (+0.6 to +1.9 pts); warning precision depends on the live traffic reading (85% good / 71% default / 50% poor).
