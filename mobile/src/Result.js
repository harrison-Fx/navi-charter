// The advice, laid out as a journey:
//   header (leave-by, countdown, risk) → timeline bar (leave · arrival window · deadline)
//   → stop-by-stop route with what happens on each stretch → why → actions → other ways.
import React, { useState } from "react";
import { View, Text, Pressable } from "react-native";
import { hm } from "./engine";

const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const until = (m, now) => { const d = m - now; if (d <= 0) return "now"; const h = Math.floor(d / 60); return `in ${h ? h + "h " : ""}${d % 60}m`; };

function TimelineBar({ s, c, b, arrive }) {
  const [w, setW] = useState(0);
  const t0 = b.leave - 3, t1 = Math.max(arrive, b.hi) + 4;
  const x = m => ((m - t0) / (t1 - t0)) * w;
  const late = b.hi > arrive;
  const BAR = 30;                                       // bar centre line
  // label boxes are 84 px wide, kept inside the bar's width
  const lab = (m, top, label, sub, color, align) => {
    const L = Math.max(0, Math.min(w - 84, x(m) - (align === "left" ? 8 : align === "right" ? 76 : 42)));
    return (
      <View key={label + sub} pointerEvents="none" style={{ position: "absolute", left: L, width: 84, top, alignItems: align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center" }}>
        <Text style={{ fontSize: 13, fontWeight: "700", color, fontVariant: ["tabular-nums"] }}>{label}</Text>
        {sub ? <Text style={{ fontSize: 10, color: c.muted }}>{sub}</Text> : null}
      </View>
    );
  };
  return (
    <View onLayout={e => setW(e.nativeEvent.layout.width)} style={{ height: 78, marginTop: 2 }} accessibilityLabel={`Leave ${hm(b.leave)}, arrive between ${hm(b.lo)} and ${hm(b.hi)}, be there by ${hm(arrive)}`}>
      {w > 0 && <>
        <View pointerEvents="none" style={{ position: "absolute", left: Math.max(0, Math.min(w - 110, x(arrive) - 104)), width: 110, top: 0, alignItems: "flex-end" }}>
          <Text style={{ fontSize: 11, color: c.slow, fontWeight: "700" }}>be there by {hm(arrive)}</Text>
        </View>
        <View style={{ position: "absolute", left: 0, right: 0, top: BAR - 2, height: 4, borderRadius: 2, backgroundColor: c.sunk }} />
        <View style={{ position: "absolute", left: x(b.leave), width: x(b.lo) - x(b.leave), top: BAR - 2, height: 4, backgroundColor: c.accent, opacity: .5 }} />
        <View style={{ position: "absolute", left: x(b.lo), width: Math.max(4, x(b.hi) - x(b.lo)), top: BAR - 8, height: 16, borderRadius: 8, backgroundColor: late ? c.schoolSoft : c.okSoft, borderWidth: 1.5, borderColor: late ? c.school : c.ok }} />
        <View style={{ position: "absolute", left: x(b.mid) - 1, width: 2, top: BAR - 10, height: 20, backgroundColor: late ? c.school : c.ok }} />
        <View style={{ position: "absolute", left: x(arrive) - 1, top: 15, width: 2, height: 24, backgroundColor: c.slow }} />
        <View style={{ position: "absolute", left: x(b.leave) - 8, top: BAR - 8, width: 16, height: 16, borderRadius: 8, backgroundColor: c.accent, borderWidth: 3, borderColor: c.surface }} />
        {lab(b.leave, BAR + 12, hm(b.leave), "leave", c.accent, "left")}
        {lab(b.mid, BAR + 12, hm(b.mid), "most likely", late ? c.school : c.ok, "center")}
      </>}
    </View>
  );
}

function Stops({ s, c, b, from, to, school }) {
  const names = [from.label, ...b.via, to.label];
  const times = [b.leave, ...b.busy.slice(1).map(x => x.at), b.mid];
  return (
    <View style={{ marginTop: 6 }}>
      {names.map((n, i) => {
        const seg = i < b.busy.length ? b.busy[i] : null;
        const last = i === names.length - 1;
        const sch = seg && b.schools.find(x => x.c === seg.c);
        const flags = [];
        if (sch) flags.push([c.school, `school zone ~${hm(sch.at)}`]);
        if (seg && seg.reportedJam) flags.push([c.slow, "reported jam"]);
        if (seg && seg.vc > .85) flags.push([c.slow, `${seg.vc >= 1 ? "very busy" : "busy"}${seg.outsideShare > .3 && seg.outsideFrom ? ` · lots from ${seg.outsideFrom}` : ""}`]);
        return (
          <View key={i} style={{ flexDirection: "row", gap: 12 }}>
            <View style={{ width: 22, alignItems: "center" }}>
              <View style={{ width: i === 0 || last ? 18 : 12, height: i === 0 || last ? 18 : 12, borderRadius: 9, marginTop: i === 0 || last ? 1 : 4,
                backgroundColor: i === 0 ? c.accent : last ? c.slow : c.surface, borderWidth: 2.5, borderColor: i === 0 ? c.accent : last ? c.slow : c.muted, alignItems: "center", justifyContent: "center" }}>
                {(i === 0 || last) && <Text style={{ color: "#fff", fontSize: 9, fontWeight: "800" }}>{i === 0 ? "A" : "B"}</Text>}
              </View>
              {!last && <View style={{ flex: 1, width: 3, minHeight: 22, backgroundColor: flags.length ? flags[0][0] : c.line, opacity: flags.length ? .7 : 1, marginVertical: 2, borderRadius: 2 }} />}
            </View>
            <View style={{ flex: 1, paddingBottom: last ? 0 : 10 }}>
              <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
                <Text style={[s.body, { flex: 1, fontWeight: i === 0 || last ? "700" : "500" }]} numberOfLines={1}>{n}</Text>
                <Text style={[s.mono, { color: c.muted }]}>{i === 0 ? "leave " : last ? "arrive ~" : "~"}{hm(times[i])}</Text>
              </View>
              {!last && (flags.length
                ? <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 }}>{flags.map(([col, t], k) => (
                    <View key={k} style={{ flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 99, backgroundColor: c.sunk }}>
                      <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: col }} /><Text style={{ fontSize: 12, color: c.fg }}>{t}</Text></View>))}</View>
                : <Text style={[s.hint, { marginTop: 2 }]}>{seg ? `${seg.road} · ${school ? "clear" : "normal traffic"}` : ""}</Text>)}
            </View>
          </View>
        );
      })}
    </View>
  );
}

export default function Result({ s, c, res, b, advised, chosen, onPickRoute, from, to, arrive, dayOff, conf, school, causes, risk, pl, link, nowMin, onMaps, onMapsPlain, onRemind, onShare, onTest, Btn, Pill, Note, RouteMap, mapWidth, closedNotes }) {
  const [showTest, setShowTest] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const spare = Math.round(arrive - b.mid);
  const tone = { ok: [c.okSoft, c.ok], warn: [c.schoolSoft, c.school], bad: [c.slowSoft, c.slow] }[risk[1]];
  return (
    <View style={{ gap: 12 }}>
      {chosen && (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: 12, backgroundColor: c.schoolSoft, borderWidth: 1, borderColor: c.school }}>
          <Text style={[s.body, { flex: 1 }]}>Showing the way you picked{advised ? ` (advised: leave ${hm(advised.leave)}${advised.via.length ? " via " + advised.via.join(", ") : ""})` : ""}.</Text>
          <Pressable onPress={() => onPickRoute(res.routes.indexOf(advised))} accessibilityRole="button"><Text style={[s.link, { fontSize: 14 }]}>Back to advised</Text></Pressable>
        </View>
      )}
      <View style={[s.card, { padding: 0, overflow: "hidden" }]}>
        <View style={{ padding: 16, paddingBottom: 12, backgroundColor: c.accentSoft, gap: 2 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={[s.cap, { color: c.accent }]}>LEAVE BY</Text>
            <Text style={[s.mono, { color: c.accent, fontWeight: "700" }]}>{dayOff ? "tomorrow" : until(b.leave, nowMin)}</Text>
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Text style={[s.leave, { marginRight: 0 }]}>{hm(b.leave)}</Text>
            <View style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: 99, backgroundColor: tone[0], borderWidth: 1, borderColor: tone[1] }}>
              <Text style={{ color: tone[1], fontWeight: "700", fontSize: 13 }}>{risk[0]} · {pl}% late</Text>
            </View>
          </View>
          <Text style={[s.hint, { color: c.fg }]} numberOfLines={2}>{from.label} → {to.label} · {b.km.toFixed(1)} km · about {Math.round(b.typical)} min</Text>
        </View>
        <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12 }}>
          <TimelineBar s={s} c={c} b={b} arrive={arrive} />
          <Text style={[s.body, { marginTop: 2 }]}>
            {b.ok
              ? <>Most likely there at <Text style={{ fontWeight: "700" }}>{hm(b.mid)}</Text>{spare > 0 ? `, ${plural(spare, "minute")} to spare` : ""}. 8 in 10 tries arrived {hm(b.lo)}–{hm(b.hi)}.</>
              : <Text style={{ color: c.slow, fontWeight: "600" }}>Even leaving at {hm(b.leave)} doesn't get you to {Math.round(conf * 100)}% sure. Leave as early as you can.</Text>}
          </Text>
        </View>
      </View>

      {causes.length > 0 && (
        <View style={[s.card, { gap: 8 }]}>
          <Text style={s.label}>Why this advice</Text>
          <View style={{ flexDirection: "row", gap: 10 }}>
            <View style={{ width: 4, borderRadius: 2, backgroundColor: tone[1] }} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={[s.body, { fontWeight: "700" }]}>{causes[0].label}</Text>
              <Text style={s.body}>{causes[0].detail}</Text>
            </View>
          </View>
          {causes.length > 1 && <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
            <Text style={s.hint}>Also:</Text>
            {causes.slice(1).map((x, i) => <View key={i} style={{ paddingHorizontal: 8, paddingVertical: 2, borderRadius: 99, backgroundColor: c.sunk }}><Text style={{ fontSize: 12, color: c.fg }}>{x.label}</Text></View>)}
          </View>}
        </View>
      )}

      <View style={s.card}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <Text style={s.label}>Your route</Text>
          <Pressable onPress={() => setShowMap(!showMap)}><Text style={[s.link, { fontSize: 13 }]}>{showMap ? "Hide sketch" : "Route sketch"}</Text></Pressable>
        </View>
        <Stops s={s} c={c} b={b} from={from} to={to} school={school} />
        {closedNotes}
        {b.vans > 0 && <Text style={[s.hint, { marginTop: 6 }]}>{b.vans} other planned trips share part of this route around your time; the advice already spreads them out.</Text>}
        {showMap && <View style={{ marginTop: 8 }}><RouteMap res={res} colors={c} width={mapWidth} /></View>}
        <View style={{ gap: 8, marginTop: 14 }}>
          <Btn s={s} kind="solid" label="Open in Google Maps" onPress={onMaps} />
          <View style={s.row}>
            <View style={{ flex: 1 }}><Btn s={s} kind="ghost" label="Remind me" onPress={onRemind} /></View>
            <View style={{ flex: 1 }}><Btn s={s} kind="ghost" label="Send as message" onPress={onShare} /></View>
          </View>
          {link.stop ? <Pressable onPress={onMapsPlain}><Text style={[s.link, { fontSize: 13, textAlign: "center" }]}>Open without the extra stop at {link.stop}</Text></Pressable> : null}
        </View>
        <Text style={[s.hint, { marginTop: 8 }]}>
          {link.stop ? `This way lets you leave ${res.gain || "a few"} min later than the usual road, so the Maps link adds a stop at ${link.stop}.` : res.keptUsual ? "Another way was only slightly quicker, so we kept the usual road." : "This is the usual road; Google Maps picks the exact streets."}
        </Text>
      </View>

      <View style={s.card}>
        <Text style={s.label}>Other ways to go</Text>
        {res.routes.map((r, i) => {
          const on = r === b, isAdv = r === (advised || b), p = Math.round(r.pLate * 100), t = p <= 10 ? c.ok : p <= 25 ? c.school : c.slow;
          return (
            <Pressable key={i} onPress={() => onPickRoute && onPickRoute(i)} accessibilityRole="button" accessibilityState={{ selected: on }}
              accessibilityLabel={`${r.via.length ? "via " + r.via.join(", ") : "Direct"}, leave ${hm(r.leave)}, ${p}% chance of being late${on ? ", shown" : ", tap to see this way"}`}
              style={({ pressed }) => [{ flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10, paddingHorizontal: 10, borderRadius: 10, marginTop: 4, backgroundColor: on ? c.accentSoft : pressed ? c.sunk : "transparent", borderWidth: 1, borderColor: on ? c.accent : c.line, cursor: "pointer" }]}>
              <View style={{ flex: 1 }}>
                <Text style={[s.body, { fontWeight: on ? "700" : "500" }]} numberOfLines={1}>{r.via.length ? "via " + r.via.join(", ") : "Direct"}</Text>
                <Text style={s.hint}>{isAdv ? "Advised · " : ""}{r === res.fastest ? "usual road · " : ""}{Math.round(r.typical)} min · {r.km.toFixed(1)} km{on ? "" : " · tap to see"}</Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={[s.mono, { fontWeight: "700", fontSize: 15 }]}>{r.ok ? hm(r.leave) : "—"}</Text>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}><View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: t }} /><Text style={s.hint}>{p}% late</Text></View>
              </View>
            </Pressable>
          );
        })}
        <Text style={[s.hint, { marginTop: 8 }]}>Leave-by times for {Math.round(conf * 100)}% sure. Tap a way to see its details and Maps link. Made-up traffic, tried 240 times per route.</Text>
      </View>

      <View style={s.card}>
        <Pressable onPress={() => setShowTest(!showTest)} style={{ flexDirection: "row", justifyContent: "space-between" }}>
          <Text style={s.label}>For testers: log this trip</Text><Text style={s.link}>{showTest ? "▴" : "▾"}</Text>
        </Pressable>
        {showTest && <>
          <Text style={[s.hint, { marginBottom: 8 }]}>Saves the plan so you can time the real trip and compare.</Text>
          <View style={s.row}>
            <View style={{ flex: 1 }}><Btn s={s} kind="ghost" label="Following advice" onPress={() => onTest("follow")} /></View>
            <View style={{ flex: 1 }}><Btn s={s} kind="ghost" label="My usual way" onPress={() => onTest("usual")} /></View>
          </View>
        </>}
      </View>
    </View>
  );
}
