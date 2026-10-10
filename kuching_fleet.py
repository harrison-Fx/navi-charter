"""
Kuching Herd-Aware Dispatch Advisor — prototype
================================================
Predict early : which deliveries will be late, given peak-hour traffic AND
                where the platform has already sent its other vehicles.
Decide better : split vehicles across sensible routes (detour cap), then for
                each at-risk delivery recommend a reroute or an honest ETA.

Map modes
  python kuching_fleet.py          -> approximate Kuching corridor model (offline)
  python kuching_fleet.py --osm    -> real Kuching road network from OpenStreetMap
                                      (needs: pip install osmnx; internet)

Traffic volumes are SIMULATED (no public live feed for Kuching). Every
assumption is in ASSUMPTIONS and printed with the results.
"""
import sys, math, itertools, csv
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 7
rng = np.random.default_rng(SEED)

ASSUMPTIONS = dict(
    n_vehicles=400,          # vehicles one delivery platform dispatches in a 15-min peak window
    fuel_l_per_km=0.12,
    idle_l_per_min=0.02,     # fuel burned per minute of congestion delay
    fuel_rm_per_l=2.15,      # diesel price assumption (Sarawak)
    driver_rm_per_min=0.25,  # ~RM15/hour
    late_penalty_rm=20.0,    # voucher/refund + reputational cost per late drop
    notified_late_rm=5.0,    # same late drop, but customer was warned early
    detour_cap=1.25,         # never suggest a route >25% longer than the shortest
    noise_sigma=0.25,        # day-to-day uncertainty in background traffic
    warn_threshold=0.5,      # warn when P(late) >= this
)
A = ASSUMPTIONS

# Road classes: free-flow speed (km/h), capacity (veh per 15 min, one direction),
# and peak-hour background volume/capacity range.
ROAD = {
    "trunk":     (70, 900, (0.85, 1.00)),
    "primary":   (50, 700, (0.85, 1.00)),
    "secondary": (40, 450, (0.70, 0.90)),
    "tertiary":  (30, 250, (0.40, 0.60)),
}

# ---------------------------------------------------------------- places
# Approximate centres of Kuching areas (lat, lon). Rough positions only.
AREAS = {
    "City Centre":   (1.5580, 110.3450),
    "Padungan":      (1.5565, 110.3570),
    "Pending":       (1.5550, 110.3850),
    "Bintawa":       (1.5680, 110.3720),
    "Kenyalang":     (1.5450, 110.3620),
    "Simpang Tiga":  (1.5350, 110.3550),
    "Stutong":       (1.5200, 110.3750),
    "Tabuan Jaya":   (1.5300, 110.3900),
    "Hui Sing":      (1.5230, 110.3600),
    "Batu Lintang":  (1.5400, 110.3450),
    "Satok":         (1.5520, 110.3350),
    "Petra Jaya":    (1.5750, 110.3300),
    "Batu Kawa":     (1.5150, 110.3000),
    "Matang":        (1.5500, 110.2850),
    "Airport":       (1.4870, 110.3450),
    "Kota Sentosa":  (1.4700, 110.3300),
}
HUBS = {"Pending": 0.65, "Kota Sentosa": 0.35}          # courier hubs (share of vehicles)
DESTS = {"City Centre": 2, "Padungan": 2, "Kenyalang": 2, "Simpang Tiga": 2,
         "Stutong": 3, "Tabuan Jaya": 3, "Hui Sing": 3, "Batu Lintang": 2,
         "Satok": 2, "Petra Jaya": 3, "Batu Kawa": 4, "Matang": 2}

# Simplified corridors between neighbouring areas (approximate, NOT exact roads).
CORRIDORS = [
    ("City Centre", "Padungan", "primary"),   ("Padungan", "Pending", "primary"),
    ("Padungan", "Kenyalang", "secondary"),   ("Pending", "Bintawa", "secondary"),
    ("Pending", "Tabuan Jaya", "secondary"),  ("Kenyalang", "Simpang Tiga", "primary"),
    ("City Centre", "Batu Lintang", "secondary"), ("City Centre", "Satok", "primary"),
    ("Satok", "Petra Jaya", "primary"),       ("Satok", "Batu Kawa", "primary"),
    ("Satok", "Batu Lintang", "secondary"),   ("Batu Lintang", "Simpang Tiga", "secondary"),
    ("Batu Lintang", "Airport", "primary"),   ("Simpang Tiga", "Hui Sing", "secondary"),
    ("Simpang Tiga", "Stutong", "primary"),   ("Stutong", "Tabuan Jaya", "primary"),
    ("Stutong", "Hui Sing", "tertiary"),      ("Hui Sing", "Airport", "secondary"),
    ("Airport", "Kota Sentosa", "trunk"),     ("Batu Kawa", "Kota Sentosa", "secondary"),
    ("Batu Kawa", "Matang", "secondary"),     ("Matang", "Petra Jaya", "secondary"),
    ("Kota Sentosa", "Stutong", "trunk"),     ("Bintawa", "Petra Jaya", "tertiary"),
    # neighbourhood back-roads (taman roads drivers use to dodge main-road jams)
    ("Pending", "Kenyalang", "tertiary"),     ("Kenyalang", "Batu Lintang", "tertiary"),
    ("Padungan", "Batu Lintang", "tertiary"), ("Tabuan Jaya", "Kenyalang", "tertiary"),
    ("Hui Sing", "Batu Lintang", "tertiary"), ("Airport", "Batu Kawa", "tertiary"),
]

def haversine_km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = (math.sin((la2 - la1) * p / 2) ** 2 +
         math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))

def add_traffic_attrs(G):
    """Give every directed edge length_km, t0, cap, bg from its road class."""
    for u, v, d in G.edges(data=True):
        cls = d.get("highway", "tertiary")
        if isinstance(cls, list):
            cls = cls[0]
        cls = cls.replace("_link", "")
        cls = "trunk" if cls == "motorway" else cls
        speed, cap, (lo, hi) = ROAD.get(cls, ROAD["tertiary"])
        d["cls"] = cls
        d["t0"] = d["length_km"] / speed * 60
        d["cap"] = cap
        d["bg"] = cap * rng.uniform(lo, hi)
        d["major"] = cls in ("trunk", "primary")
    return G

def schematic_kuching():
    G = nx.DiGraph()
    for name, (lat, lon) in AREAS.items():
        G.add_node(name, y=lat, x=lon, label=name)
    for a, b, cls in CORRIDORS:
        L = haversine_km(AREAS[a], AREAS[b]) * 1.3      # roads aren't straight lines
        for u, v in [(a, b), (b, a)]:
            G.add_edge(u, v, length_km=L, highway=cls, name=f"{a}–{b}")
    place = {n: n for n in AREAS}
    return add_traffic_attrs(G), place

def osm_kuching():
    import osmnx as ox
    print("Downloading Kuching road network from OpenStreetMap ...")
    M = ox.graph_from_place("Kuching, Sarawak, Malaysia", network_type="drive",
                            custom_filter='["highway"~"motorway|trunk|primary|secondary|tertiary"]')
    D = ox.convert.to_digraph(M, weight="length")
    D = D.subgraph(max(nx.strongly_connected_components(D), key=len)).copy()
    G = nx.DiGraph()
    for n, d in D.nodes(data=True):
        G.add_node(n, y=d["y"], x=d["x"])
    for u, v, d in D.edges(data=True):
        name = d.get("name", d.get("highway", "road"))
        if isinstance(name, list):
            name = name[0]
        G.add_edge(u, v, length_km=d["length"] / 1000, highway=d.get("highway", "tertiary"), name=str(name))
    def nearest(lat, lon):
        return min(G.nodes, key=lambda n: haversine_km((lat, lon), (G.nodes[n]["y"], G.nodes[n]["x"])))
    place = {a: nearest(*AREAS[a]) for a in AREAS}
    for a, n in place.items():
        G.nodes[n]["label"] = a
    print(f"  {G.number_of_nodes()} junctions, {G.number_of_edges()} road segments")
    return add_traffic_attrs(G), place

# ---------------------------------------------------------------- core model
def edge_time(d, flow, cap_mult=1.0):
    """BPR congestion function (standard traffic-engineering formula)."""
    return d["t0"] * (1 + 0.15 * (flow / (d["cap"] * cap_mult)) ** 4)

def edges(p):
    return list(zip(p, p[1:]))

def route_stats(G, path, flows, bg_mult=None, cap_mult=None):
    t = dist = delay = 0.0
    for e in edges(path):
        d = G.edges[e]
        bm = bg_mult[e] if bg_mult else 1.0
        cm = cap_mult.get(e, 1.0) if cap_mult else 1.0
        te = edge_time(d, d["bg"] * bm + flows.get(e, 0), cm)
        t += te; dist += d["length_km"]; delay += te - d["t0"]
    return t, dist, delay

def trip_cost(t, dist, delay, late, notified=False):
    fuel = (dist * A["fuel_l_per_km"] + delay * A["idle_l_per_min"]) * A["fuel_rm_per_l"]
    pen = (A["notified_late_rm"] if notified else A["late_penalty_rm"]) if late else 0
    return fuel + t * A["driver_rm_per_min"] + pen, fuel

def flows_of(plan):
    f = {}
    for p in plan.values():
        for e in edges(p):
            f[e] = f.get(e, 0) + 1
    return f

def candidate_routes(G, o, d, k=4, scan=40):
    """Up to k genuinely different routes within the detour cap. On a real map
    many shortest paths differ by one tiny segment, so near-duplicates
    (>70% shared distance with a kept route) are skipped."""
    kept, best_len = [], None
    for p in itertools.islice(nx.shortest_simple_paths(G, o, d, weight="t0"), scan):
        L = sum(G.edges[e]["length_km"] for e in edges(p))
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

def make_vehicles(G, place, n):
    hubs, hw = list(HUBS), np.array(list(HUBS.values()))
    dests, dw = list(DESTS), np.array(list(DESTS.values()), float)
    vs = []
    for i in range(n):
        h = hubs[rng.choice(len(hubs), p=hw / hw.sum())]
        d = dests[rng.choice(len(dests), p=dw / dw.sum())]
        if d == h:
            d = "City Centre"
        o, t = place[h], place[d]
        ff = nx.shortest_path_length(G, o, t, weight="t0")
        vs.append(dict(id=i, hub=h, dest=d, o=o, d=t, deadline=ff * rng.uniform(1.3, 1.8)))
    return vs

def sample_noise(G, S):
    E = list(G.edges)
    return [dict(zip(E, rng.lognormal(0, A["noise_sigma"], len(E)))) for _ in range(S)]

def evaluate(G, vs, plan, scenarios, cap_mult=None, notified=()):
    f = flows_of(plan)
    res = dict(late=0, surprise=0, time=0.0, cost=0.0, fuel=0.0)
    late_m = np.zeros((len(scenarios), len(vs)), bool)
    for s, bm in enumerate(scenarios):
        for j, v in enumerate(vs):
            t, dist, delay = route_stats(G, plan[v["id"]], f, bm, cap_mult)
            late = t > v["deadline"]
            c, fu = trip_cost(t, dist, delay, late, v["id"] in notified)
            late_m[s, j] = late
            res["late"] += late; res["surprise"] += late and v["id"] not in notified
            res["time"] += t; res["cost"] += c; res["fuel"] += fu
    S, N = len(scenarios), len(vs)
    return dict(on_time=100 * (1 - res["late"] / (S * N)), avg_min=res["time"] / (S * N),
                cost_rm=res["cost"] / S, fuel_rm=res["fuel"] / S,
                surprise_late=res["surprise"] / S, late_matrix=late_m)

# ---------------------------------------------------------------- strategies
def naive_plan(G, vs, routes):
    """What a typical navigation app does: best route per vehicle, ignoring
    the other vehicles it is sending at the same moment."""
    best = {}
    plan = {}
    for v in vs:
        key = (v["o"], v["d"])
        if key not in best:
            best[key] = min(routes[key], key=lambda p: route_stats(G, p, {})[0])
        plan[v["id"]] = best[key]
    return plan

def herd_aware_plan(G, vs, routes):
    """Batch assignment: tightest deadlines first; each vehicle takes the
    cheapest route GIVEN the vehicles already assigned in this window."""
    plan, f = {}, {}
    slack = lambda v: v["deadline"] - route_stats(G, routes[(v["o"], v["d"])][0], {})[0]
    for v in sorted(vs, key=slack):
        best, best_c = None, 1e18
        for p in routes[(v["o"], v["d"])]:
            trial = dict(f)
            for e in edges(p):
                trial[e] = trial.get(e, 0) + 1
            t, dist, delay = route_stats(G, p, trial)
            c, _ = trip_cost(t, dist, delay, t > v["deadline"])
            if c < best_c:
                best, best_c = p, c
        plan[v["id"]] = best
        for e in edges(best):
            f[e] = f.get(e, 0) + 1
    return plan

# ---------------------------------------------------------------- early warnings
def p_late(G, v, path, f, samples, cap_mult=None):
    return np.mean([route_stats(G, path, f, bm, cap_mult)[0] > v["deadline"] for bm in samples])

def via(G, path):
    labels = [G.nodes[n].get("label") for n in path[1:-1]]
    labels = [l for l in labels if l]
    return " > ".join(labels) if labels else "alternative road"

def live_advisor(G, vs, base_plan, routes, true_day, cap_mult, thr, n_samp=30):
    """Live check at dispatch. The base plan was built from historical averages;
    now the advisor reads today's live feed (true conditions + sensor error,
    including any closure), re-estimates P(late) per vehicle, and acts:
    reroute if an alternative materially helps, notify the customer if the
    delivery is still likely late."""
    E = list(G.edges)
    obs = np.array([true_day[e] for e in E]) * rng.lognormal(0, 0.10, len(E))
    samples = [dict(zip(E, obs * rng.lognormal(0, 0.10, len(E)))) for _ in range(n_samp)]
    plan = dict(base_plan)
    f = flows_of(plan)
    warned, notified, log = set(), set(), []
    for v in vs:
        cur = plan[v["id"]]
        p = p_late(G, v, cur, f, samples, cap_mult)
        if p < thr:
            continue
        warned.add(v["id"])
        chosen, new_p = None, p
        for alt in routes[(v["o"], v["d"])]:
            if alt == cur:
                continue
            for e in edges(cur): f[e] -= 1
            for e in edges(alt): f[e] = f.get(e, 0) + 1
            pa = p_late(G, v, alt, f, samples, cap_mult)
            for e in edges(alt): f[e] -= 1
            for e in edges(cur): f[e] += 1
            if pa < new_p - 0.05:
                chosen, new_p = alt, pa
        parts = []
        if chosen:
            for e in edges(cur): f[e] -= 1
            for e in edges(chosen): f[e] = f.get(e, 0) + 1
            plan[v["id"]] = cur = chosen
            parts.append(f"Reroute via {via(G, chosen)} (P(late) {p:.0%} -> {new_p:.0%})")
        if new_p >= thr:
            eta = np.percentile([route_stats(G, cur, f, bm, cap_mult)[0] for bm in samples], 80)
            notified.add(v["id"])
            parts.append(f"Notify customer: realistic ETA {eta:.0f} min (promised {v['deadline']:.0f})")
        log.append(dict(vehicle=v["id"], hub=v["hub"], destination=v["dest"],
                        p_late=round(float(p), 2), action="; ".join(parts)))
    return plan, notified, warned, log

def run_days(G, vs, base_plan, routes, days, cap_mult, thr, advisor=True):
    """Average results over held-out days; also warning precision/recall."""
    agg = dict(on_time=0, avg_min=0, cost_rm=0, fuel_rm=0, surprise_late=0)
    tp = fp = fn = 0
    last_log = []
    for day in days:
        if advisor:
            plan, notified, warned, last_log = live_advisor(G, vs, base_plan, routes, day, cap_mult, thr)
            base_late = evaluate(G, vs, base_plan, [day], cap_mult)["late_matrix"][0]
            for j, v in enumerate(vs):
                w = v["id"] in warned
                tp += w and base_late[j]; fp += w and not base_late[j]; fn += (not w) and base_late[j]
        else:
            plan, notified = base_plan, ()
        r = evaluate(G, vs, plan, [day], cap_mult, notified)
        for k in agg:
            agg[k] += r[k] / len(days)
    agg["precision"] = tp / max(tp + fp, 1)
    agg["recall"] = tp / max(tp + fn, 1)
    agg["warnings_per_day"] = (tp + fp) / len(days)
    return agg, last_log

# ---------------------------------------------------------------- charts
def plot_maps(G, plans, fname):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.0))
    cmap = plt.get_cmap("RdYlGn_r")
    for ax, (name, plan) in zip(axes, plans):
        f = flows_of(plan)
        for (u, v), d in G.edges.items():
            if u > v and G.has_edge(v, u):
                continue                                   # draw each road once
            vc = max((d["bg"] + f.get((u, v), 0)) / d["cap"],
                     (G.edges[v, u]["bg"] + f.get((v, u), 0)) / G.edges[v, u]["cap"]) if G.has_edge(v, u) else \
                 (d["bg"] + f.get((u, v), 0)) / d["cap"]
            xs = [G.nodes[u]["x"], G.nodes[v]["x"]]; ys = [G.nodes[u]["y"], G.nodes[v]["y"]]
            ax.plot(xs, ys, color=cmap(min(max((vc - 0.6) / 0.6, 0), 1)),
                    lw=1.5 + 3 * (d["cls"] in ("trunk", "primary")), solid_capstyle="round")
        for n, d in G.nodes(data=True):
            if d.get("label"):
                hub = d["label"] in HUBS
                ax.scatter(d["x"], d["y"], s=60 if hub else 14, c="#222" if hub else "#555", zorder=3,
                           marker="s" if hub else "o")
                ax.annotate(d["label"] + (" (hub)" if hub else ""), (d["x"], d["y"]), fontsize=7,
                            xytext=(3, 3), textcoords="offset points")
        ax.set_title(name, fontsize=11); ax.set_aspect("equal"); ax.axis("off")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0.6, 1.2))
    cb = fig.colorbar(sm, ax=axes, shrink=0.6, label="Road load (volume / capacity)")
    fig.suptitle("Kuching peak window — where the platform's vehicles push roads over capacity", fontsize=11, y=0.98)
    fig.savefig(fname, dpi=150, bbox_inches="tight")

def plot_bars(rows, fname):
    names = [r[0].replace(" + ", "\n+ ") for r in rows]
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.2))
    colors = ["#9aa0a6", "#3b7dd8", "#1a9e6a"]
    for i, (key, title, fmt) in enumerate([("on_time", "On-time deliveries (%)", "{:.0f}%"),
                                            ("avg_min", "Avg trip time (min)", "{:.1f}"),
                                            ("cost_rm", "Cost per 15-min window (RM)", "RM{:,.0f}")]):
        normal = [r[1][key] for r in rows]; inc = [r[2][key] for r in rows]
        x = np.arange(len(rows))
        b1 = ax[i].bar(x - 0.2, normal, 0.4, color=colors, label="Normal peak")
        b2 = ax[i].bar(x + 0.2, inc, 0.4, color=colors, alpha=0.45, hatch="//", label="Surprise road closure")
        for b, val in list(zip(b1, normal)) + list(zip(b2, inc)):
            ax[i].text(b.get_x() + b.get_width() / 2, b.get_height(), fmt.format(val),
                       ha="center", va="bottom", fontsize=8)
        ax[i].set_xticks(x); ax[i].set_xticklabels(names, fontsize=8)
        ax[i].set_title(title); ax[i].spines[["top", "right"]].set_visible(False)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, fontsize=9, frameon=False)
    fig.suptitle(f"Kuching, {A['n_vehicles']} delivery vehicles in one peak window "
                 "(simulated traffic, held-out days)", fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(fname, dpi=150)

# ---------------------------------------------------------------- main
def main():
    use_osm = "--osm" in sys.argv
    G, place = osm_kuching() if use_osm else schematic_kuching()
    vs = make_vehicles(G, place, A["n_vehicles"])
    routes = {}
    for v in vs:
        key = (v["o"], v["d"])
        if key not in routes:
            routes[key] = candidate_routes(G, *key)
    test_scen = sample_noise(G, 30 if use_osm else 200)   # held-out "real" days (fewer on the big real map)

    naive = naive_plan(G, vs, routes)
    herd = herd_aware_plan(G, vs, routes)

    # Surprise closure nobody planned for: the major road the platform relies on most loses 60% capacity
    use = {}
    for p in (naive, herd):
        for e, n in flows_of(p).items():
            use[e] = use.get(e, 0) + n
    closed = max((e for e in use if G.edges[e]["major"]), key=use.get)
    incident = {closed: 0.4}
    thr = A["warn_threshold"]

    print("Map:", "OpenStreetMap (real roads)" if use_osm else "approximate corridor model")
    print("ASSUMPTIONS:", A)
    print("Surprise closure on:", G.edges[closed]["name"], f"({len(test_scen)} held-out days each)\n")
    configs = [("Typical app (naive)", naive, False),
               ("Herd-aware batch", herd, False),
               ("Herd-aware + live early warnings", herd, True)]
    rows, logs = [], {}
    for name, plan, adv in configs:
        r, _ = run_days(G, vs, plan, routes, test_scen, None, thr, adv)
        ri, log_i = run_days(G, vs, plan, routes, test_scen, incident, thr, adv)
        rows.append((name, r, ri))
        if adv:
            logs = log_i
            r_adv, ri_adv = r, ri
        print(f"{name:33s} on-time {r['on_time']:5.1f}% | avg {r['avg_min']:5.1f} min | "
              f"cost RM{r['cost_rm']:7,.0f} (fuel RM{r['fuel_rm']:5,.0f}) | "
              f"unannounced late {r['surprise_late']:5.1f}")
        print(f"{'   ...with surprise closure':33s} on-time {ri['on_time']:5.1f}% | avg {ri['avg_min']:5.1f} min | "
              f"cost RM{ri['cost_rm']:7,.0f} (fuel RM{ri['fuel_rm']:5,.0f}) | "
              f"unannounced late {ri['surprise_late']:5.1f}")

    print("\nWarning quality (live advisor, held-out days):")
    print(f"  normal peak : {r_adv['warnings_per_day']:5.1f} warnings/day, precision {r_adv['precision']:.0%}, recall {r_adv['recall']:.0%}")
    print(f"  closure day : {ri_adv['warnings_per_day']:5.1f} warnings/day, precision {ri_adv['precision']:.0%}, recall {ri_adv['recall']:.0%}")
    print("\nFalse-alarm trade-off (normal peak, up to 100 days):")
    print(" threshold | warnings/day | precision | recall")
    for t in (0.3, 0.5, 0.7):
        q, _ = run_days(G, vs, herd, routes, test_scen[:100], None, t, True)
        print(f"   {t:.1f}     |    {q['warnings_per_day']:6.1f}    |  {q['precision']:6.0%}   | {q['recall']:6.0%}")

    warns = sorted(logs, key=lambda x: -x["p_late"])
    with open("kuching_warnings.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["vehicle", "hub", "destination", "p_late", "action"])
        w.writeheader(); w.writerows(warns)
    print(f"\nSample closure day: {len(warns)} early warnings -> kuching_warnings.csv")
    for x in warns[:6]:
        print(f"  #{x['vehicle']:3d} {x['hub']:>12s} -> {x['destination']:<12s} P(late) {x['p_late']:.2f}  {x['action']}")

    plot_bars(rows, "kuching_results.png")
    plot_maps(G, [("Typical app: everyone takes the 'best' road", naive),
                  ("Herd-aware: vehicles split across routes", herd)],
              "kuching_map.png")
    print("charts: kuching_results.png, kuching_map.png")

if __name__ == "__main__":
    main()
