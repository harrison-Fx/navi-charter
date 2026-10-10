// Find a place by name.
// 1) Offline: Kuching areas plus well-known landmarks. Landmark positions are APPROXIMATE
//    (about ±1 km); the advice only needs the nearest area, and the user can drag the pin.
// 2) Online (optional): OpenStreetMap's Nominatim search, limited to Greater Kuching.
import { AREAS, EXT, NODES, nearest, hav } from "./engine";

// [name, lat, lon, extra words people might type]
export const LANDMARKS = [
  ["Kuching Waterfront", 1.5585, 110.3455, "riverside esplanade"],
  ["Plaza Merdeka", 1.5576, 110.3443, "mall"],
  ["Carpenter Street", 1.5580, 110.3462, "old town"],
  ["Borneo Cultures Museum", 1.5555, 110.3430, "sarawak museum"],
  ["Tun Jugah Shopping Centre", 1.5570, 110.3510, "mall"],
  ["Kuching Civic Centre", 1.5470, 110.3460, "civic"],
  ["Sarawak General Hospital", 1.5440, 110.3410, "hospital umum sarawak hus"],
  ["IPG Kampus Batu Lintang", 1.5410, 110.3440, "teachers institute"],
  ["Swinburne University Sarawak", 1.5320, 110.3570, "swinburne"],
  ["The Spring Shopping Mall", 1.5380, 110.3570, "the spring mall"],
  ["Vivacity Megamall", 1.5303, 110.3725, "mall"],
  ["CityOne Megamall", 1.5235, 110.3770, "city one mall"],
  ["Saradise", 1.5250, 110.3700, "stutong"],
  ["Taman BDC", 1.5240, 110.3640, "bdc"],
  ["Kenyalang Park", 1.5450, 110.3620, "taman kenyalang"],
  ["Pending Industrial Estate", 1.5570, 110.3850, "kawasan perindustrian pending"],
  ["Kuching Port (Pending)", 1.5600, 110.3920, "pelabuhan port"],
  ["Demak Laut Industrial Park", 1.5900, 110.3950, "demak"],
  ["Senari Port", 1.5950, 110.4100, "sejingkat port"],
  ["Sarawak State Assembly (DUN)", 1.5640, 110.3480, "dewan undangan negeri dun petra jaya"],
  ["Wisma Bapa Malaysia", 1.5750, 110.3370, "government offices petra jaya"],
  ["Normah Medical Specialist Centre", 1.5700, 110.3450, "normah hospital"],
  ["Sarawak Stadium", 1.5650, 110.3200, "stadium negeri petra jaya"],
  ["Batu Kawa New Township (MJC)", 1.5100, 110.3080, "mjc"],
  ["Kuching Sentral", 1.4870, 110.3380, "bus terminal penrissen"],
  ["Kuching International Airport", 1.4847, 110.3470, "kch airport lapangan terbang"],
  ["UNIMAS", 1.4655, 110.4285, "universiti malaysia sarawak samarahan"],
  ["UiTM Samarahan", 1.4550, 110.4500, "uitm kota samarahan"],
  ["Matang Jaya", 1.5500, 110.2850, "matang"],
];

const norm = t => (t || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
const words = t => norm(t).split(" ").filter(w => w.length > 1 && !["jalan", "jln", "taman", "tmn", "kuching", "the", "of"].includes(w));

function spot(label, ll, kind, approx) {
  const n = nearest(ll);
  return { kind, node: n.name, ll, label, note: `near ${n.name}${approx ? " · approximate, drag the pin to adjust" : ""}` };
}

// Offline matches, best first. `detail` (road / taman / landmark) only adds to the score.
export function searchOffline(query, detail = "", saved = []) {
  const q = words(query), d = words(detail);
  if (!q.length && !d.length) return [];
  const cands = [
    ...saved.map(p => ({ text: p.name, item: spot(p.name, p.ll, "saved", false) })),
    ...Object.keys(AREAS).map(n => ({ text: n, item: { kind: "area", node: n, label: n } })),
    ...Object.keys(EXT).map(n => ({ text: n, item: { kind: "area", node: n, label: n } })),
    ...LANDMARKS.map(([n, la, lo, extra]) => ({ text: n + " " + extra, area: nearest([la, lo]).name, item: spot(n, [la, lo], "spot", true) })),
  ];
  const scored = cands.map(c => {
    const t = norm(c.text);
    let sc = 0;
    q.forEach(w => { if (t.split(" ").some(x => x.startsWith(w))) sc += 3; else if (t.includes(w)) sc += 2; });
    const ta = t + " " + norm(c.area);   // details also match the area a landmark is in
    d.forEach(w => { if (ta.includes(w)) sc += 1; });
    if (q.length && norm(c.text).startsWith(q.join(" "))) sc += 2;
    return { sc, item: c.item };
  }).filter(x => x.sc >= Math.max(2, q.length * 2));
  scored.sort((a, b) => b.sc - a.sc);
  return scored.slice(0, 8).map(x => x.item);
}

// Online search (needs internet). Combines the name with the optional details.
export async function searchOnline(query, road = "", near = "", box = null) {
  const q = [query, road, near, "Kuching, Sarawak"].filter(x => x && x.trim()).join(", ");
  const vb = box ? `${box[1] - .04},${box[0] + .04},${box[1] + .04},${box[0] - .04}` : "110.22,1.62,110.52,1.38";
  const url = "https://nominatim.openstreetmap.org/search?format=json&limit=6&countrycodes=my&bounded=1"
    + "&viewbox=" + vb + "&q=" + encodeURIComponent(q);
  const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = ctl ? setTimeout(() => ctl.abort(), 8000) : null;
  try {
    const r = await fetch(url, { headers: { "Accept-Language": "en", "User-Agent": "KuchingTripAdvisor/0.1 (hackathon prototype)" }, signal: ctl?.signal });
    if (!r.ok) throw new Error("search failed");
    const js = await r.json();
    return js.map(x => {
      const parts = String(x.display_name).split(",").map(p => p.trim());
      const ll = [parseFloat(x.lat), parseFloat(x.lon)];
      const it = spot(parts.slice(0, 2).join(", "), ll, "spot", false);
      it.note = `${parts.slice(2, 4).join(", ")} · near ${it.node}`;
      return it;
    });
  } finally { if (timer) clearTimeout(timer); }
}

// Map projection shared by the pin picker (Greater Kuching, slightly padded).
const pts = Object.values(NODES);
export const BOUNDS = {
  la0: Math.min(...pts.map(p => p[0])) - 0.01, la1: Math.max(...pts.map(p => p[0])) + 0.01,
  lo0: Math.min(...pts.map(p => p[1])) - 0.01, lo1: Math.max(...pts.map(p => p[1])) + 0.01,
};

// Street name for a dropped pin (online only). Returns null if it can't be found.
export async function streetName(ll) {
  const url = `https://nominatim.openstreetmap.org/reverse?format=json&zoom=17&lat=${ll[0]}&lon=${ll[1]}`;
  try {
    const r = await fetch(url, { headers: { "Accept-Language": "en", "User-Agent": "KuchingTripAdvisor/0.1 (hackathon prototype)" } });
    if (!r.ok) return null;
    const a = (await r.json()).address || {};
    return a.road || a.neighbourhood || a.suburb || a.amenity || null;
  } catch { return null; }
}

// ---- type-ahead for the From / To boxes ---------------------------------------------
// Splits what the user typed into the place itself and extra context:
//   "7-Eleven near Saradise"        → name "7-Eleven",  near "Saradise"
//   "SMK Green Road, Jalan Batu Lintang" → name "SMK Green Road", road "Jalan Batu Lintang"
//   "office tmn bdc"                → name "office", road "tmn bdc"
const NEAR = /\s*(?:\bnear\b|\bdekat\b|\bberhampiran\b|\bopposite\b|\bopp\b|\bbeside\b|\bbehind\b|\bnext to\b|\bsebelah\b|\bdepan\b|@)\s*/i;
const ROADWORD = /\b(jalan|jln|lorong|lrg|taman|tmn|kampung|kg|lebuh|persiaran)\b/i;
export function parseTyped(text) {
  let t = (text || "").trim(), near = "", road = "";
  const m = t.split(NEAR);
  if (m.length > 1) { t = m[0]; near = m.slice(1).join(" "); }
  const parts = t.split(",").map(x => x.trim()).filter(Boolean);
  let name = parts.shift() || "";
  parts.forEach(p => { road += (road ? " " : "") + p; });
  const rm = name.match(ROADWORD);
  if (rm && rm.index > 0) { road = (name.slice(rm.index) + " " + road).trim(); name = name.slice(0, rm.index).trim(); }
  return { name, road, near };
}

// A rough position for the "near …" / road part, if it's something we know offline.
export function anchorFor(parsed, saved = []) {
  const ctx = [parsed.near, parsed.road].filter(Boolean).join(" ");
  if (!ctx) return null;
  const hit = searchOffline(ctx, "", saved)[0];
  if (!hit) return null;
  return { ll: hit.ll || NODES[hit.node], label: hit.label };
}

// Offline suggestions for typed text; context words boost matches, and an anchor
// ("near Saradise") re-ranks by distance to it.
export function suggest(text, saved = []) {
  const p = parseTyped(text);
  const anchor = anchorFor(p, saved);
  let list;
  if (anchor) {
    // must match the name; context only decides the order (closest to the anchor first)
    list = (p.name ? searchOffline(p.name, "", saved) : [])
      .map(it => ({ it, d: hav(it.ll || NODES[it.node], anchor.ll) }))
      .sort((a, b) => a.d - b.d)
      .map(x => ({ ...x.it, note: (x.it.note ? x.it.note + " · " : "") + `${x.d < 1 ? "under 1" : x.d.toFixed(1)} km from ${anchor.label}` }));
    // always offer the anchor itself as an approximate spot ("somewhere near Saradise")
    const a = nearest(anchor.ll);
    list.push({ kind: "spot", node: a.name, ll: anchor.ll, label: p.name ? `${p.name} (near ${anchor.label})` : anchor.label,
                note: `Approximate: placed at ${anchor.label}. Drag the pin to adjust.` });
  } else {
    list = searchOffline(p.name || text, p.road, saved);
  }
  return { parsed: p, anchor, list: list.slice(0, 6) };
}

export async function suggestOnline(text, saved = []) {
  const p = parseTyped(text);
  const anchor = anchorFor(p, saved);
  // a known anchor narrows the search box instead of being sent as words
  let res = await searchOnline(p.name || text, p.road, anchor ? "" : p.near, anchor ? anchor.ll : null);
  if (!res.length && anchor) res = await searchOnline(p.name || text, p.road, p.near);
  if (anchor) res = res.map(it => ({ it, d: hav(it.ll, anchor.ll) })).sort((a, b) => a.d - b.d)
    .map(x => ({ ...x.it, note: x.it.note + ` · ${x.d < 1 ? "under 1" : x.d.toFixed(1)} km from ${anchor.label}` }));
  return res;
}
