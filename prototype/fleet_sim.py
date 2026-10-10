"""
Herd-aware fleet dispatch advisor — one-day prototype.

Predict early: which deliveries will be late, given traffic AND where our
own vans are already being sent.
Decide better: split vans across routes (with a detour cap), then for each
at-risk delivery recommend a reroute or an honest customer ETA.

Everything is simulated. Assumptions are listed in ASSUMPTIONS and printed.
"""
import itertools, random, csv
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 7
rng = np.random.default_rng(SEED)
random.seed(SEED)

ASSUMPTIONS = dict(
    n_vans=150,              # vans in one dispatch wave (15-min window)
    fuel_l_per_km=0.12,      # light van, moving
    idle_l_per_min=0.02,     # fuel burned per minute of congestion delay
    fuel_rm_per_l=2.15,      # diesel price assumption
    driver_rm_per_min=0.25,  # ~RM15/hour
    late_penalty_rm=20.0,    # refund/voucher + reputational cost per late drop
    notified_late_rm=5.0,    # same late drop, but customer was warned early
    detour_cap=1.20,         # never suggest a route >20% longer than shortest
    noise_sigma=0.25,        # day-to-day uncertainty in background traffic
    warn_threshold=0.5,      # warn when P(late) >= this
)
A = ASSUMPTIONS

# ---------------------------------------------------------------- network
def build_network(n=6):
    G = nx.DiGraph()
    arterial_rows = {1, 4}
    for r, c in itertools.product(range(n), range(n)):
        for dr, dc in [(0, 1), (1, 0)]:
            r2, c2 = r + dr, c + dc
            if r2 >= n or c2 >= n:
                continue
            art = dr == 0 and r in arterial_rows
            length = rng.uniform(1.2, 1.8)
            speed = 60 if art else 35          # km/h
            cap = 120 if art else 50           # vehicles per 15 min
            t0 = length / speed * 60           # minutes
            bg = cap * (rng.uniform(0.55, 0.8) if art else rng.uniform(0.3, 0.6))
            for u, v in [((r, c), (r2, c2)), ((r2, c2), (r, c))]:
                G.add_edge(u, v, length=length, t0=t0, cap=cap, bg=bg, art=art)
    return G

def edge_time(d, flow, cap_mult=1.0):
    """BPR congestion function (standard traffic-engineering formula)."""
    return d["t0"] * (1 + 0.15 * (flow / (d["cap"] * cap_mult)) ** 4)

# ---------------------------------------------------------------- demand
def make_vans(G, n):
    vans = []
    for i in range(n):
        o = (2, 0) if rng.random() < 0.7 else (3, 0) # two hubs on the west side
        dst = (int(rng.integers(2, 6)), int(rng.integers(4, 6)))  # customers in the east district
        ff = nx.shortest_path_length(G, o, dst, weight="t0")
        vans.append(dict(id=i, o=o, d=dst,
                         deadline=ff * rng.uniform(1.4, 2.0)))
    return vans

def candidate_routes(G, o, d, k=6):
    paths = list(itertools.islice(nx.shortest_simple_paths(G, o, d, weight="t0"), k))
    lens = [sum(G[u][v]["length"] for u, v in zip(p, p[1:])) for p in paths]
    best = min(lens)
    return [p for p, L in zip(paths, lens) if L <= best * A["detour_cap"]]

def edges(p):
    return list(zip(p, p[1:]))

# ---------------------------------------------------------------- evaluation
def route_stats(G, path, flows, bg_mult=None, cap_mult=None):
    t = dist = delay = 0.0
    for e in edges(path):
        d = G[e[0]][e[1]]
        bm = bg_mult[e] if bg_mult else 1.0
        cm = cap_mult.get(e, 1.0) if cap_mult else 1.0
        te = edge_time(d, d["bg"] * bm + flows.get(e, 0), cm)
        t += te; dist += d["length"]; delay += te - d["t0"]
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

def sample_noise(G, S):
    return [{e: float(rng.lognormal(0, A["noise_sigma"])) for e in G.edges} for _ in range(S)]

def evaluate(G, vans, plan, scenarios, cap_mult=None, notified=()):
    f = flows_of(plan)
    on_time, times, costs, fuels, surprise = [], [], [], [], []
    late_matrix = np.zeros((len(scenarios), len(vans)), dtype=bool)
    for s, bm in enumerate(scenarios):
        for j, v in enumerate(vans):
            t, dist, delay = route_stats(G, plan[v["id"]], f, bm, cap_mult)
            late = t > v["deadline"]
            c, fu = trip_cost(t, dist, delay, late, v["id"] in notified)
            late_matrix[s, j] = late
            surprise.append(late and v["id"] not in notified)
            on_time.append(not late); times.append(t); costs.append(c); fuels.append(fu)
    S = len(scenarios)
    return dict(on_time=100 * np.mean(on_time), avg_min=np.mean(times),
                cost_rm=np.sum(costs) / S, fuel_rm=np.sum(fuels) / S,
                surprise_late=np.sum(surprise) / S,
                late_matrix=late_matrix)

# ---------------------------------------------------------------- strategies
def naive_plan(G, vans, routes):
    """What a typical navigation app does: best route for each van on its own,
    ignoring the other vans it is sending at the same moment."""
    plan = {}
    for v in vans:
        plan[v["id"]] = min(routes[v["id"]], key=lambda p: route_stats(G, p, {})[0])
    return plan

def herd_aware_plan(G, vans, routes):
    """Batch assignment: tightest deadlines first; each van gets the cheapest
    route GIVEN the vans already assigned in this wave. Detour cap enforced by
    candidate_routes()."""
    plan, f = {}, {}
    order = sorted(vans, key=lambda v: v["deadline"] - route_stats(G, routes[v["id"]][0], {})[0])
    for v in order:
        best, best_c = None, 1e18
        for p in routes[v["id"]]:
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
def p_late(G, v, path, f, samples):
    return np.mean([route_stats(G, path, f, bm)[0] > v["deadline"] for bm in samples])

def eta_p80(G, path, f, samples):
    return np.percentile([route_stats(G, path, f, bm)[0] for bm in samples], 80)

def warnings_and_actions(G, vans, plan, routes, samples, thr):
    """Predict P(late) for each van; for at-risk vans pick an action."""
    plan = dict(plan)
    out = []
    for v in vans:
        f = flows_of(plan)
        p = p_late(G, v, plan[v["id"]], f, samples)
        if p < thr:
            continue
        action, new_p = None, p
        for alt in routes[v["id"]]:
            if alt == plan[v["id"]]:
                continue
            f2 = dict(f)
            for e in edges(plan[v["id"]]):
                f2[e] -= 1
            for e in edges(alt):
                f2[e] = f2.get(e, 0) + 1
            pa = p_late(G, v, alt, f2, samples)
            if pa < thr and pa < new_p:
                action, new_p, chosen = "reroute", pa, alt
        if action == "reroute":
            plan[v["id"]] = chosen
            msg = f"Reroute: P(late) {p:.0%} -> {new_p:.0%}"
        else:
            eta = eta_p80(G, plan[v["id"]], f, samples)
            msg = f"Notify customer now: realistic ETA {eta:.0f} min (deadline {v['deadline']:.0f})"
        out.append(dict(van=v["id"], p_late=round(p, 2), action=msg))
    return plan, out

def warning_quality(G, vans, plan, plan_samples, test_scen, thr):
    f = flows_of(plan)
    probs = np.array([p_late(G, v, plan[v["id"]], f, plan_samples) for v in vans])
    warned = probs >= thr
    actual = evaluate(G, vans, plan, test_scen)["late_matrix"]   # S x N
    tp = (actual & warned).sum(); fp = (~actual & warned).sum(); fn = (actual & ~warned).sum()
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    return warned.sum(), prec, rec

# ---------------------------------------------------------------- main
def main():
    G = build_network()
    vans = make_vans(G, A["n_vans"])
    routes = {v["id"]: candidate_routes(G, v["o"], v["d"]) for v in vans}
    plan_samples = sample_noise(G, 150)   # what the planner "imagines"
    test_scen = sample_noise(G, 300)      # held-out "real days"

    plans = {"Typical app (naive)": naive_plan(G, vans, routes),
             "Herd-aware batch": herd_aware_plan(G, vans, routes)}
    hp, warns = warnings_and_actions(G, vans, plans["Herd-aware batch"], routes,
                                     plan_samples, A["warn_threshold"])
    plans["Herd-aware + early warnings"] = hp
    notified = {w["van"] for w in warns if w["action"].startswith("Notify")}

    # incident nobody predicted: the arterial link our vans rely on most loses 60% capacity
    use = {}
    for p in list(plans.values())[:2]:
        for e, n in flows_of(p).items():
            use[e] = use.get(e, 0) + n
    busiest = max((e for e in use if G.edges[e]["art"]), key=use.get)
    incident = {busiest: 0.4}
    print("Surprise incident on link", busiest)

    print("ASSUMPTIONS:", A, "\n")
    rows = []
    for name, plan in plans.items():
        nt = notified if "warnings" in name else ()
        r = evaluate(G, vans, plan, test_scen, notified=nt)
        ri = evaluate(G, vans, plan, test_scen, incident, notified=nt)
        rows.append((name, r, ri))
        print(f"{name:30s} on-time {r['on_time']:5.1f}% | avg {r['avg_min']:5.1f} min | "
              f"cost RM{r['cost_rm']:7.0f} (fuel RM{r['fuel_rm']:5.0f}) | unannounced late {r['surprise_late']:5.1f} || "
              f"INCIDENT on-time {ri['on_time']:5.1f}% cost RM{ri['cost_rm']:7.0f}")

    print("\nFalse-alarm check (herd-aware plan, held-out days):")
    print(" threshold | warnings | precision | recall")
    for thr in (0.3, 0.5, 0.7):
        n, p, rc = warning_quality(G, vans, plans["Herd-aware batch"], plan_samples, test_scen, thr)
        print(f"   {thr:.1f}     |  {n:5d}   |  {p:6.1%}   | {rc:6.1%}")

    with open("warnings.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["van", "p_late", "action"])
        w.writeheader(); w.writerows(sorted(warns, key=lambda x: -x["p_late"]))
    print(f"\n{len(warns)} early warnings written to warnings.csv")
    for x in sorted(warns, key=lambda x: -x["p_late"])[:5]:
        print("  van", x["van"], x["p_late"], x["action"])

    # chart
    names = [r[0].replace(" + ", "\n+ ") for r in rows]
    fig, ax = plt.subplots(1, 3, figsize=(13, 4.2))
    colors = ["#9aa0a6", "#3b7dd8", "#1a9e6a"]
    for i, (key, title, fmt) in enumerate([("on_time", "On-time deliveries (%)", "{:.0f}%"),
                                            ("avg_min", "Avg trip time (min)", "{:.1f}"),
                                            ("cost_rm", "Cost per wave (RM)", "RM{:.0f}")]):
        normal = [r[1][key] for r in rows]; inc = [r[2][key] for r in rows]
        x = np.arange(len(rows))
        b1 = ax[i].bar(x - 0.2, normal, 0.4, color=colors, label="Normal day")
        b2 = ax[i].bar(x + 0.2, inc, 0.4, color=colors, alpha=0.45, hatch="//", label="Surprise incident")
        for b, val in list(zip(b1, normal)) + list(zip(b2, inc)):
            ax[i].text(b.get_x() + b.get_width() / 2, b.get_height(), fmt.format(val),
                       ha="center", va="bottom", fontsize=8)
        ax[i].set_xticks(x); ax[i].set_xticklabels(names, fontsize=8)
        ax[i].set_title(title); ax[i].spines[["top", "right"]].set_visible(False)
    ax[0].legend(fontsize=8, loc="upper left")
    fig.suptitle(f"{A['n_vans']} vans, one dispatch wave — solid: normal day, hatched: unpredicted lane closure",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig("results.png", dpi=150)
    print("chart saved: results.png")

if __name__ == "__main__":
    main()
