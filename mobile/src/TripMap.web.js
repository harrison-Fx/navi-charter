// Real street map for the web version (OpenStreetMap tiles via Leaflet).
// Tap to set the start or destination, drag the pins to adjust, "Locate me" uses the browser.
// If the map tiles can't load (no internet, or a page that blocks them), it says so and the
// app falls back to the simple map pickers.
import React, { useEffect, useRef, useState } from "react";
import { View, Text, Pressable } from "react-native";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { NODES, nearest } from "./engine";
import Seg from "./Seg";

const KUCHING = [1.545, 110.355];
const BOUNDS = [[1.36, 110.18], [1.66, 110.56]];

const pinIcon = (letter, color) => L.divIcon({
  className: "kta-pin",
  html: `<div style="position:relative;width:30px;height:40px">
    <svg width="30" height="40" viewBox="0 0 30 40"><path d="M15 39 C15 39 2 23 2 14 A13 13 0 0 1 28 14 C28 23 15 39 15 39Z" fill="${color}" stroke="#fff" stroke-width="2.5"/></svg>
    <span style="position:absolute;top:6px;left:0;width:30px;text-align:center;color:#fff;font:700 13px system-ui,sans-serif">${letter}</span></div>`,
  iconSize: [30, 40], iconAnchor: [15, 39],
});
const llOf = p => p && (p.ll || NODES[p.node]);

export default function TripMap({ s, c, from, to, onSet, height = 280 }) {
  const box = useRef(null), map = useRef(null), mk = useRef({}), aim = useRef("from");
  const [aimState, setAimState] = useState("from");
  const [tilesOk, setTilesOk] = useState(true);
  const [locating, setLocating] = useState(false);
  const setAim = a => { aim.current = a; setAimState(a); };
  const cb = useRef(onSet); cb.current = onSet;

  useEffect(() => {
    if (!box.current || map.current) return;
    const m = L.map(box.current, { zoomControl: true, attributionControl: true, maxBounds: BOUNDS, minZoom: 10, scrollWheelZoom: false }).setView(KUCHING, 12);
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "© OpenStreetMap contributors",
    }).addTo(m);
    let loaded = 0, failed = 0;
    tiles.on("tileload", () => { loaded++; setTilesOk(true); });
    tiles.on("tileerror", () => { failed++; if (failed >= 4 && loaded === 0) setTilesOk(false); });
    m.on("click", e => {
      const which = aim.current;
      cb.current(which, [e.latlng.lat, e.latlng.lng]);
      if (which === "from") setAim("to");
    });
    map.current = m;
    setTimeout(() => m.invalidateSize(), 50);
    return () => { m.remove(); map.current = null; mk.current = {}; };
  }, []);

  // keep markers in step with the trip
  useEffect(() => {
    const m = map.current; if (!m) return;
    [["from", from, "A", c.accent], ["to", to, "B", c.slow]].forEach(([k, p, letter, color]) => {
      const ll = llOf(p);
      if (!ll) { if (mk.current[k]) { mk.current[k].remove(); delete mk.current[k]; } return; }
      if (!mk.current[k]) {
        const marker = L.marker(ll, { draggable: true, icon: pinIcon(letter, color), title: k === "from" ? "Start" : "Destination" }).addTo(m);
        marker.on("dragend", () => { const q = marker.getLatLng(); cb.current(k, [q.lat, q.lng]); });
        mk.current[k] = marker;
      } else mk.current[k].setLatLng(ll);
    });
    const pts = [llOf(from), llOf(to)].filter(Boolean);
    if (pts.length === 2) m.fitBounds(pts, { padding: [40, 40], maxZoom: 15 });
  }, [from && (from.ll || from.node), to && (to.ll || to.node)]);

  const locate = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      pos => { setLocating(false); const ll = [pos.coords.latitude, pos.coords.longitude]; cb.current("from", ll, true); map.current && map.current.setView(ll, 15); setAim("to"); },
      () => setLocating(false), { enableHighAccuracy: true, timeout: 10000 });
  };

  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Text style={[s.label, { marginBottom: 0 }]}>Tap the map to set</Text>
        <Seg s={s} value={aimState} onChange={setAim} options={[["from", "A · Start"], ["to", "B · Destination"]]} />
      </View>
      <View style={{ height, borderRadius: 12, overflow: "hidden", borderWidth: 1, borderColor: c.line }}>
        <View ref={box} style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, cursor: "crosshair" }} />
        <Pressable onPress={locate} style={{ position: "absolute", right: 10, bottom: 24, zIndex: 500, backgroundColor: c.surface, borderRadius: 18, paddingVertical: 8, paddingHorizontal: 12, borderWidth: 1, borderColor: c.line }}>
          <Text style={[s.link, { fontSize: 13 }]}>{locating ? "Finding you…" : "◎ Locate me"}</Text>
        </Pressable>
      </View>
      <Text style={s.hint}>{tilesOk
        ? "Drag A or B to fine-tune. The advice uses the nearest area; Google Maps gets the exact point."
        : "The street map needs internet. Use the place list or \"Pick exact spot\" instead."}</Text>
    </View>
  );
}

export const hasTripMap = true;
