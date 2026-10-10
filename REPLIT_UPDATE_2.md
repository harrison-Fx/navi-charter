# Update for Replit #2 — Kuching Dispatch Advisor

**From:** Claude · **Owner:** Ming · **Date:** 10 Oct 2026, ~15:30 Kuching time
**Applies on top of:** `kuching-dispatch-v5.zip` and `REPLIT_BRIEF.md` (the run/check list there still stands). Details: `BLUEPRINT.md` sections 9–10, `JOURNAL.md`.

## Decisions since v5

1. **Product shape: an advisor, not a map app.** "Plan here, drive there." Our app decides *when to leave*, *which corridor* (counting other trips, avoiding school zones) and *chance of being late*; Google Maps or Waze does turn-by-turn. Handoff = a Google Maps link with the destination plus a waypoint on the chosen bypass (Maps URLs: up to 3 waypoints on mobile browsers, 9 otherwise; not honoured by every Maps product). Google Navigation Connect is an option later (one destination, no waypoints, returns telemetry, experimental). Own navigation / Android Auto only if a pilot proves it's needed.
2. **Accounts.** Public: none (settings on the phone, anonymous throwaway trip IDs; identity stays with the user's maps app). Dispatchers: individual staff logins under a company account (roles, two-step sign-in, per-person action log) because they handle customer data. Drivers: company-issued join code.
3. **Tools, not priority.** Payment and accounts buy tools, never road priority; public trips use a neutral order. Tested with `--priority-scan` (in v5): a neutral order loses nothing, false urgency does not pay.
4. **Route changes during a trip.** We can't push updates into a running Google Maps trip, so:
   - plan well before departure (lowest-risk route + timing) so mid-trip changes are rare;
   - refresh the route at natural stops (between deliveries), never while driving;
   - splitting a trip into legs is an internal decision, not something users see;
   - sudden jams: let the maps app reroute; we update the ETA and customer notice;
   - use trip data from vehicles already out to adjust the *next* departures;
   - one-tap/voice "new route" prompts and own navigation: later.
5. **Closures and accidents.** Incident input planned from: (a) one-tap reports from our drivers/dispatchers (Waze-style crowdsourcing, small scale), (b) official notices and local news, (c) paid incident feeds later. Hackathon: dispatcher marks a closure on the map.
6. **Older / non-map users.** Not scoped out. Timing advice needs no map ("Leave by 6:55; Jalan X slow until 7:30") — deliverable by WhatsApp/SMS or set up by a family member; simple large-text mode. Non-users still benefit indirectly from freer roads.
7. **Validation: mockup + one practical test.** Claude is building a proof-of-concept web page that is both the demo and the test tool: pick a Kuching trip and arrive-by time → leave time, corridor, chance of being late → real "Open in Google Maps" button with the bypass waypoint → log actual departure/arrival. Planned test: about a week of real trips, alternating "follow advice" and "usual way" days. It checks the *process* (does Maps honour the waypoint? do people follow the timing? how far off are ETAs?) — predictions are still based on simulated traffic.

## In progress (Claude)

- **Kuching school list with session types** (morning only / afternoon only / both) to replace the single assumed school window. Finding so far: public government datasets found give school **counts by district**, not individual schools with sessions ([DOSM schools_district](https://open.dosm.gov.my/data-catalogue/schools_district)); the session per school is not in any open dataset found yet. Plan: school locations from OpenStreetMap + session type from school/education-office sources where findable, otherwise marked "assumed".
- Proof-of-concept page (item 7).

## Requests to Replit (in addition to `REPLIT_BRIEF.md`)

1. When you run `--osm`, please also send back `data/kuching_schools.csv` (OSM schools) — we will attach session types to it.
2. If you can find an official list of Kuching schools with **session type** (e.g. from the Ministry of Education, the Sarawak Education Department or district education offices), please send the source link.
3. If you can test on a phone: does a Google Maps directions link with one waypoint open in the **Google Maps app** with the waypoint kept (Android)? Example format:
   `https://www.google.com/maps/dir/?api=1&origin=1.5550,110.3850&destination=1.5400,110.3450&waypoints=1.5450,110.3620&travelmode=driving`
   (Pending → Batu Lintang via Kenyalang; coordinates are approximate area centres.)

## Addendum (15:45)

- School list added: `data/kuching_schools_sessions.csv` (38 schools, sessions unverified → morning by default). The engine now builds per-road school windows from it; real-map schools are matched by name. New option `--double-session X`. Details and results: `BLUEPRINT.md` section 11. Please use the updated `kuching_advisor.py` and include the `data/` folder.

