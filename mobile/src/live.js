// Live traffic from TomTom's Traffic Flow API: current vs normal (free-flow) speed on a road.
// We sample each road of our map near its middle. Results are cached for 5 minutes.
import { ROADS, NODES } from "./engine";
import { TOMTOM_KEY } from "./config";

const cache = {};
const url = (pt, key) => `https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point=${pt[0].toFixed(5)},${pt[1].toFixed(5)}&unit=KMPH&key=${key}`;
const mid = c => { const r = ROADS[c], a = NODES[r.a], b = NODES[r.b]; return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; };
const wait = ms => new Promise(r => setTimeout(r, ms));

async function one(pt, key) {
  const res = await fetch(url(pt, key));
  if (!res.ok) { const e = new Error(res.status === 403 ? "key refused (check the key and its allowed websites)" : res.status === 429 ? "too many requests, try again in a minute" : `TomTom error ${res.status}`); e.status = res.status; throw e; }
  const j = (await res.json()).flowSegmentData;
  if (!j) throw new Error("no traffic data for this spot");
  const cur = Math.max(3, j.currentSpeed), free = Math.max(5, j.freeFlowSpeed);
  return { ratio: Math.max(.85, Math.min(4, free / cur)), cur: j.currentSpeed, free: j.freeFlowSpeed, closed: !!j.roadClosure, conf: j.confidence };
}

// corridors: array of road indexes. Returns { data: {c: {...}|null}, ok, failed, error }
export async function liveFor(corridors, key = TOMTOM_KEY) {
  const data = {}; let ok = 0, failed = 0, error = null; const now = Date.now();
  const todo = [];
  for (const c of corridors) { const h = cache[c]; if (h && now - h.t < 5 * 60e3) { data[c] = h.d; ok++; } else todo.push(c); }
  for (let i = 0; i < todo.length; i += 4) {                 // TomTom free tier: max 5 calls a second
    await Promise.all(todo.slice(i, i + 4).map(async c => {
      try { const d = await one(mid(c), key); cache[c] = { t: Date.now(), d }; data[c] = d; ok++; }
      catch (e) { data[c] = null; failed++; error = error || e.message; }
    }));
    if (i + 4 < todo.length) await wait(900);
    if (error && ok === 0 && failed >= 2) break;               // key or network problem: stop early
  }
  return { data, ok, failed, error };
}

// One call near the city centre, for the Settings "Test live traffic" button.
export async function testLive(key = TOMTOM_KEY) {
  try { const d = await one(NODES["City Centre"], key); return { ok: true, ...d }; }
  catch (e) { return { ok: false, error: e.message || String(e) }; }
}
