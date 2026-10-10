// Kuching Trip Advisor engine (JavaScript port of kuching_advisor.py, approximate map).
// Traffic is MADE UP: road type, time of day, school hours, people driving in from
// outside Kuching, and 400 delivery vans leaving depots at 07:00. Volumes are assumptions.

export const AREAS = {
  "City Centre": [1.5580, 110.3450], "Padungan": [1.5565, 110.3570], "Pending": [1.5550, 110.3850],
  "Bintawa": [1.5680, 110.3720], "Kenyalang": [1.5450, 110.3620], "Simpang Tiga": [1.5350, 110.3550],
  "Stutong": [1.5200, 110.3750], "Tabuan Jaya": [1.5300, 110.3900], "Hui Sing": [1.5230, 110.3600],
  "Batu Lintang": [1.5400, 110.3450], "Satok": [1.5520, 110.3350], "Petra Jaya": [1.5750, 110.3300],
  "Batu Kawa": [1.5150, 110.3000], "Matang": [1.5500, 110.2850], "Airport": [1.4870, 110.3450],
  "Kota Sentosa": [1.4700, 110.3300],
};
const ROAD = { trunk: [70, 900, .85, 1.0], primary: [50, 700, .85, 1.0], secondary: [40, 450, .70, .90], tertiary: [30, 250, .40, .60] };
const CORR = [["City Centre", "Padungan", "primary"], ["Padungan", "Pending", "primary"], ["Padungan", "Kenyalang", "secondary"], ["Pending", "Bintawa", "secondary"], ["Pending", "Tabuan Jaya", "secondary"], ["Kenyalang", "Simpang Tiga", "primary"], ["City Centre", "Batu Lintang", "secondary"], ["City Centre", "Satok", "primary"], ["Satok", "Petra Jaya", "primary"], ["Satok", "Batu Kawa", "primary"], ["Satok", "Batu Lintang", "secondary"], ["Batu Lintang", "Simpang Tiga", "secondary"], ["Batu Lintang", "Airport", "primary"], ["Simpang Tiga", "Hui Sing", "secondary"], ["Simpang Tiga", "Stutong", "primary"], ["Stutong", "Tabuan Jaya", "primary"], ["Stutong", "Hui Sing", "tertiary"], ["Hui Sing", "Airport", "secondary"], ["Airport", "Kota Sentosa", "trunk"], ["Batu Kawa", "Kota Sentosa", "secondary"], ["Batu Kawa", "Matang", "secondary"], ["Matang", "Petra Jaya", "secondary"], ["Kota Sentosa", "Stutong", "trunk"], ["Bintawa", "Petra Jaya", "tertiary"], ["Pending", "Kenyalang", "tertiary"], ["Kenyalang", "Batu Lintang", "tertiary"], ["Padungan", "Batu Lintang", "tertiary"], ["Tabuan Jaya", "Kenyalang", "tertiary"], ["Hui Sing", "Batu Lintang", "tertiary"], ["Airport", "Batu Kawa", "tertiary"]];
// schools per area from data/kuching_schools_sessions.csv (38 schools; morning/afternoon not confirmed)
const SCHOOLS = { "City Centre": 8, "Padungan": 2, "Pending": 1, "Bintawa": 1, "Batu Lintang": 3, "Kenyalang": 2, "Simpang Tiga": 1, "Tabuan Jaya": 2, "Stutong": 3, "Satok": 1, "Petra Jaya": 4, "Matang": 3, "Batu Kawa": 4, "Airport": 2, "Kota Sentosa": 1 };
const WINDOWS = { morning: [[405, 450], [795, 840]], both: [[405, 450], [765, 840], [1095, 1140]] };
// areas around Kuching: [lat, lon, morning-peak cars per 15 min heading into town (ASSUMED), entry roads]
export const EXT = {
  "Samarahan": [1.4600, 110.4930, 600, [["Stutong", "trunk", 900], ["Tabuan Jaya", "primary", 500]]],
  "Siburan": [1.4050, 110.3600, 450, [["Kota Sentosa", "trunk", 900]]],
  "Matang outer": [1.5550, 110.2450, 250, [["Matang", "secondary", 450]]],
  "Samariang": [1.5950, 110.3050, 200, [["Petra Jaya", "secondary", 450]]],
  "Sejingkat": [1.5950, 110.4100, 120, [["Bintawa", "secondary", 450]]],
};
const JOBS = { "City Centre": 3, "Padungan": 2, "Satok": 2, "Petra Jaya": 3, "Pending": 2, "Batu Lintang": 1, "Simpang Tiga": 1, "Kenyalang": 1, "Stutong": 1, "Tabuan Jaya": 1, "Hui Sing": 1, "Airport": 1, "Bintawa": 1 };
export const DEPOTS = [["Pending", .65], ["Kota Sentosa", .35]];
const DESTS = { "City Centre": 2, "Padungan": 2, "Kenyalang": 2, "Simpang Tiga": 2, "Stutong": 3, "Tabuan Jaya": 3, "Hui Sing": 3, "Batu Lintang": 2, "Satok": 2, "Petra Jaya": 3, "Batu Kawa": 4, "Matang": 2 };
const P = { a: .15, b: 4, detour: 1.25, minKm: .3, minShare: .10, sigma: .25, schoolBoost: .35, vans: 400, waveStart: 420, waveMin: 15, bin: 5, mc: 240 };

export const NODES = { ...AREAS };
for (const z in EXT) NODES[z] = [EXT[z][0], EXT[z][1]];
const ALLCORR = CORR.slice();
for (const z in EXT) for (const [a, cls, cap] of EXT[z][3]) ALLCORR.push([z, a, cls, cap]);
export const ROADS = ALLCORR.map(([a, b, cls]) => ({ a, b, cls }));

export const hm = m => { m = Math.round(m); m = ((m % 1440) + 1440) % 1440; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); };
export function hav(a, b) { const p = Math.PI / 180, h = Math.sin((b[0] - a[0]) * p / 2) ** 2 + Math.cos(a[0] * p) * Math.cos(b[0] * p) * Math.sin((b[1] - a[1]) * p / 2) ** 2; return 2 * 6371 * Math.asin(Math.sqrt(h)); }
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function gauss(r) { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function hashStr(s) { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
export function nearest(ll) { let best = null, bd = Infinity; for (const n in NODES) { const d = hav(ll, NODES[n]); if (d < bd) { bd = d; best = n; } } return { name: best, km: bd }; }

// ---- network
const E = []; const OUT = {}; Object.keys(NODES).forEach(n => (OUT[n] = []));
ALLCORR.forEach(([a, b, cls, gcap], i) => {
  const L = hav(NODES[a], NODES[b]) * 1.3, [spd, ccap, lo, hi] = ROAD[cls], cap = gcap || ccap, gate = !!gcap;
  const nS = (SCHOOLS[a] || 0) + (SCHOOLS[b] || 0);
  const local = !gate && (cls === "secondary" || cls === "tertiary") && nS > 0;
  const vcPeak = gate ? .3 : lo + (hi - lo) * ((hashStr(a + b) % 100) / 100);
  [[a, b], [b, a]].forEach(([u, v]) => { const e = { id: E.length, c: i, u, v, cls, L, t0: L / spd * 60, cap, vcPeak, local, nS, boost: local ? P.schoolBoost * Math.min(1, nS / 2) : 0, name: a + "–" + b }; E.push(e); OUT[u].push(e); });
});
function profile(m, day) { const g = (mu, s) => Math.exp(-.5 * ((m - mu) / s) ** 2); const k = day === "holiday" ? .8 : 1; return .3 + .7 * Math.max(k * g(450, 35), .75 * k * g(765, 40), g(1065, 45)); }
const tide = (m, pk, sd) => .15 + .85 * Math.exp(-.5 * ((m - pk) / sd) ** 2);

function makeCtx(opts) {
  const S = { day: opts.day || "term", sess: opts.sess || "morning", commOn: opts.commOn !== false, vansOn: opts.vansOn !== false, closed: new Set(opts.closed || []), slow: new Set(opts.slow || []) };
  S.schoolOn = (e, m) => S.day === "term" && e.local && WINDOWS[S.sess].some(([a, b]) => m >= a && m < b);
  S.vcAt = (e, m) => {
    let vc = e.vcPeak * profile(m, S.day) * (S.comm ? .8 : 1);
    if (S.comm) { const k = S.day === "holiday" ? .85 : 1; vc += k * ((S.comm.in[e.id] || 0) * tide(m, 440, 45) + (S.comm.out[e.id] || 0) * tide(m, 1065, 50)) / e.cap; }
    if (S.slow.has(e.c)) vc += .5;
    if (S.schoolOn(e, m)) vc += e.boost;
    if (S.herd) { const b = Math.floor(m / P.bin); vc += (S.herd[e.id]?.[b] || 0) * (15 / P.bin) / e.cap; }
    return vc;
  };
  S.edgeTime = (e, m) => S.closed.has(e.c) ? Infinity : e.t0 * (1 + P.a * S.vcAt(e, m) ** P.b);
  S.travel = (path, dep, noise) => { let t = dep; for (const e of path) t += S.edgeTime(e, t) * (noise ? noise[e.id] : 1); return t - dep; };
  return S;
}
function dijkstra(o, d, w) {
  const dist = {}, prev = {}, seen = new Set(); Object.keys(NODES).forEach(n => (dist[n] = Infinity)); dist[o] = 0;
  for (;;) {
    let u = null, b = Infinity; for (const n in dist) if (!seen.has(n) && dist[n] < b) { b = dist[n]; u = n; }
    if (u === null || u === d) break; seen.add(u);
    for (const e of OUT[u]) { const c = w(e); if (!isFinite(c)) continue; if (dist[u] + c < dist[e.v]) { dist[e.v] = dist[u] + c; prev[e.v] = e; } }
  }
  if (!isFinite(dist[d])) return null; const p = []; let n = d; while (n !== o) { p.unshift(prev[n]); n = prev[n].u; } return p;
}
const plen = p => p.reduce((s, e) => s + e.L, 0);
function distinct(p, kept) { const L = plen(p); return kept.every(q => { const ids = new Set(q.map(e => e.c)); const own = p.filter(e => !ids.has(e.c)).reduce((s, e) => s + e.L, 0); return own >= Math.max(P.minKm, P.minShare * L); }); }
function routes(S, o, d, k = 3) {
  const pen = {}, kept = []; let best = null;
  for (let i = 0; i < 25 && kept.length < k; i++) {
    const p = dijkstra(o, d, e => S.closed.has(e.c) ? Infinity : e.t0 * (pen[e.id] || 1)); if (!p) break;
    const L = plen(p); best = best ?? L; const key = p.map(e => e.id).join(",");
    if (L <= best * P.detour && !kept.some(q => q.map(e => e.id).join(",") === key) && (!kept.length || distinct(p, kept))) kept.push(p);
    p.forEach(e => (pen[e.id] = (pen[e.id] || 1) * 1.5));
  }
  return kept;
}
function buildCommuters(S) {
  if (!S.commOn) return null; const C = { in: {}, out: {}, zin: {} }; const jw = Object.values(JOBS).reduce((a, b) => a + b, 0);
  for (const dir of ["in", "out"]) {
    const F = C[dir]; const w = e => { if (S.closed.has(e.c)) return Infinity; const vc = e.vcPeak * .8 + (F[e.id] || 0) / e.cap; return e.t0 * (1 + P.a * vc ** P.b); };
    for (let k = 0; k < 4; k++) for (const z in EXT) {
      const q = EXT[z][2] / 4;
      for (const j in JOBS) {
        const p = dir === "in" ? dijkstra(z, j, w) : dijkstra(j, z, w); if (!p) continue;
        for (const e of p) { F[e.id] = (F[e.id] || 0) + q * JOBS[j] / jw; if (dir === "in") { (C.zin[e.id] ??= {})[z] = (C.zin[e.id][z] || 0) + q * JOBS[j] / jw; } }
      }
    }
  }
  return C;
}
function buildVans(S) {
  const herd = {}; if (!S.vansOn) return herd; S.herd = herd;
  const r = rng(7 + (S.day === "term" ? 0 : 100)); const dests = Object.entries(DESTS), tot = dests.reduce((s, [, w]) => s + w, 0); const trips = [];
  for (let i = 0; i < P.vans; i++) { const hub = r() < DEPOTS[0][1] ? DEPOTS[0][0] : DEPOTS[1][0]; let x = r() * tot, dst = dests[0][0]; for (const [n, w] of dests) { if ((x -= w) < 0) { dst = n; break; } } if (dst !== hub) trips.push({ hub, dst, dep: P.waveStart + r() * P.waveMin }); }
  trips.sort((a, b) => a.dep - b.dep); const cache = {};
  for (const t of trips) {
    const rs = cache[t.hub + t.dst] ??= routes(S, t.hub, t.dst); if (!rs.length) continue;
    let best = null, bt = Infinity; for (const p of rs) { const x = S.travel(p, t.dep); if (x < bt) { bt = x; best = p; } }
    let m = t.dep; for (const e of best) { const b = Math.floor(m / P.bin); (herd[e.id] ??= {})[b] = (herd[e.id][b] || 0) + 1; m += S.edgeTime(e, m); }
  }
  return herd;
}
function topZone(S, e) { const z = S.comm?.zin[e.id]; if (!z) return null; let best = null, bv = 0; for (const k in z) if (z[k] > bv) { bv = z[k]; best = k; } return best; }

// cache the expensive background (commuters + vans) per settings
const bgCache = {};
function context(opts) {
  const S = makeCtx(opts);
  const key = [S.day, S.sess, S.commOn, S.vansOn, [...S.closed].sort(), [...S.slow].sort()].join("|");
  if (!bgCache[key]) { S.herd = null; S.comm = buildCommuters(S); S.herd = buildVans(S); bgCache[key] = { comm: S.comm, herd: S.herd }; }
  S.comm = bgCache[key].comm; S.herd = bgCache[key].herd; return S;
}

/** Advice for one trip. opts: {from, to (node names), arriveBy (minutes), conf (0.8|0.9|0.95), day, sess, commOn, vansOn, closed, slow} */
export function advise(opts) {
  const S = context(opts); const o = opts.from, d = opts.to;
  if (o === d) return { err: `Start and destination are both in ${o}. For a trip this short, just go.` };
  const rs = routes(S, o, d); if (!rs.length) return { err: "No way through with the reported closures. Clear a report and try again." };
  const arr = opts.arriveBy, conf = opts.conf || .9, r = rng(hashStr([o, d, arr, S.day, S.sess, S.commOn, S.vansOn].join("|")));
  const noises = Array.from({ length: P.mc }, () => { const common = Math.exp(.6 * P.sigma * gauss(r)), n = {}; for (const e of E) n[e.id] = common * Math.exp(.8 * P.sigma * gauss(r)); return n; });
  const out = rs.map(p => {
    const free = p.reduce((s, e) => s + e.t0, 0), deps = [];
    for (let dep = arr - Math.ceil(free * 3 / 5) * 5 - 30; dep <= arr - 2; dep += 1) { const ts = noises.map(n => S.travel(p, dep, n)).sort((a, b) => a - b); deps.push({ dep, pl: ts.filter(t => dep + t > arr).length / ts.length, ts }); }
    let pick = null; for (const x of deps) if (x.pl <= 1 - conf) pick = x; const ok = !!pick; if (!pick) pick = deps[0];
    const q = f => pick.dep + pick.ts[Math.min(pick.ts.length - 1, Math.floor(f * pick.ts.length))];
    let m = pick.dep; const schools = [], busy = [];
    for (const e of p) { if (S.schoolOn(e, m)) schools.push({ road: e.name, at: m, n: e.nS, c: e.c }); const b = Math.floor(m / P.bin); let h = 0; for (let k = b - 3; k <= b + 3; k++) h += S.herd[e.id]?.[k] || 0; const vc = S.vcAt(e, m); const share = S.comm ? ((S.comm.in[e.id] || 0) * tide(m, 440, 45) + (S.comm.out[e.id] || 0) * tide(m, 1065, 50)) / e.cap / vc : 0; busy.push({ road: e.name, c: e.c, at: m, vc, vans: h, outsideShare: share, outsideFrom: topZone(S, e), reportedJam: S.slow.has(e.c) }); m += S.edgeTime(e, m); }
    return { via: p.slice(0, -1).map(e => e.v), roads: p.map(e => e.c), km: plen(p), leave: pick.dep, ok, pLate: pick.pl, lo: q(.1), mid: q(.5), hi: q(.9), typical: pick.ts[Math.floor(pick.ts.length / 2)], schools, busy, vans: Math.max(0, ...busy.map(b => b.vans)) };
  });
  const okR = out.filter(x => x.ok); const pool = (okR.length ? okR : out).slice();
  pool.sort((a, b) => b.leave - a.leave || a.schools.length - b.schools.length || a.pLate - b.pLate);
  // only send people a different way when it is worth it: 3+ minutes later departure, or clearly safer
  const fastest = out[0]; let best = pool[0], keptUsual = false;
  if (best !== fastest && fastest.ok && best.leave - fastest.leave < 3 && fastest.pLate - best.pLate < .05) { best = fastest; keptUsual = true; }
  // the road Google Maps would pick on a normal day (it doesn't know our reports or the planned trips)
  const usual = dijkstra(o, d, e => e.t0); const usualVia = usual ? usual.slice(0, -1).map(e => e.v) : [];
  const sameAsUsual = usual && usual.length === best.roads.length && usual.every((e, i) => e.c === best.roads[i]);
  return { routes: out, best, fastest, keptUsual, usualVia, sameAsUsual, gain: best === fastest ? 0 : best.leave - fastest.leave, from: o, to: d, arriveBy: arr, conf };
}

/** Google Maps link. A stop is added only when we send people away from the usual fastest road. */
export function mapsLink(res, fromLL, toLL, fromHere) {
  const ll = a => a.map(v => v.toFixed(5)).join(",");
  const o = fromLL || NODES[res.from], d = toLL || NODES[res.to];
  const usualNodes = new Set(res.usualVia);
  const wp = res.sameAsUsual ? null : (res.best.via.find(n => !usualNodes.has(n)) || null);
  const plain = "https://www.google.com/maps/dir/?api=1" + (fromHere ? "" : "&origin=" + encodeURIComponent(ll(o))) + "&destination=" + encodeURIComponent(ll(d)) + "&travelmode=driving";
  return { url: wp ? plain + "&waypoints=" + encodeURIComponent(ll(NODES[wp])) : plain, plain, stop: wp };
}

export function message(res, fromLabel, toLabel) {
  const b = res.best; const slow = [...new Set(b.busy.filter(x => x.vc > .85).map(x => x.road))];
  let m = `Leave ${fromLabel ? fromLabel + " " : ""}by ${hm(b.leave)} to reach ${toLabel} by ${hm(res.arriveBy)}.`;
  m += `\nGo via ${b.via.length ? b.via.join(", ") : "the direct road"}.`;
  if (b.schools.length) m += `\nSchool traffic near ${[...new Set(b.schools.map(s => s.road))].join(", ")}.`;
  if (slow.length) m += `\nSlow: ${slow.join(", ")}.`;
  m += `\nYou should arrive around ${hm(b.mid)}. Chance of being late: about ${Math.round(b.pLate * 100)}%.`;
  return m;
}
