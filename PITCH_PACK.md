# Pitch pack — Dormathon 2026, Track 1 (Predictive Model)

Guiding question: **"Does your model help someone make a better decision, and can you prove it?"**
Phase 1: 3-min pitch + 2-min Q&A. Phase 2: 4-min demo + 3-min Q&A. Five criteria × 20 points.

Decks:
- **3-minute pitch** (6 slides, timed speaker notes): "Kuching Trip Advisor 3-Minute Pitch" artifact.
- Backup for Q&A: the 10-slide "Kuching Trip Advisor Pitch" (Expo) or "(Flutter)" copy.

Before presenting, fill in: price placeholder on the proof slide (or delete it), team/contact on the last slide, and turn on GitHub Pages so the last slide's QR (harrison-fx.github.io/navi-charter) opens.

## How each criterion is covered

| Criterion | Where | What to say |
|---|---|---|
| 1 Problem & value | Slides 1, 2, 5 | Two personas: delivery fleets (they pay: fuel, driver time, late-drop compensation) and office commuters (reach). Money case: RM 2,043 saved on a closure morning vs fixed routes for a 400-van fleet (simulated). |
| 2 Rigor & robustness | Slide 4 | BPR volume-delay + Monte Carlo + congestion-aware assignment; tested against noise, sensor error, closures, unconfirmed school hours, fake trips, false urgency; warnings 80% recall / 72% precision (normal), 94% / 91% (closures), Brier 0.03. Paired comparisons with 95% CIs. |
| 3 Decision support | Slide 3 + demo | Predict → explain → act. Risk level (Low/Medium/High), ranked main cause, then actions: open Maps, reminder, message. Fleets: early customer notice. |
| 4 Explainability | Slide 3 + demo | "Why this advice" box: plain-language main risk (school rush, traffic from outside Kuching, closure, crowding, peak traffic). |
| 5 Live demo & pitch | Slide 6 + demo | Web prototype in any browser (judges scan the QR on slide 6); laptop runs it from the folder if Wi-Fi fails. 3:00 timing in the notes. |

## Phase 2: 4-minute demo script (web prototype on the laptop, projected; `START-WEB-DEMO.bat`, press S to hide the cue card)

1. **0:00 Normal morning (45 s).** Type *Pending* → *Batu Lintang* (or tap the map for A and B), tap 07:30, Tomorrow, School day, 90%. Tap *When should I leave?* Read out: leave 07:13, Low risk 8%, the timeline: most likely 07:25, 5 minutes to spare. Point at **Why this advice: school rush** and the school-zone flag on Padungan–Batu Lintang ~07:19.
2. **0:45 School day vs holiday (30 s).** Change the trip to Stutong → Satok (arrive 07:30): school day says leave 07:07 with two school zones; switch to *No school* and it says 07:14, school notes gone. "Seven minutes back, because we know the school timetable."
3. **1:15 Something goes wrong (60 s).** Road reports → Padungan–Pending → *Closed / accident*. Ask again: route switches to Kenyalang → Simpang Tiga, earlier leave time, main risk now "Road closure". Show *Open in Google Maps*: the link carries a stop so Maps follows our road.
4. **2:15 Outside-Kuching commuter (40 s).** From Samarahan → City Centre, arrive 08:00. Why box: traffic from outside Kuching on Stutong → Simpang Tiga. Map switches to Greater Kuching.
5. **2:55 Act (35 s).** *Open in Google Maps*, *Remind me* (on the phone it's a notification), *Send as message* (copies a WhatsApp-ready text). Optional: type "hospital near Petra Jaya" in To to show it reads context, or plan a trip for Today 30–90 min ahead to show "Live traffic checked at …" (needs internet). For testers → log the trip shows how we measure real results.
6. **3:30 Close (30 s).** "Runs in any browser, under a second per answer; scan the QR to try it. Next: real road map, shared reports, one-week pilot."

Finding places (if asked): type a name ("Vivacity", "UNIMAS"), add a road or landmark to narrow it, or drop and drag a pin. Indoors, Settings → Demo makes "My location" pretend to be in Pending, Samarahan, etc.

Backup if Wi-Fi fails: `mobile/START-WEB-DEMO.bat` on the laptop. It is the same app (same screens, same engine) in a phone frame, offline, with this script as a cue card (press **S** to hide it, F11 for full screen). Reminders show a note and "Send as message" copies the text instead. Online copy: the "Trip Advisor Demo" artifact. Rebuild after app changes: `cd mobile && npm run web-demo`.

## Q&A cheat sheet

- **"Is this AI / machine learning?"** It's a probabilistic forecasting model, not ML, on purpose: Kuching has no years of trip data. We use the standard transport-engineering volume-delay function (BPR) and simulate uncertainty explicitly (Monte Carlo). Real counts calibrate it; ML can be added later on collected trips.
- **"Where does your data come from?"** Live speeds from TomTom for trips leaving within about 2 hours (Settings → Traffic → Test live traffic shows it working). OpenStreetMap roads; 38 Kuching schools (Wikipedia list; hours not yet confirmed); entry roads from public sources (Samarahan Expressway, FT 8302, Kuching–Serian). Traffic volumes are assumptions; we say so on the slide. Next: JKR / council counts.
- **"Why not just use Waze or Google Maps?"** They react to traffic that exists and give everyone the same shortcut. We predict the departure decision and plan with other trips in mind. And we hand off to Google Maps for driving, so users keep their app.
- **"What if everyone uses it?"** That's the design point: it counts planned trips and spreads them. Our test of "everyone gets the same advice" (random split / typical app) is in the results. Nobody can pay for priority.
- **"How do you know it works?"** Simulation today (60 days × 3 seeds, paired comparisons with confidence intervals) plus a built-in test log for a one-week field pilot that times every real trip. We report the honest finding: on normal days timing matters most; spreading pays on bad days.
- **"False alarms?"** On normal days 72% of late warnings are right and 80% of late trips are caught; on closure days 91% / 94%. Brier score 0.03. Show `calibration_approx.png`: our estimates lean cautious in the middle (when we say 60%, about 45% are actually late), never the risky way.
- **"What if the data is noisy?"** Noise scan (`outputs/v9/noise_scan_approx.txt`): on closure days the advisor beats the typical app at every noise level tried (+0.6 to +1.9 points). Warning quality depends on the live traffic reading: precision 85% with a good reading, 71% with our default, 50% with a poor one. That's why live data sources are on the roadmap.
- **"Privacy?"** No account; saved places stay on the phone; shared plans will carry a throwaway ID (PDPA-friendly).
- **"Business model?"** Fleets pay for dispatch tools (per van per month); commuters free. Never sell road priority.
- **"Is the traffic real?"** For trips in the next ~2 hours, yes: TomTom's current speeds adjust the model. For tomorrow, it's the model only, because live traffic can't see the future; historical patterns from councils or TomTom are the next step.
- **"Weaknesses?"** Approximate map until the real-map run; assumed volumes; live speeds only for the next couple of hours; mid-range probabilities a bit cautious (over-warn); school hours unverified. Each has a named fix.

## Numbers used (from `outputs/v7/`, approximate map, simulated)

| | Fixed routes | Typical app | Our advisor | Our advisor + school-safe |
|---|---|---|---|---|
| On time, school day normal | 88.1% | 91.1% | 91.2% | 90.6% |
| On time, school day closure | 54.1% | 62.1% | 63.8% | 65.0% |
| Time+fuel RM/day, normal | 2,642 | 2,591 | 2,579 | 2,605 |
| Time+fuel RM/day, closure | 5,123 | 3,136 | 3,080 | 3,268 |
| Warnings precision / recall, normal | | 71% / 80% | 72% / 80% | |
| Warnings precision / recall, closure | | 91% / 94% | 91% / 94% | |
| Brier | | 0.032 | 0.031 | |

Wave timing (typical app, school day, normal): 07:00 91.1% → 07:30 96.0%.

Noise scan (school days, `outputs/v9/noise_scan_approx.csv`, one setting changed at a time):

| Setting | Advisor vs typical app, closure | Warnings precision / recall, normal | Brier, normal |
|---|---|---|---|
| Traffic noise low (0.10) | +0.6 pts | 54% / 69% | 0.018 |
| Default (0.25 / 0.10) | +1.6 pts | 71% / 79% | 0.033 |
| Traffic noise high (0.40) | +1.4 pts | 83% / 86% | 0.042 |
| Live reading good (0.05) | +1.4 pts | 85% / 87% | 0.016 |
| Live reading poor (0.20) | +1.9 pts | 50% / 71% | 0.070 |

(Low traffic noise means few late trips, so the few warnings are harder to get right: precision drops but Brier improves.)

Update these from the real-map run: double-click `RUN-REAL-MAP.bat`; `outputs/real-map/pitch_numbers_osm.md` then has this table filled in.
