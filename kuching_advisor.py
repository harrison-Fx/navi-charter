"""
Kuching Dispatch Advisor — v2 prototype (Gate 1: route choice + fair comparison)
================================================================================
Question this script tests:
    Does accounting for a fleet's OWN planned road usage improve delivery
    outcomes, compared with routing each vehicle independently using the
    SAME live traffic information? And separately: how useful are early
    lateness warnings?

What is real and what is simulated
    - Road network: approximate Kuching corridor model (default) or real
      OpenStreetMap roads (--osm; cached to data/kuching_drive.graphml).
    - Traffic, demand, closures, costs: SIMULATED. Results are a probabilistic
      simulation prototype (BPR congestion + Monte Carlo), not a trained
      machine-learning model and not a field trial.

Strategies (all except the static plan see the same simulated live view)
    static        : each vehicle's fastest route under AVERAGE conditions (no live info)
    independent   : each vehicle's fastest route under today's live view,
                    ignoring the other vehicles in the wave (typical navigation app)
    random_split  : vehicles split at random across the same acceptable routes
                    (tests whether simple spreading explains any gain)
    coordinated   : congestion-aware greedy assignment: each vehicle, tightest
                    deadline first, takes the cheapest route given the load the
                    fleet has already placed on each road in each 5-minute bin

Two ledgers, never mixed
    Ledger 1 (physical): on-time %, vehicle-hours, P90 trip time, fuel and driver
                         cost, route changes and detours vs the independent plan
    Ledger 2 (notices):  warnings, precision/recall, ETA coverage, calibration,
                         modelled compensation with sensitivity to RM20/RM5

Usage
    python kuching_advisor.py                    # approximate map, default experiment
    python kuching_advisor.py --osm              # real Kuching roads (download once)
    python kuching_advisor.py --days 60 --seeds 3 --vehicles 400
    python kuching_advisor.py --sweep            # fleet size x incident location x seeds
    python kuching_advisor.py --routes=yen       # old route search, to reproduce the
                                                 # single-route finding
"""
import os, sys, math, itertools, csv, argparse
from collections import Counter
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------- assumptions
A = dict(
    n_vehicles=400,          # vehicles dispatched in one 15-minute peak wave
    wave_min=15,             # departures spread uniformly over this window
    bin_min=5,               # time-expanded loading: vehicles counted per 5-min entry bin
    fuel_l_per_km=0.12,
    idle_l_per_min=0.02,     # extra fuel per minute of congestion delay
    fuel_rm_per_l=2.15,      # diesel price assumption (Sarawak)
    driver_rm_per_min=0.25,  # ~RM15/hour
    late_penalty_rm=20.0,    # ASSUMPTION: compensation per late drop with no warning
    notified_late_rm=5.0,    # ASSUMPTION: compensation per late drop warned early
    detour_cap=1.25,         # never offer a route >25% longer than the shortest
    min_distinct_km=0.3,     # a route counts as a real alternative if it uses at least
    min_distinct_share=0.10, #   max(0.3 km, 10% of its length) of roads the others don't
    noise_sigma=0.25,        # day-to-day variation in background traffic
    sensor_sigma=0.10,       # error in the simulated live observation
    warn_threshold=0.5,      # warn when P(late) >= this
    mc_samples=30,           # Monte Carlo samples per lateness estimate
    # --- school traffic (ASSUMPTIONS: verify against the Ministry of Education calendar) ---
    wave_start="07:00",      # clock time the dispatch wave starts
    school_boost=0.35,       # extra traffic on school-zone roads in a window, as a share of capacity
                             # (full boost with 2+ schools on the road's areas; half with one)
    unknown_session_as="morning",  # session assumed for schools whose session is not verified
    double_session_share=0.0,      # sensitivity: share of unverified PRIMARY schools treated as two-session
    school_radius_km=0.3,    # (real map) roads with a midpoint within this distance of a school
    school_safe_rm=3.0,      # school-safe variant: planning penalty per school-zone road in a window
    # --- commuters from outside Kuching (ASSUMPTIONS: replace with JKR / council traffic counts) ---
    commuters=1.0,           # scale on the inbound/outbound commuter layer (0 = off)
    local_share=0.8,         # with commuters on, the old background level is treated as 80% local traffic
    am_peak="07:20", am_sd=45,   # inbound (towards town) peak and spread, minutes
    pm_peak="17:45", pm_sd=50,   # outbound peak
    tidal_floor=0.15,        # off-peak commuter trickle as a share of the peak
)

def hm(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)

# School traffic windows by session type. Session times: morning 07:30-13:30, afternoon
# 13:30-18:30 (typical times reported in Kosmo, 5 Feb 2023 — not Kuching-specific; verify).
# Windows = traffic around arrival and dismissal.
SESSION_WINDOWS = {
    "morning":   (("06:45", "07:30"), ("13:15", "14:00")),
    "afternoon": (("12:45", "13:30"), ("18:15", "19:00")),
    "both":      (("06:45", "07:30"), ("12:45", "14:00"), ("18:15", "19:00")),
}
SCHOOL_FILE = os.path.join("data", "kuching_schools_sessions.csv")

def load_school_sessions(path=SCHOOL_FILE):
    """Kuching schools with level, approximate area and session type. Unverified
    sessions ('unknown') use A['unknown_session_as']; a share of unverified primary
    schools can be switched to two-session as a sensitivity test."""
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    r = np.random.default_rng(99)
    for row in rows:
        sess = row.get("session", "unknown").strip().lower()
        if sess not in SESSION_WINDOWS:
            sess = A["unknown_session_as"]
            if row.get("level") == "primary" and r.random() < A["double_session_share"]:
                sess = "both"
        row["session_used"] = sess
    return rows

def windows_for(sessions):
    """Union of traffic windows (minutes) for a set of session types."""
    out = set()
    for sname in sessions:
        for a, b in SESSION_WINDOWS[sname]:
            out.add((hm(a), hm(b)))
    return sorted(out)

# Approximate map only: areas ASSUMED to contain schools (residential areas). On the real map,
# school zones come from OpenStreetMap amenity=school locations instead.
SCHOOL_AREAS = {"Batu Lintang", "Kenyalang", "Hui Sing", "Stutong", "Tabuan Jaya", "Petra Jaya",
                "Batu Kawa", "Matang", "Simpang Tiga"}
ROUTE_METHOD = "penalty"

ROAD = {   # free-flow km/h, capacity veh per 15 min one direction, peak background v/c range
    "trunk":     (70, 900, (0.85, 1.00)),
    "primary":   (50, 700, (0.85, 1.00)),
    "secondary": (40, 450, (0.70, 0.90)),
    "tertiary":  (30, 250, (0.40, 0.60)),
}

# ---------------------------------------------------------------- places (approximate)
AREAS = {
    "City Centre": (1.5580, 110.3450), "Padungan": (1.5565, 110.3570), "Pending": (1.5550, 110.3850),
    "Bintawa": (1.5680, 110.3720), "Kenyalang": (1.5450, 110.3620), "Simpang Tiga": (1.5350, 110.3550),
    "Stutong": (1.5200, 110.3750), "Tabuan Jaya": (1.5300, 110.3900), "Hui Sing": (1.5230, 110.3600),
    "Batu Lintang": (1.5400, 110.3450), "Satok": (1.5520, 110.3350), "Petra Jaya": (1.5750, 110.3300),
    "Batu Kawa": (1.5150, 110.3000), "Matang": (1.5500, 110.2850), "Airport": (1.4870, 110.3450),
    "Kota Sentosa": (1.4700, 110.3300),
}
HUBS = {"Pending": 0.65, "Kota Sentosa": 0.35}
DESTS = {"City Centre": 2, "Padungan": 2, "Kenyalang": 2, "Simpang Tiga": 2, "Stutong": 3,
         "Tabuan Jaya": 3, "Hui Sing": 3, "Batu Lintang": 2, "Satok": 2, "Petra Jaya": 3,
         "Batu Kawa": 4, "Matang": 2}
CORRIDORS = [
    ("City Centre", "Padungan", "primary"), ("Padungan", "Pending", "primary"),
    ("Padungan", "Kenyalang", "secondary"), ("Pending", "Bintawa", "secondary"),
    ("Pending", "Tabuan Jaya", "secondary"), ("Kenyalang", "Simpang Tiga", "primary"),
    ("City Centre", "Batu Lintang", "secondary"), ("City Centre", "Satok", "primary"),
    ("Satok", "Petra Jaya", "primary"), ("Satok", "Batu Kawa", "primary"),
    ("Satok", "Batu Lintang", "secondary"), ("Batu Lintang", "Simpang Tiga", "secondary"),
    ("Batu Lintang", "Airport", "primary"), ("Simpang Tiga", "Hui Sing", "secondary"),
    ("Simpang Tiga", "Stutong", "primary"), ("Stutong", "Tabuan Jaya", "primary"),
    ("Stutong", "Hui Sing", "tertiary"), ("Hui Sing", "Airport", "secondary"),
    ("Airport", "Kota Sentosa", "trunk"), ("Batu Kawa", "Kota Sentosa", "secondary"),
    ("Batu Kawa", "Matang", "secondary"), ("Matang", "Petra Jaya", "secondary"),
    ("Kota Sentosa", "Stutong", "trunk"), ("Bintawa", "Petra Jaya", "tertiary"),
    ("Pending", "Kenyalang", "tertiary"), ("Kenyalang", "Batu Lintang", "tertiary"),
    ("Padungan", "Batu Lintang", "tertiary"), ("Tabuan Jaya", "Kenyalang", "tertiary"),
    ("Hui Sing", "Batu Lintang", "tertiary"), ("Airport", "Batu Kawa", "tertiary"),
]

# Traffic that starts outside Kuching and funnels in through a few entry roads.
# name: (lat, lon, AM-peak inbound vehicles per 15 min, [(Kuching area it enters at, road class, capacity per 15 min)])
# Entry roads from public sources: Kuching–Samarahan Expressway and FT 8302 Jalan Mambong–Sejingkat
# (Pending – Muara Tabuan – Stutong – Samarahan), Jalan Kuching–Serian (Pan Borneo) via Penrissen,
# the Kuching Barrage / Pending causeway towards Sejingkat. Volumes and capacities are ASSUMED.
EXTERNAL = {
    "Samarahan":    (1.4600, 110.4930, 600, [("Stutong", "trunk", 900), ("Tabuan Jaya", "primary", 500)]),  # incl. Asajaya, Moyan
    "Siburan":      (1.4050, 110.3600, 450, [("Kota Sentosa", "trunk", 900)]),                            # Kuching–Serian road
    "Matang outer": (1.5550, 110.2450, 250, [("Matang", "secondary", 450)]),
    "Samariang":    (1.5950, 110.3050, 200, [("Petra Jaya", "secondary", 450)]),
    "Sejingkat":    (1.5950, 110.4100, 120, [("Bintawa", "secondary", 450)]),
}
# where inbound commuters work (ASSUMED weights)
JOBS = {"City Centre": 3, "Padungan": 2, "Satok": 2, "Petra Jaya": 3, "Pending": 2, "Batu Lintang": 1,
        "Simpang Tiga": 1, "Kenyalang": 1, "Stutong": 1, "Tabuan Jaya": 1, "Hui Sing": 1, "Airport": 1, "Bintawa": 1}

def tidal(minute, which):
    pk, sd = (hm(A["am_peak"]), A["am_sd"]) if which == "in" else (hm(A["pm_peak"]), A["pm_sd"])
    f = A["tidal_floor"]
    return f + (1 - f) * math.exp(-0.5 * ((minute - pk) / sd) ** 2)

def add_commuters(G, zone_nodes, place, steps=4):
    """Load inbound (AM) and outbound (PM) commuter flows onto directed edges as
    edge attributes c_in / c_out (vehicles per 15 min at the peak). Incremental
    assignment: 4 slices, each on the then-fastest path, so flows spread over
    entry roads as they fill up (funnelling emerges where they merge)."""
    for _, _, d in G.edges(data=True):
        d["c_in"] = 0.0; d["c_out"] = 0.0
    if A["commuters"] <= 0:
        return G
    jw = sum(JOBS.values())
    for key, attr in (("in", "c_in"), ("out", "c_out")):
        def w(u, v, d):
            vol = d["bg"] * A["local_share"] + d[attr]
            return d["t0"] * (1 + 0.15 * (vol / d["cap"]) ** 4)
        for _ in range(steps):
            for z, zn in zone_nodes.items():
                q = EXTERNAL[z][2] * A["commuters"] / steps
                for job, wt in JOBS.items():
                    o, t = (zn, place[job]) if key == "in" else (place[job], zn)
                    try:
                        path = nx.shortest_path(G, o, t, weight=w)
                    except nx.NetworkXNoPath:
                        continue
                    for e in zip(path, path[1:]):
                        G.edges[e][attr] += q * wt / jw
    return G

def funnel_report(G, n=6):
    rows = []
    for u, v, d in G.edges(data=True):
        am = (d["bg"] * A["local_share"] + d["c_in"]) / d["cap"]
        rows.append((am, d["c_in"], d.get("name", f"{u}-{v}"), u, v))
    rows.sort(reverse=True)
    print("Busiest roads in the morning commuter peak (v/c incl. inflow from outside Kuching):")
    for am, c, nm, u, v in rows[:n]:
        print(f"  {str(nm)[:40]:40s} {str(u)[:14]:>14s} -> {str(v)[:14]:14s} v/c {am:.2f}  commuters {c:.0f}/15min")

def haversine_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = (math.sin((la2 - la1) * p / 2) ** 2 +
         math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))

# ---------------------------------------------------------------- maps
def add_traffic_attrs(G, rng):
    for u, v, d in G.edges(data=True):
        cls = d.get("highway", "tertiary")
        if isinstance(cls, list):
            cls = cls[0]
        cls = cls.replace("_link", "")
        cls = "trunk" if cls == "motorway" else cls
        speed, cap, (lo, hi) = ROAD.get(cls, ROAD["tertiary"])
        d.update(cls=cls, t0=d["length_km"] / speed * 60, cap=cap,
                 bg=cap * rng.uniform(lo, hi), major=cls in ("trunk", "primary"))
    return G

def schematic_kuching(rng):
    G = nx.DiGraph()
    for name, (lat, lon) in AREAS.items():
        G.add_node(name, y=lat, x=lon, label=name)
    schools = load_school_sessions()
    by_area = {}
    for row in schools:
        by_area.setdefault(row["area"], []).append(row["session_used"])
    for a, b, cls in CORRIDORS:
        L = haversine_km(AREAS[a], AREAS[b]) * 1.3
        if schools:
            sess = by_area.get(a, []) + by_area.get(b, [])
        else:   # no school file: fall back to the earlier assumed school areas, morning session
            sess = ["morning"] * (2 * ((a in SCHOOL_AREAS) + (b in SCHOOL_AREAS)))
        local = cls in ("secondary", "tertiary") and len(sess) > 0
        for u, v in [(a, b), (b, a)]:
            G.add_edge(u, v, length_km=L, highway=cls, name=f"{a}–{b}", school=local,
                       school_windows=windows_for(set(sess)) if local else [],
                       school_boost=A["school_boost"] * min(1.0, len(sess) / 2) if local else 0.0)
    for z, (lat, lon, _, gates) in EXTERNAL.items():
        G.add_node(z, y=lat, x=lon, label=z, external=True)
        for area, cls, cap in gates:
            L = haversine_km((lat, lon), AREAS[area]) * 1.3
            for u, v in [(z, area), (area, z)]:
                G.add_edge(u, v, length_km=L, highway=cls, name=f"{z}–{area}", school=False,
                           school_windows=[], school_boost=0.0, gate_cap=cap)
    G = add_traffic_attrs(G, rng)
    for _, _, d in G.edges(data=True):
        if "gate_cap" in d:
            d["cap"] = d["gate_cap"]; d["bg"] = d["cap"] * 0.3   # little local traffic on entry roads
    place = {n: n for n in AREAS}
    return add_commuters(G, {z: z for z in EXTERNAL}, place), place

GRAPH_FILE = os.path.join("data", "greater_kuching_drive.graphml")
GREATER_BBOX = (110.22, 1.38, 110.52, 1.62)   # west, south, east, north (approximate)

def osm_kuching(rng, path=None):
    """Real Greater Kuching roads (trunk to tertiary). Loads the cached GraphML file if
    present; otherwise downloads from OpenStreetMap once and saves it."""
    import osmnx as ox
    path = path or GRAPH_FILE
    if os.path.exists(path):
        print(f"Loading Kuching road network from {path}")
        M = ox.load_graphml(path)
    else:
        print("Downloading Greater Kuching road network from OpenStreetMap ...")
        # Greater Kuching box: Kuching plus Samarahan, Siburan, Matang, Samariang and Sejingkat,
        # so traffic from those areas is routed on real roads up to where it merges.
        flt = '["highway"~"motorway|trunk|primary|secondary|tertiary"]'
        west, south, east, north = GREATER_BBOX
        try:   # osmnx 2.x
            M = ox.graph_from_bbox((west, south, east, north), network_type="drive", custom_filter=flt)
        except TypeError:   # osmnx 1.x
            M = ox.graph_from_bbox(north, south, east, west, network_type="drive", custom_filter=flt)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        ox.save_graphml(M, path)
        print(f"  saved to {path} (later runs work offline)")
    D = ox.convert.to_digraph(M, weight="length")
    D = D.subgraph(max(nx.strongly_connected_components(D), key=len)).copy()
    G = nx.DiGraph()
    for n, d in D.nodes(data=True):
        G.add_node(n, y=float(d["y"]), x=float(d["x"]))
    for u, v, d in D.edges(data=True):
        name = d.get("name", d.get("highway", "road"))
        name = name[0] if isinstance(name, list) else name
        G.add_edge(u, v, length_km=float(d["length"]) / 1000, highway=d.get("highway", "tertiary"),
                   name=str(name))
    nodes = list(G.nodes)
    ys = np.array([G.nodes[n]["y"] for n in nodes]); xs = np.array([G.nodes[n]["x"] for n in nodes])
    place = {}
    for a, (lat, lon) in AREAS.items():
        n = nodes[int(np.argmin((ys - lat) ** 2 + ((xs - lon) * math.cos(lat * math.pi / 180)) ** 2))]
        place[a] = n
        G.nodes[n]["label"] = a
    print(f"  {G.number_of_nodes()} junctions, {G.number_of_edges()} directed road segments")
    mark_osm_schools(G, os.path.join(os.path.dirname(path) or ".", "kuching_schools.csv"))
    G = add_traffic_attrs(G, rng)
    # each outside area starts at the road junction nearest its centre (inside the Greater Kuching box)
    zone_nodes = {}
    for z, (lat, lon, _, _) in EXTERNAL.items():
        zone_nodes[z] = nodes[int(np.argmin((ys - lat) ** 2 + ((xs - lon) * math.cos(lat * math.pi / 180)) ** 2))]
    return add_commuters(G, zone_nodes, place), place

def mark_osm_schools(G, cache):
    """Flag roads whose midpoint lies within school_radius_km of an OpenStreetMap
    school (amenity=school). Cached to CSV after the first download."""
    pts = []
    if os.path.exists(cache):
        with open(cache) as fh:
            pts = [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(fh)]
    else:
        try:
            import osmnx as ox
            F = ox.features_from_place("Kuching, Sarawak, Malaysia", tags={"amenity": "school"})
            cen = F.geometry.representative_point()
            rows = [dict(name=str(n), lat=p.y, lon=p.x) for n, p in zip(F.get("name", [""] * len(F)), cen)]
            with open(cache, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["name", "lat", "lon"]); w.writeheader(); w.writerows(rows)
            pts = [(r["lat"], r["lon"]) for r in rows]
            print(f"  downloaded {len(pts)} schools -> {cache}")
        except Exception as ex:
            print(f"  WARNING: could not load schools ({ex}); no school zones on this map")
    for u, v, d in G.edges(data=True):
        d.update(school=False, school_windows=[], school_boost=0.0)
    if not pts:
        return
    names = []
    if os.path.exists(cache):
        with open(cache) as fh:
            names = [r.get("name", "") for r in csv.DictReader(fh)]
    known = {r["name"].lower(): r["session_used"] for r in load_school_sessions()}
    def session_of(nm):
        nm = (nm or "").lower()
        for k_, sv in known.items():
            core = k_.replace("smk ", "").replace("sk ", "").replace("sjk(c) ", "")
            if core and core in nm:
                return sv
        return A["unknown_session_as"]
    sess = [session_of(names[i] if i < len(names) else "") for i in range(len(pts))]
    P = np.array(pts)
    k = math.cos(1.53 * math.pi / 180)
    for u, v, d in G.edges(data=True):
        my = (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2; mx = (G.nodes[u]["x"] + G.nodes[v]["x"]) / 2
        dist = 111.2 * np.sqrt((P[:, 0] - my) ** 2 + ((P[:, 1] - mx) * k) ** 2)
        near = np.where(dist <= A["school_radius_km"])[0]
        if len(near):
            d.update(school=True, school_windows=windows_for({sess[i] for i in near}),
                     school_boost=A["school_boost"] * min(1.0, len(near) / 2))
    print(f"  {len(pts)} schools; {sum(d['school'] for *_, d in G.edges(data=True))} road segments in school zones")

# ---------------------------------------------------------------- route search
def edges(p):
    return list(zip(p, p[1:]))

def route_len(G, p):
    return sum(G.edges[e]["length_km"] for e in edges(p))

def is_real_alternative(G, p, kept):
    """Bottleneck-aware diversity: keep a route if, against EVERY kept route, it
    uses at least max(min_distinct_km, min_distinct_share x its length) of road
    the other route does not. A short bypass around one jammed stretch counts,
    even if the rest of the journey is shared."""
    L = route_len(G, p)
    need = max(A["min_distinct_km"], A["min_distinct_share"] * L)
    pe = set(edges(p))
    for q in kept:
        own = sum(G.edges[e]["length_km"] for e in pe - set(edges(q)))
        if own < need:
            return False
    return True

def candidate_routes(G, o, d, k=4):
    return routes_penalty(G, o, d, k) if ROUTE_METHOD == "penalty" else routes_yen(G, o, d, k)

def routes_penalty(G, o, d, k=4, factor=1.5, max_iter=25):
    """Penalty method: find the fastest route, make its roads `factor` times more
    expensive in the SEARCH only, search again. Real travel times are untouched.
    Routes beyond the detour cap or not a real alternative are discarded."""
    pen, kept, best_len = {}, [], None
    w = lambda u, v, dd: dd["t0"] * pen.get((u, v), 1.0)
    for _ in range(max_iter):
        p = nx.shortest_path(G, o, d, weight=w)
        L = route_len(G, p)
        best_len = best_len or L
        if L <= best_len * A["detour_cap"] and p not in kept and (not kept or is_real_alternative(G, p, kept)):
            kept.append(p)
            if len(kept) == k:
                break
        for e in edges(p):
            pen[e] = pen.get(e, 1.0) * factor
    return kept

def routes_yen(G, o, d, k=4, scan=40):
    """v1 method (Yen's k-shortest paths + 70% overlap filter), kept for comparison."""
    kept, best_len = [], None
    for p in itertools.islice(nx.shortest_simple_paths(G, o, d, weight="t0"), scan):
        L = route_len(G, p)
        best_len = best_len or L
        if L > best_len * A["detour_cap"]:
            continue
        pe = set(edges(p))
        if any(sum(G.edges[e]["length_km"] for e in pe & set(edges(q))) > 0.7 * L for q in kept):
            continue
        kept.append(p)
        if len(kept) == k:
            break
    return kept

# ---------------------------------------------------------------- vehicles
def make_vehicles(G, place, n, rng):
    hubs, hw = list(HUBS), np.array(list(HUBS.values()))
    dests, dw = list(DESTS), np.array(list(DESTS.values()), float)
    vs = []
    for i in range(n):
        h = hubs[rng.choice(len(hubs), p=hw / hw.sum())]
        dd = dests[rng.choice(len(dests), p=dw / dw.sum())]
        o, t = place[h], place[dd]
        ff = nx.shortest_path_length(G, o, t, weight="t0")
        vs.append(dict(id=i, hub=h, dest=dd, o=o, d=t, key=(o, t),
                       dep=float(rng.uniform(0, A["wave_min"])),       # departure minute in the wave
                       deadline=ff * float(rng.uniform(1.3, 1.8))))   # minutes after departure
    return vs

# ---------------------------------------------------------------- time-expanded congestion model
class Model:
    """Edge travel time = BPR with background + fleet vehicles entering that edge
    in the same 5-minute bin (converted to a 15-minute rate). Entry times use
    free-flow travel times along the route (a static approximation: no queues)."""
    def __init__(self, G):
        self.G = G
        self.scale = A["wave_min"] / A["bin_min"]
        self._offs = {}
        self.t0 = hm(A["wave_start"])

    def in_window(self, e, b):
        mid = (b + 0.5) * A["bin_min"]
        return any(a <= mid < z for a, z in self.G.edges[e].get("school_windows", []))

    def school_passes(self, path, dep, school_on):
        if not school_on:
            return 0
        return sum(1 for e, b in self.bins(path, dep) if self.G.edges[e].get("school") and self.in_window(e, b))

    def offsets(self, path):
        key = tuple(path)
        if key not in self._offs:
            cum, out = 0.0, []
            for e in edges(path):
                out.append((e, cum))
                cum += self.G.edges[e]["t0"]
            self._offs[key] = out
        return self._offs[key]

    def bins(self, path, dep):
        b = A["bin_min"]
        return [(e, int((self.t0 + dep + c) // b)) for e, c in self.offsets(path)]

    def add(self, flows, path, dep, sign=1):
        for eb in self.bins(path, dep):
            flows[eb] = flows.get(eb, 0) + sign

    def flows_of(self, plan, vs):
        f = {}
        for v in vs:
            self.add(f, plan[v["id"]], v["dep"])
        return f

    def trip(self, path, dep, flows, view):
        """view = (bg_mult dict or None, cap_mult dict or None, school day?). Returns (min, km, delay)."""
        bgm, capm, school_on = view
        t = dist = delay = 0.0
        for e, b in self.bins(path, dep):
            d = self.G.edges[e]
            mid = (b + 0.5) * A["bin_min"]
            m = bgm[e] if bgm else 1.0
            local = A["local_share"] if A["commuters"] > 0 else 1.0
            vol = (d["bg"] * local + d.get("c_in", 0) * tidal(mid, "in") + d.get("c_out", 0) * tidal(mid, "out")) * m \
                  + self.scale * flows.get((e, b), 0)
            if school_on and d.get("school") and self.in_window(e, b):
                vol += d.get("school_boost", A["school_boost"]) * d["cap"]
            cap = d["cap"] * (capm.get(e, 1.0) if capm else 1.0)
            te = d["t0"] * (1 + 0.15 * (vol / cap) ** 4)
            t += te; dist += d["length_km"]; delay += te - d["t0"]
        return t, dist, delay

def physical_cost(t, dist, delay):
    fuel = (dist * A["fuel_l_per_km"] + delay * A["idle_l_per_min"]) * A["fuel_rm_per_l"]
    return fuel + t * A["driver_rm_per_min"], fuel

# ---------------------------------------------------------------- strategies
def plan_independent(M, vs, routes, view):
    """Each vehicle's fastest route under `view`, ignoring the wave's other vehicles."""
    best, plan = {}, {}
    for v in vs:
        if v["key"] not in best:
            best[v["key"]] = min(routes[v["key"]], key=lambda p: M.trip(p, 0.0, {}, view)[0])
        plan[v["id"]] = best[v["key"]]
    return plan

def plan_random(M, vs, routes, view, rng):
    return {v["id"]: routes[v["key"]][int(rng.integers(len(routes[v["key"]])))] for v in vs}

def plan_coordinated(M, vs, routes, view, school_pen=0.0, order="slack", rng=None):
    """Congestion-aware greedy assignment (not a global system optimum): tightest
    slack first; each vehicle takes the route with the lowest own cost (time,
    fuel, expected late penalty) given load already assigned in each time bin."""
    plan, f = {}, {}
    slack = {v["id"]: v["deadline"] - min(M.trip(p, v["dep"], {}, view)[0] for p in routes[v["key"]])
             for v in vs}
    if order == "slack":            # tightest deadline first (deadlines from real orders)
        seq = sorted(vs, key=lambda v: slack[v["id"]])
    elif order == "departure":      # neutral: first come, first served by departure time
        seq = sorted(vs, key=lambda v: v["dep"])
    else:                           # neutral: random order
        seq = [vs[i] for i in rng.permutation(len(vs))]
    for v in seq:
        best, best_c = None, float("inf")
        for p in routes[v["key"]]:
            M.add(f, p, v["dep"])
            t, dist, delay = M.trip(p, v["dep"], f, view)
            M.add(f, p, v["dep"], -1)
            c = physical_cost(t, dist, delay)[0] + (A["late_penalty_rm"] if t > v["deadline"] else 0)
            if school_pen:
                c += school_pen * M.school_passes(p, v["dep"], view[2])
            if c < best_c:
                best, best_c = p, c
        plan[v["id"]] = best
        M.add(f, best, v["dep"])
    return plan

# ---------------------------------------------------------------- live view + warnings
def live_view(G, true_bgm, capm, rng):
    E = list(G.edges)
    obs = np.array([true_bgm[e] for e in E]) * rng.lognormal(0, A["sensor_sigma"], len(E))
    return dict(zip(E, obs)), capm, E, obs

def warnings_for(M, vs, plan, live, rng, school_on):
    """Same policy for every plan: Monte Carlo P(late) around the live view; warn
    if P >= threshold; the ETA given is the 80th-percentile simulated arrival."""
    bgm_obs, capm, E, obs = live
    samples = [dict(zip(E, obs * rng.lognormal(0, A["sensor_sigma"], len(E)))) for _ in range(A["mc_samples"])]
    f = M.flows_of(plan, vs)
    out = {}
    for v in vs:
        ts = np.array([M.trip(plan[v["id"]], v["dep"], f, (s, capm, school_on))[0] for s in samples])
        out[v["id"]] = (float(np.mean(ts > v["deadline"])), float(np.percentile(ts, 80)))
    return out

# ---------------------------------------------------------------- evaluation of one day
def evaluate_day(M, vs, plan, truth, ref_plan=None, warn=None, min_passes=None):
    f = M.flows_of(plan, vs)
    times, late, km, fuel_rm, phys_rm = [], [], [], 0.0, 0.0
    for v in vs:
        t, dist, delay = M.trip(plan[v["id"]], v["dep"], f, truth)
        c, fu = physical_cost(t, dist, delay)
        times.append(t); late.append(t > v["deadline"]); km.append(dist)
        fuel_rm += fu; phys_rm += c
    times, late, km = np.array(times), np.array(late), np.array(km)
    r = dict(on_time=100 * (1 - late.mean()), veh_hours=times.sum() / 60, p90_min=float(np.percentile(times, 90)),
             fuel_rm=fuel_rm, phys_rm=phys_rm, late=int(late.sum()),
             school_passes=sum(M.school_passes(plan[v["id"]], v["dep"], truth[2]) for v in vs),
             school_unavoidable=sum(min_passes.values()) if min_passes else 0)
    if ref_plan is not None:
        ref_km = np.array([route_len(M.G, ref_plan[v["id"]]) for v in vs])
        changed = np.array([plan[v["id"]] != ref_plan[v["id"]] for v in vs])
        r.update(changed=int(changed.sum()),
                 extra_km_mean=float((km - ref_km)[changed].mean()) if changed.any() else 0.0,
                 extra_km_max=float((km - ref_km).max()))
    if warn is not None:
        thr = A["warn_threshold"]
        p = np.array([warn[v["id"]][0] for v in vs]); eta = np.array([warn[v["id"]][1] for v in vs])
        w = p >= thr
        tp, fp, fn = int((w & late).sum()), int((w & ~late).sum()), int((~w & late).sum())
        def comp(warned_rm):
            return float((late & w).sum() * warned_rm + (late & ~w).sum() * A["late_penalty_rm"])
        r.update(warnings=int(w.sum()), tp=tp, fp=fp, fn=fn, unwarned_late=int((late & ~w).sum()),
                 eta_covered=int((times[w] <= eta[w]).sum()),
                 comp_no_warnings=float(late.sum() * A["late_penalty_rm"]),
                 comp_rm5=comp(A["notified_late_rm"]), comp_rm10=comp(10.0), comp_rm20=comp(20.0),
                 brier=float(np.mean((p - late) ** 2)), _p=p, _late=late)
    return r

# ---------------------------------------------------------------- experiment
STRATS = ["static", "independent", "random_split", "coordinated", "school_safe"]
LABEL = {"static": "Static plan (average traffic)", "independent": "Live, independent (typical app)",
         "random_split": "Live, random split", "coordinated": "Live, coordinated (herd-aware)",
         "school_safe": "Live, coordinated + school-safe"}

def busiest_major_edges(M, vs, routes, n=3):
    plan = plan_independent(M, vs, routes, (None, None, True))
    use = Counter()
    for v in vs:
        for e in edges(plan[v["id"]]):
            use[e] += 1
    return [e for e, _ in use.most_common() if M.G.edges[e]["major"]][:n]

DAYTYPES = ("term", "holiday")

def run(G, place, n_vehicles, days, seed, incident_edge="auto", collect_warn=True, verbose=True, daytypes=DAYTYPES):
    setup = np.random.default_rng(seed)               # vehicles
    scen = np.random.default_rng(seed + 1000)         # scenario days (same for every strategy)
    alg = np.random.default_rng(seed + 2000)          # random split + Monte Carlo + sensor noise
    vs = make_vehicles(G, place, n_vehicles, setup)
    M = Model(G)
    routes = {}
    for v in vs:
        if v["key"] not in routes:
            routes[v["key"]] = candidate_routes(G, *v["key"])
    diag = diagnostics(M, vs, routes)
    if incident_edge == "auto":
        incident_edge = busiest_major_edges(M, vs, routes, 1)[0]
    # The static plan knows the school calendar (it is published in advance), but not today's traffic
    static = {dt: plan_independent(M, vs, routes, (None, None, dt == "term")) for dt in daytypes}
    E = list(G.edges)
    rows, sample_warn = [], None
    for di in range(days):
        true_bgm = dict(zip(E, scen.lognormal(0, A["noise_sigma"], len(E))))
        for dt in daytypes:
            school_on = dt == "term"
            for scenario in ("normal", "closure"):
                capm = {incident_edge: 0.4} if scenario == "closure" else None
                truth = (true_bgm, capm, school_on)
                live = live_view(G, true_bgm, capm, alg)
                view = (live[0], capm, school_on)
                plans = {"static": static[dt],
                         "independent": plan_independent(M, vs, routes, view),
                         "random_split": plan_random(M, vs, routes, view, alg),
                         "coordinated": plan_coordinated(M, vs, routes, view)}
                plans["school_safe"] = (plan_coordinated(M, vs, routes, view, A["school_safe_rm"])
                                        if school_on else plans["coordinated"])
                # Unavoidable passes: the fewest school-zone passes any acceptable route allows
                # (destination inside a school zone, or every route within the detour cap crosses one)
                min_passes = {v["id"]: min(M.school_passes(p, v["dep"], school_on) for p in routes[v["key"]])
                              for v in vs}
                for s in STRATS:
                    warn = (warnings_for(M, vs, plans[s], live, alg, school_on)
                            if (collect_warn and s in ("independent", "coordinated")) else None)
                    r = evaluate_day(M, vs, plans[s], truth, plans["independent"], warn, min_passes)
                    r.update(day=di, daytype=dt, scenario=scenario, strategy=s, seed=seed, vehicles=n_vehicles)
                    rows.append(r)
                    if (warn is not None and s == "coordinated" and scenario == "closure"
                            and dt == daytypes[0] and sample_warn is None):
                        sample_warn = (vs, plans[s], warn, truth, M)
        if verbose and (di + 1) % max(1, days // 5) == 0:
            print(f"  ... day {di + 1}/{days}")
    return rows, diag, incident_edge, sample_warn, (M, vs, routes, static)

def diagnostics(M, vs, routes):
    per_od = Counter(len(r) for r in routes.values())
    veh_multi = sum(len(routes[v["key"]]) > 1 for v in vs)
    ratios = [route_len(M.G, p) / route_len(M.G, rs[0]) for rs in routes.values() for p in rs[1:]]
    return dict(pairs=dict(sorted(per_od.items())), n_pairs=len(routes), vehicles_with_choice=veh_multi,
                alt_extra_median=(float(np.median(ratios)) - 1) if ratios else None,
                alt_extra_max=(max(ratios) - 1) if ratios else None)

# ---------------------------------------------------------------- reporting
def mean_ci(x):
    x = np.asarray(x, float)
    if len(x) < 2:
        return float(x.mean()), 0.0
    return float(x.mean()), float(1.96 * x.std(ddof=1) / math.sqrt(len(x)))

def summarise(rows, G, diag, incident_edge, title):
    print(f"\n=== {title} ===")
    print(f"Route search: {ROUTE_METHOD} | OD pairs: {diag['n_pairs']} | routes per pair: "
          + ", ".join(f"{k}:{v}" for k, v in diag["pairs"].items())
          + f" | vehicles with >1 route: {diag['vehicles_with_choice']}")
    if diag["alt_extra_median"] is not None:
        print(f"Alternatives are {diag['alt_extra_median']:.0%} longer (median), {diag['alt_extra_max']:.0%} max; cap {A['detour_cap'] - 1:.0%}")
    print(f"Simulated closure: 60% capacity loss on {G.edges[incident_edge]['name']}")
    sc = load_school_sessions()
    print(f"Wave starts {A['wave_start']}; schools: {len(sc)} listed "
          f"({sum(r['session'] == 'unknown' for r in sc)} with unverified session, treated as "
          f"{A['unknown_session_as']}; two-session share of those primaries {A['double_session_share']:.0%}); "
          f"school-zone road segments: {sum(1 for *_, d in G.edges(data=True) if d.get('school'))}")
    combos = [(dt, sc) for dt in DAYTYPES for sc in ("normal", "closure")
              if any(r["daytype"] == dt and r["scenario"] == sc for r in rows)]
    for daytype, scenario in combos:
        R = [r for r in rows if r["scenario"] == scenario and r["daytype"] == daytype]
        days = sorted({(r["seed"], r["day"]) for r in R})
        tag_ = f"{daytype.upper()} DAY, {scenario.upper()}"
        print(f"\n-- {tag_} ({len(days)} simulated days) -- LEDGER 1: physical")
        print(f"{'strategy':34s}{'on-time':>9s}{'veh-hours':>11s}{'P90 min':>9s}{'fuel RM':>9s}{'time+fuel RM':>14s}{'changed':>9s}{'school':>8s}{'avoidable':>10s}")
        for s in STRATS:
            X = [r for r in R if r["strategy"] == s]
            m = lambda k: np.mean([x[k] for x in X])
            print(f"{LABEL[s]:34s}{m('on_time'):8.1f}%{m('veh_hours'):11.1f}{m('p90_min'):9.1f}"
                  f"{m('fuel_rm'):9,.0f}{m('phys_rm'):14,.0f}{m('changed'):9.1f}{m('school_passes'):8.0f}"
                  f"{m('school_passes') - m('school_unavoidable'):10.0f}")
        print("Paired difference vs live independent (mean ± 95% CI across days):")
        idx = {(r["seed"], r["day"], r["strategy"]): r for r in R}
        for s in ("static", "random_split", "coordinated", "school_safe"):
            d_on = [idx[k + (s,)]["on_time"] - idx[k + ("independent",)]["on_time"] for k in days]
            d_vh = [idx[k + (s,)]["veh_hours"] - idx[k + ("independent",)]["veh_hours"] for k in days]
            (a, ea), (b, eb) = mean_ci(d_on), mean_ci(d_vh)
            print(f"  {LABEL[s]:32s} on-time {a:+.2f} ± {ea:.2f} pts | vehicle-hours {b:+.2f} ± {eb:.2f}")
        X = [r for r in R if r["strategy"] == "coordinated" and r["changed"] > 0]
        if X:
            print(f"Detours (coordinated vs independent): {np.mean([r['changed'] for r in R if r['strategy']=='coordinated']):.1f} vehicles/day "
                  f"moved, mean extra {np.mean([r['extra_km_mean'] for r in X]):.2f} km, worst {max(r['extra_km_max'] for r in X):.2f} km")
        print(f"-- {tag_} -- LEDGER 2: early warnings (same policy on both plans)")
        print(f"{'plan':34s}{'warn/day':>9s}{'precision':>10s}{'recall':>8s}{'ETA ok':>8s}{'unwarned':>9s}"
              f"{'comp RM':>9s}{'@RM5':>8s}{'@RM10':>8s}{'@RM20':>8s}{'Brier':>7s}")
        for s in ("independent", "coordinated"):
            X = [r for r in R if r["strategy"] == s and "tp" in r]
            if not X:
                continue
            tp, fp, fn = (sum(x[k] for x in X) for k in ("tp", "fp", "fn"))
            w = sum(x["warnings"] for x in X); cov = sum(x["eta_covered"] for x in X)
            m = lambda k: np.mean([x[k] for x in X])
            print(f"{LABEL[s]:34s}{w / len(X):9.1f}{tp / max(tp + fp, 1):10.0%}{tp / max(tp + fn, 1):8.0%}"
                  f"{cov / max(w, 1):8.0%}{m('unwarned_late'):9.1f}{m('comp_no_warnings'):9,.0f}"
                  f"{m('comp_rm5'):8,.0f}{m('comp_rm10'):8,.0f}{m('comp_rm20'):8,.0f}{m('brier'):7.3f}")
    print("school = vehicle passes through school-zone roads during school windows; avoidable = passes above the"
          "\nminimum any acceptable route allows (the rest are unavoidable: destination or every route in a school zone)")
    print("comp RM = modelled compensation with no warnings (RM20 per late drop); @RM5/10/20 = same, if a warned late"
          "\ndrop costs RM5/10/20 instead. @RM20 shows warnings saving nothing: compensation value is an ASSUMPTION.")

def calibration_table(rows):
    P = np.concatenate([r["_p"] for r in rows if "_p" in r]); L = np.concatenate([r["_late"] for r in rows if "_late" in r])
    print("\nCalibration of P(late) (all warned-plan vehicles, both scenarios):")
    print(" predicted   n      observed late rate")
    for lo, hi in [(0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)]:
        m = (P >= lo) & (P < hi)
        if m.sum():
            print(f" {lo:.1f}-{min(hi, 1):.1f}  {m.sum():7d}   {L[m].mean():.0%}")

CAL_BINS = [(0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.01)]

def plot_calibration(rows, fname, title=""):
    """Reliability diagram: predicted P(late) (binned) vs the share of those trips that
    actually arrived late. On the diagonal = honest probabilities. Point size = trips."""
    names = {"independent": "Typical app", "coordinated": "Our advisor"}
    fig, ax = plt.subplots(figsize=(6.4, 6))
    ax.plot([0, 1], [0, 1], ls="--", c="#888", lw=1, label="Perfectly calibrated")
    for s, col, mk in (("independent", "#C2410C", "s"), ("coordinated", "#2B5FAD", "o")):
        R = [r for r in rows if r.get("strategy") == s and "_p" in r]
        if not R:
            continue
        P = np.concatenate([r["_p"] for r in R]); L = np.concatenate([r["_late"] for r in R]).astype(float)
        xs, ys, ns = [], [], []
        for lo, hi in CAL_BINS:
            m = (P >= lo) & (P < hi)
            if m.sum() >= 20:
                xs.append(P[m].mean()); ys.append(L[m].mean()); ns.append(m.sum())
        brier = float(np.mean((P - L) ** 2))
        ax.plot(xs, ys, c=col, lw=1.5, alpha=.8)
        ax.scatter(xs, ys, s=[20 + 180 * n / max(ns) for n in ns], c=col, marker=mk, zorder=3,
                   label=f"{names[s]} (Brier {brier:.3f})")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal")
    ax.set_xlabel("Predicted chance of being late"); ax.set_ylabel("Share that actually arrived late")
    ax.set_title(title or "Are the late warnings honest?", fontsize=11)
    ax.grid(alpha=.25); ax.legend(loc="upper left", fontsize=9, frameon=False)
    fig.tight_layout(); fig.savefig(fname, dpi=150); plt.close(fig)

def save_rows(rows, fname):
    keys = [k for k in rows[0] if not k.startswith("_")]
    for r in rows:
        for k in r:
            if not k.startswith("_") and k not in keys:
                keys.append(k)
    with open(fname, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def save_sample_warnings(sample, fname):
    if not sample:
        return
    vs, plan, warn, truth, M = sample
    rows = []
    for v in vs:
        p, eta = warn[v["id"]]
        if p >= A["warn_threshold"]:
            rows.append(dict(vehicle=v["id"], hub=v["hub"], destination=v["dest"], p_late=round(p, 2),
                             promised_min=round(v["deadline"]), realistic_eta_min=round(eta),
                             action=f"Notify customer: realistic ETA {eta:.0f} min (promised {v['deadline']:.0f})"))
    rows.sort(key=lambda r: -r["p_late"])
    with open(fname, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["vehicle"])
        w.writeheader(); w.writerows(rows)
    print(f"Sample closure-day warnings ({len(rows)}) -> {fname}")

def plot_ledger1(rows, fname, title):
    combos = [(dt, sc) for dt in DAYTYPES for sc in ("normal", "closure")
              if any(r["daytype"] == dt and r["scenario"] == sc for r in rows)]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.4))
    cols = {"static": "#c4c8ce", "independent": "#7d8590", "random_split": "#c9a227",
            "coordinated": "#3b7dd8", "school_safe": "#1f4e8c"}
    w = 0.16
    for i, (k, t, fmt) in enumerate([("on_time", "On-time deliveries (%)", "{:.0f}"),
                                      ("veh_hours", "Vehicle-hours per wave", "{:.0f}")]):
        x = np.arange(len(combos))
        for j, s in enumerate(STRATS):
            vals = [np.mean([r[k] for r in rows if r["strategy"] == s and r["daytype"] == dt and r["scenario"] == sc])
                    for dt, sc in combos]
            b = ax[i].bar(x + (j - 2) * w, vals, w, color=cols[s], label=LABEL[s])
            for bb, val in zip(b, vals):
                ax[i].text(bb.get_x() + bb.get_width() / 2, bb.get_height(), fmt.format(val), ha="center",
                           va="bottom", fontsize=6.5)
        ax[i].set_xticks(x)
        ax[i].set_xticklabels([f"{'School term' if dt == 'term' else 'School holiday'}\n"
                               f"{'normal' if sc == 'normal' else 'simulated closure'}" for dt, sc in combos], fontsize=8)
        ax[i].set_title(t); ax[i].spines[["top", "right"]].set_visible(False)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(fname, dpi=150)

# ---------------------------------------------------------------- main
def main():
    global ROUTE_METHOD
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", action="store_true")
    ap.add_argument("--graph", default=None, help="path to a cached GraphML file")
    ap.add_argument("--routes", default="penalty", choices=["penalty", "yen"])
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--vehicles", type=int, default=A["n_vehicles"])
    ap.add_argument("--sweep", action="store_true", help="fleet size x incident location x seeds")
    ap.add_argument("--wave", default=A["wave_start"], help="wave start clock time, e.g. 07:00")
    ap.add_argument("--double-session", type=float, default=0.0,
                    help="sensitivity: share of unverified primary schools treated as two-session (0-1)")
    ap.add_argument("--wave-scan", action="store_true", help="term-day results for several wave start times")
    ap.add_argument("--commuters", type=float, default=A["commuters"],
                    help="scale on commuter traffic from outside Kuching (0 = off, 1 = assumed levels)")
    ap.add_argument("--fake-scan", action="store_true", help="robustness to fake trip requests (abuse test)")
    ap.add_argument("--noise-scan", action="store_true", help="robustness to traffic noise and live-data error")
    ap.add_argument("--priority-scan", action="store_true", help="does claiming urgency pay? (priority inflation test)")
    args = ap.parse_args()
    ROUTE_METHOD = args.routes
    A["wave_start"] = args.wave
    A["double_session_share"] = args.double_session
    A["commuters"] = args.commuters
    days = args.days or (20 if args.osm else 60)
    tag = ("osm" if args.osm else "approx") + ("_yen" if ROUTE_METHOD == "yen" else "")
    net_rng = np.random.default_rng(7)          # background traffic levels: fixed across seeds
    G, place = osm_kuching(net_rng, args.graph) if args.osm else schematic_kuching(net_rng)
    print("Map:", "OpenStreetMap (real roads)" if args.osm else "approximate corridor model")
    print("ASSUMPTIONS:", A)
    if A["commuters"] > 0:
        funnel_report(G)

    if args.sweep:
        return sweep(G, place, days, args.seeds, tag)
    if args.wave_scan:
        return wave_scan(G, place, days, args.seeds, args.vehicles, tag)
    if args.fake_scan:
        return fake_scan(G, place, days, args.seeds, args.vehicles, tag)
    if args.priority_scan:
        return priority_scan(G, place, days, args.seeds, args.vehicles, tag)
    if args.noise_scan:
        return noise_scan(G, place, days, args.seeds, args.vehicles, tag)

    all_rows, diag, inc, sample = [], None, None, None
    for seed in range(1, args.seeds + 1):
        print(f"seed {seed}:")
        rows, d, inc_e, sw, ctx = run(G, place, args.vehicles, days, seed)
        all_rows += rows; diag = diag or d; inc = inc or inc_e; sample = sample or sw
    title = (f"Kuching ({'real OSM roads' if args.osm else 'approximate map'}), {args.vehicles} vehicles, "
             f"{days} days x {args.seeds} seeds — simulated")
    summarise(all_rows, G, diag, inc, title)
    calibration_table([r for r in all_rows if "_p" in r])
    save_rows(all_rows, f"results_{tag}.csv")
    save_sample_warnings(sample, f"warnings_{tag}.csv")
    plot_ledger1(all_rows, f"ledger1_{tag}.png", title)
    plot_calibration(all_rows, f"calibration_{tag}.png", "Are the late warnings honest? " + title.split(",")[0].replace(" (", ", ").rstrip(")") + ", simulated")
    print(f"Saved: results_{tag}.csv, warnings_{tag}.csv, ledger1_{tag}.png, calibration_{tag}.png")

def sweep(G, place, days, seeds, tag):
    """Fleet size x incident location x seed. Reports the paired coordinated-minus-
    independent difference so a positive result is not an artefact of one setup."""
    out = []
    for n in (100, 200, 400, 800):
        for seed in range(1, seeds + 1):
            setup = np.random.default_rng(seed)
            vs = make_vehicles(G, place, n, setup)
            M = Model(G)
            routes = {}
            for v in vs:
                routes.setdefault(v["key"], candidate_routes(G, *v["key"]))
            for rank, e in enumerate(busiest_major_edges(M, vs, routes, 3)):
                rows, *_ = run(G, place, n, days, seed, incident_edge=e, collect_warn=False, verbose=False)
                for dt, sc in itertools.product(DAYTYPES, ("normal", "closure")):
                    idx = {(r["day"], r["strategy"]): r for r in rows if r["scenario"] == sc and r["daytype"] == dt}
                    d_on = [idx[(d, "coordinated")]["on_time"] - idx[(d, "independent")]["on_time"] for d in range(days)]
                    d_rs = [idx[(d, "random_split")]["on_time"] - idx[(d, "independent")]["on_time"] for d in range(days)]
                    d_vh = [idx[(d, "coordinated")]["veh_hours"] - idx[(d, "independent")]["veh_hours"] for d in range(days)]
                    d_ss = [idx[(d, "school_safe")]["on_time"] - idx[(d, "independent")]["on_time"] for d in range(days)]
                    (a, ea), (b, eb), (c, ec), (q, eq) = mean_ci(d_on), mean_ci(d_rs), mean_ci(d_vh), mean_ci(d_ss)
                    out.append(dict(vehicles=n, seed=seed, incident_rank=rank + 1, incident=G.edges[e]["name"],
                                    daytype=dt, scenario=sc, coord_on_time_diff=round(a, 2), ci=round(ea, 2),
                                    random_on_time_diff=round(b, 2), random_ci=round(eb, 2),
                                    coord_veh_hours_diff=round(c, 2), vh_ci=round(ec, 2),
                                    school_safe_on_time_diff=round(q, 2), school_safe_ci=round(eq, 2)))
                    print(f"n={n:3d} seed={seed} incident#{rank + 1} {dt:7s} {sc:7s} coordinated {a:+.2f}±{ea:.2f} pts | school-safe {q:+.2f}±{eq:.2f} | "
                          f"random {b:+.2f}±{eb:.2f} | veh-hours {c:+.2f}±{ec:.2f}")
    save_rows(out, f"sweep_{tag}.csv")
    plot_sweep(out, f"fleet_size_effect_{tag}.png", tag)
    print(f"Saved: sweep_{tag}.csv, fleet_size_effect_{tag}.png")

def noise_scan(G, place, days, seeds, n, tag):
    """Robustness to noisy data. Varies one at a time (the other stays at its default):
      noise_sigma  : how much real traffic differs day to day from the usual pattern
      sensor_sigma : how wrong the live traffic reading is
    School-term days. Reports on-time (typical app vs our advisor) and warning quality."""
    base = (A["noise_sigma"], A["sensor_sigma"])
    grid = [("noise_sigma", x) for x in (0.10, 0.25, 0.40)] + [("sensor_sigma", x) for x in (0.05, 0.20)]
    out = []
    for knob, val in grid:
        A["noise_sigma"], A["sensor_sigma"] = base
        A[knob] = val
        rows = []
        for seed in range(1, seeds + 1):
            r_, *_ = run(G, place, n, days, seed, verbose=False, daytypes=("term",))
            rows += r_
        for sc in ("normal", "closure"):
            R = [r for r in rows if r["scenario"] == sc]
            keys = sorted({(r["seed"], r["day"]) for r in R})
            idx = {(r["seed"], r["day"], r["strategy"]): r for r in R}
            ind = np.mean([idx[k + ("independent",)]["on_time"] for k in keys])
            crd = np.mean([idx[k + ("coordinated",)]["on_time"] for k in keys])
            dc = mean_ci([idx[k + ("coordinated",)]["on_time"] - idx[k + ("independent",)]["on_time"] for k in keys])
            W = [idx[k + ("coordinated",)] for k in keys]
            tp, fp, fn = (sum(w.get(x) or 0 for w in W) for x in ("tp", "fp", "fn"))
            prec = tp / (tp + fp) if tp + fp else float("nan"); rec = tp / (tp + fn) if tp + fn else float("nan")
            P = np.concatenate([w["_p"] for w in W if "_p" in w]); L = np.concatenate([w["_late"] for w in W if "_late" in w])
            brier = float(np.mean((P - L) ** 2))
            out.append(dict(knob=knob, noise_sigma=A["noise_sigma"], sensor_sigma=A["sensor_sigma"], scenario=sc,
                            typical_app_on_time=round(ind, 1), advisor_on_time=round(crd, 1),
                            advisor_diff=round(dc[0], 2), ci=round(dc[1], 2),
                            warn_precision=round(100 * prec, 1), warn_recall=round(100 * rec, 1), brier=round(brier, 3)))
            print(f"{knob}={val:.2f} {sc:7s} typical app {ind:5.1f}% | advisor {crd:5.1f}% ({dc[0]:+.2f}±{dc[1]:.2f}) | "
                  f"warnings precision {prec:.0%} recall {rec:.0%} | Brier {brier:.3f}")
    A["noise_sigma"], A["sensor_sigma"] = base
    save_rows(out, f"noise_scan_{tag}.csv")
    print(f"Saved: noise_scan_{tag}.csv")

def wave_scan(G, place, days, seeds, n, tag):
    """Term-day results for waves starting at different clock times: how much does
    overlap with school drop-off / session change matter?"""
    out = []
    for start in ("06:30", "07:00", "07:30", "08:00", "10:00", "12:45", "13:15", "14:00", "18:00"):
        A["wave_start"] = start
        rows = []
        for seed in range(1, seeds + 1):
            r_, *_ = run(G, place, n, days, seed, collect_warn=False, verbose=False, daytypes=("term",))
            rows += r_
        for sc in ("normal", "closure"):
            R = [r for r in rows if r["scenario"] == sc]
            keys = sorted({(r["seed"], r["day"]) for r in R})
            idx = {(r["seed"], r["day"], r["strategy"]): r for r in R}
            ind = np.mean([idx[k + ("independent",)]["on_time"] for k in keys])
            dc = mean_ci([idx[k + ("coordinated",)]["on_time"] - idx[k + ("independent",)]["on_time"] for k in keys])
            ds = mean_ci([idx[k + ("school_safe",)]["on_time"] - idx[k + ("independent",)]["on_time"] for k in keys])
            sp = {s: np.mean([idx[k + (s,)]["school_passes"] for k in keys]) for s in ("independent", "coordinated", "school_safe")}
            un = np.mean([idx[k + ("independent",)]["school_unavoidable"] for k in keys])
            out.append(dict(wave_start=start, scenario=sc, independent_on_time=round(ind, 1),
                            coordinated_diff=round(dc[0], 2), coordinated_ci=round(dc[1], 2),
                            school_safe_diff=round(ds[0], 2), school_safe_ci=round(ds[1], 2),
                            school_passes_independent=round(sp["independent"]), school_passes_coordinated=round(sp["coordinated"]),
                            school_passes_school_safe=round(sp["school_safe"]), school_unavoidable=round(un)))
            print(f"{start} {sc:7s} typical app {ind:5.1f}% | coordinated {dc[0]:+.2f}±{dc[1]:.2f} | school-safe "
                  f"{ds[0]:+.2f}±{ds[1]:.2f} | school passes {sp['independent']:.0f}/{sp['coordinated']:.0f}/{sp['school_safe']:.0f}"
                  f" (unavoidable {un:.0f})")
    save_rows(out, f"wave_scan_{tag}.csv")
    print(f"Saved: wave_scan_{tag}.csv")

def fake_scan(G, place, days, seeds, n, tag):
    """Abuse test. Fake trip requests (phantoms) are counted by the coordinated
    planner as if real, but never drive. Real deliveries are then evaluated.
      random   : fake trips spread like real demand (spam / noise)
      targeted : fake trips all on the busiest real origin-destination pair, so the
                 planner steers real vehicles off that corridor (someone 'reserving' it)
    The typical app ignores other vehicles, so fake trips cannot affect it: it is the
    floor that coordination must stay above. School-term days, wave at A['wave_start']."""
    out = []
    for frac in (0.0, 0.1, 0.3, 0.5):
        for mode in (("random", "targeted") if frac else ("none",)):
            rows = []
            for seed in range(1, seeds + 1):
                setup = np.random.default_rng(seed); scen = np.random.default_rng(seed + 1000)
                alg = np.random.default_rng(seed + 2000); fk = np.random.default_rng(seed + 3000)
                vs = make_vehicles(G, place, n, setup)
                M = Model(G)
                routes = {}
                for v in vs:
                    routes.setdefault(v["key"], candidate_routes(G, *v["key"]))
                incident = busiest_major_edges(M, vs, routes, 1)[0]
                k = int(round(frac * n))
                fakes = make_vehicles(G, place, k, fk) if k else []
                if mode == "targeted" and fakes:
                    top = Counter(v["key"] for v in vs).most_common(1)[0][0]
                    tv = next(v for v in vs if v["key"] == top)
                    for f in fakes:
                        f.update(key=top, o=tv["o"], d=tv["d"], hub=tv["hub"], dest=tv["dest"])
                for f in fakes:
                    f["id"] += 100000
                    routes.setdefault(f["key"], candidate_routes(G, *f["key"]))
                E = list(G.edges)
                for di in range(days):
                    true_bgm = dict(zip(E, scen.lognormal(0, A["noise_sigma"], len(E))))
                    for scenario in ("normal", "closure"):
                        capm = {incident: 0.4} if scenario == "closure" else None
                        truth = (true_bgm, capm, True)
                        live = live_view(G, true_bgm, capm, alg)
                        view = (live[0], capm, True)
                        ind = plan_independent(M, vs, routes, view)
                        honest = plan_coordinated(M, vs, routes, view)
                        fooled = plan_coordinated(M, vs + fakes, routes, view)       # planner sees fakes
                        fooled = {v["id"]: fooled[v["id"]] for v in vs}              # only real vehicles drive
                        safe = plan_coordinated(M, vs + fakes, routes, view, A["school_safe_rm"])
                        safe = {v["id"]: safe[v["id"]] for v in vs}
                        for s, p in (("independent", ind), ("coordinated_honest", honest),
                                     ("coordinated_with_fakes", fooled), ("school_safe_with_fakes", safe)):
                            r = evaluate_day(M, vs, p, truth, ind)
                            r.update(seed=seed, day=di, scenario=scenario, strategy=s)
                            rows.append(r)
            for sc in ("normal", "closure"):
                R = [r for r in rows if r["scenario"] == sc]
                keys = sorted({(r["seed"], r["day"]) for r in R})
                idx = {(r["seed"], r["day"], r["strategy"]): r for r in R}
                d = lambda a, b: mean_ci([idx[k_ + (a,)]["on_time"] - idx[k_ + (b,)]["on_time"] for k_ in keys])
                vs_ind, vs_hon = d("coordinated_with_fakes", "independent"), d("coordinated_with_fakes", "coordinated_honest")
                ss_ind = d("school_safe_with_fakes", "independent")
                tgt = np.mean([idx[k_ + ("coordinated_with_fakes",)]["changed"] for k_ in keys])
                out.append(dict(fake_share=frac, mode=mode, scenario=sc,
                                typical_app_on_time=round(np.mean([idx[k_ + ("independent",)]["on_time"] for k_ in keys]), 1),
                                fooled_vs_typical=round(vs_ind[0], 2), ci=round(vs_ind[1], 2),
                                fooled_vs_honest=round(vs_hon[0], 2), ci_honest=round(vs_hon[1], 2),
                                school_safe_fooled_vs_typical=round(ss_ind[0], 2), vehicles_moved=round(tgt, 1)))
                print(f"fakes {frac:4.0%} {mode:8s} {sc:7s} coordinated (fooled) vs typical app {vs_ind[0]:+.2f}±{vs_ind[1]:.2f} | "
                      f"vs honest coordination {vs_hon[0]:+.2f}±{vs_hon[1]:.2f} | school-safe vs typical {ss_ind[0]:+.2f}")
    save_rows(out, f"fake_scan_{tag}.csv")
    print(f"Saved: fake_scan_{tag}.csv")

def priority_scan(G, place, days, seeds, n, tag):
    """Priority inflation test ('tools, not priority'). The coordinated planner
    serves vehicles in some order; earlier vehicles get first pick of roads.
      honest_slack  : tightest true deadline first (fleet orders: deadlines are real)
      neutral       : by departure time, ignoring deadlines (first come, first served)
      all_urgent    : every trip claims maximum urgency (everyone games it)
      cheat_30      : 30% of trips falsely claim maximum urgency, the rest honest
    Claimed urgency changes only what the PLANNER sees; results use true deadlines.
    Key question: do cheaters gain, and does everyone cheating help anyone?
    School-term days, wave at A['wave_start']."""
    out = []
    for seed in range(1, seeds + 1):
        setup = np.random.default_rng(seed); scen = np.random.default_rng(seed + 1000)
        alg = np.random.default_rng(seed + 2000); ch = np.random.default_rng(seed + 4000)
        vs = make_vehicles(G, place, n, setup)
        M = Model(G)
        routes = {}
        for v in vs:
            routes.setdefault(v["key"], candidate_routes(G, *v["key"]))
        incident = busiest_major_edges(M, vs, routes, 1)[0]
        cheaters = set(int(i) for i in ch.choice(n, size=int(0.3 * n), replace=False))
        def claim(vs_, who):
            # claimed deadline = free-flow time (zero slack), i.e. "maximum urgency"
            out_ = []
            for v in vs_:
                c = dict(v)
                if who is None or v["id"] in who:
                    c["deadline"] = min(M.trip(p, v["dep"], {}, (None, None, True))[0] for p in routes[v["key"]])
                out_.append(c)
            return out_
        everyone = claim(vs, None); some = claim(vs, cheaters)
        E = list(G.edges)
        for di in range(days):
            true_bgm = dict(zip(E, scen.lognormal(0, A["noise_sigma"], len(E))))
            for scenario in ("normal", "closure"):
                capm = {incident: 0.4} if scenario == "closure" else None
                truth = (true_bgm, capm, True)
                view = (live_view(G, true_bgm, capm, alg)[0], capm, True)
                plans = {"independent": plan_independent(M, vs, routes, view),
                         "honest_slack": plan_coordinated(M, vs, routes, view, order="slack"),
                         "neutral": plan_coordinated(M, vs, routes, view, order="departure"),
                         "all_urgent": plan_coordinated(M, everyone, routes, view, order="slack"),
                         "cheat_30": plan_coordinated(M, some, routes, view, order="slack")}
                for s, p in plans.items():
                    f = M.flows_of(p, vs)
                    late = {v["id"]: M.trip(p[v["id"]], v["dep"], f, truth)[0] > v["deadline"] for v in vs}
                    ch_on = 100 * (1 - np.mean([late[i] for i in cheaters]))
                    hon_on = 100 * (1 - np.mean([late[v["id"]] for v in vs if v["id"] not in cheaters]))
                    out.append(dict(seed=seed, day=di, scenario=scenario, strategy=s, vehicles=n,
                                    on_time=100 * (1 - np.mean(list(late.values()))),
                                    group_cheaters_on_time=ch_on, group_others_on_time=hon_on))
    rows = []
    print(f"\nPriority inflation test — {n} vehicles, school-term days ({days} days x {seeds} seeds)")
    for sc in ("normal", "closure"):
        R = [r for r in out if r["scenario"] == sc]
        keys = sorted({(r["seed"], r["day"]) for r in R})
        idx = {(r["seed"], r["day"], r["strategy"]): r for r in R}
        d = lambda a, b, k="on_time": mean_ci([idx[x + (a,)][k] - idx[x + (b,)][k] for x in keys])
        print(f"-- {sc}: on-time vs honest tightest-deadline-first (pts, mean ± 95% CI)")
        for s in ("independent", "neutral", "all_urgent", "cheat_30"):
            m, e = d(s, "honest_slack")
            print(f"   {s:12s} {m:+.2f} ± {e:.2f}")
            rows.append(dict(vehicles=n, scenario=sc, comparison=f"{s} vs honest_slack", diff=round(m, 2), ci=round(e, 2)))
        mc, ec = d("cheat_30", "honest_slack", "group_cheaters_on_time")
        mo, eo = d("cheat_30", "honest_slack", "group_others_on_time")
        print(f"   with 30% cheating: cheaters {mc:+.2f} ± {ec:.2f} | honest others {mo:+.2f} ± {eo:.2f}")
        rows.append(dict(vehicles=n, scenario=sc, comparison="cheaters gain (cheat_30 vs honest)", diff=round(mc, 2), ci=round(ec, 2)))
        rows.append(dict(vehicles=n, scenario=sc, comparison="honest others change (cheat_30 vs honest)", diff=round(mo, 2), ci=round(eo, 2)))
    save_rows(rows, f"priority_scan_{n}_{tag}.csv")
    print(f"Saved: priority_scan_{n}_{tag}.csv")

def plot_sweep(out, fname, tag):
    """On-time gain over the typical app, by fleet size. Left: school holidays.
    Right: school term, including school-safe coordination. Points = mean over
    seeds x closure locations; bars = min to max."""
    sizes = sorted({int(r["vehicles"]) for r in out})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), sharey=True)
    panels = (("holiday", "School holiday", (("normal", "coord_on_time_diff", "#7fb0ea", "-", "Coordinated, normal"),
                                             ("closure", "coord_on_time_diff", "#1f4e8c", "-", "Coordinated, closure"))),
              ("term", "School term", (("normal", "coord_on_time_diff", "#7fb0ea", "-", "Coordinated, normal"),
                                       ("closure", "coord_on_time_diff", "#1f4e8c", "-", "Coordinated, closure"),
                                       ("closure", "school_safe_on_time_diff", "#c9a227", "--", "School-safe, closure"))))
    for ax, (dt, title, lines) in zip(axes, panels):
        for sc, key, col, ls, lab in lines:
            sel = lambda n: [float(r[key]) for r in out if int(r["vehicles"]) == n and r["scenario"] == sc
                             and r.get("daytype", "term") == dt and key in r]
            if not sel(sizes[0]):
                continue
            m = [np.mean(sel(n)) for n in sizes]; lo = [min(sel(n)) for n in sizes]; hi = [max(sel(n)) for n in sizes]
            ax.errorbar(sizes, m, yerr=[np.subtract(m, lo), np.subtract(hi, m)], marker="o", capsize=3, color=col,
                        ls=ls, label=lab, lw=1.5)
            ax.annotate(f"{m[-1]:+.1f}", (sizes[-1], m[-1]), xytext=(8, -3), textcoords="offset points",
                        fontsize=8, color=col)
        ax.axhline(0, color="#888", lw=0.8)
        ax.set_xscale("log", base=2); ax.set_xticks(sizes); ax.set_xticklabels([str(n) for n in sizes])
        ax.set_xlim(sizes[0] * 0.8, sizes[-1] * 1.35)
        ax.set_title(title, fontsize=10); ax.set_xlabel("Vehicles coordinated in one 15-minute wave")
        ax.spines[["top", "right"]].set_visible(False); ax.legend(frameon=False, fontsize=8, loc="upper left")
    axes[0].set_ylabel("On-time gain vs typical app (pts)")
    fig.suptitle("Coordination pays off as more vehicles take part; on school days it must also avoid school zones\n"
                 f"({'real OSM roads' if tag.startswith('osm') else 'approximate Kuching map'}, simulated, wave at "
                 f"{A['wave_start']}; bars = range over seeds x closure locations)", fontsize=9.5)
    fig.tight_layout(); fig.savefig(fname, dpi=150)

if __name__ == "__main__":
    main()
