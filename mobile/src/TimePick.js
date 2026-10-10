// "Arrive by" time picker:
//  • tap the big time and type it ("8:15", "815", "8.15pm", "20:15")
//  • drag along the day bar (busy periods shaded), 5-minute steps
//  • one-tap common times, and −15/−5/+5/+15 for fine tuning
import React, { useState } from "react";
import { View, Text, TextInput, Pressable, ScrollView } from "react-native";

const pad = n => String(n).padStart(2, "0");
const hm = m => `${pad(Math.floor(m / 60) % 24)}:${pad(m % 60)}`;
const ampm = m => { const h = Math.floor(m / 60) % 24, mm = m % 60; return `${((h + 11) % 12) + 1}:${pad(mm)} ${h < 12 ? "AM" : "PM"}`; };

// Understands 8, 815, 0815, 8:15, 8.15, 8 15, 8:15pm, 8pm, 20:15. Hours 1–6 with no am/pm are read as PM.
export function parseTime(str) {
  const t = String(str || "").trim().toLowerCase().replace(/\s+/g, " ");
  const m = t.match(/^(\d{1,2})(?:[:. h]?(\d{2}))?\s*(am|pm|a|p|pagi|petang|malam)?$/);
  if (!m) return null;
  let h = +m[1], mi = m[2] ? +m[2] : 0; const suf = m[3];
  if (!m[2] && m[1].length === 3) return null;          // "815" is handled below
  if (h > 23 || mi > 59) return null;
  if (suf && /^(pm|p|petang|malam)$/.test(suf) && h < 12) h += 12;
  if (suf && /^(am|a|pagi)$/.test(suf) && h === 12) h = 0;
  if (!suf && h >= 1 && h <= 6) h += 12;
  return h * 60 + mi;
}
function parseLoose(str) {
  const t = String(str || "").trim().toLowerCase();
  const d = t.match(/^(\d{3,4})\s*(am|pm|a|p)?$/);            // 815, 0815, 1730pm
  if (d) { const s = d[1].padStart(4, "0"); return parseTime(`${s.slice(0, 2)}:${s.slice(2)}${d[2] ? " " + d[2] : ""}`); }
  return parseTime(t);
}

const DAY0 = 5 * 60, DAY1 = 22 * 60;                    // bar covers 05:00–22:00
const BUSY = [[6 * 60 + 45, 8 * 60 + 30], [12 * 60 + 30, 14 * 60], [17 * 60, 18 * 60 + 45]];
const PRESETS = [7 * 60, 7 * 60 + 30, 8 * 60, 8 * 60 + 30, 9 * 60, 13 * 60, 17 * 60 + 30];

export default function TimePick({ s, c, value, onChange, dayOff, nowMin }) {
  const [text, setText] = useState(null);
  const [bad, setBad] = useState(false);
  const [w, setW] = useState(0);
  const commit = () => {
    if (text === null) return;
    const v = parseLoose(text);
    if (v === null) { setBad(true); return; }
    setBad(false); setText(null); onChange(v);
  };
  const clampSet = v => onChange(Math.max(0, Math.min(1439, Math.round(v / 5) * 5)));
  const fromX = x => DAY0 + Math.max(0, Math.min(1, x / w)) * (DAY1 - DAY0);
  const xOf = m => ((Math.max(DAY0, Math.min(DAY1, m)) - DAY0) / (DAY1 - DAY0)) * w;
  const drag = e => w && clampSet(fromX(e.nativeEvent.locationX));
  let rel = "";
  if (!dayOff && typeof nowMin === "number") {
    const d = value - nowMin;
    rel = d <= 0 ? "already passed today" : `in ${Math.floor(d / 60) ? Math.floor(d / 60) + "h " : ""}${d % 60}m`;
  }
  const step = d => <Pressable key={d} onPress={() => onChange((value + d + 1440) % 1440)} accessibilityRole="button" accessibilityLabel={`${d > 0 ? "plus" : "minus"} ${Math.abs(d)} minutes`}
    style={({ pressed }) => [{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 }, pressed && { backgroundColor: c.sunk }]}>
    <Text style={{ color: c.accent, fontWeight: "700", fontSize: 13, fontVariant: ["tabular-nums"] }}>{d > 0 ? "+" + d : "−" + -d}</Text></Pressable>;

  return (
    <View style={{ gap: 10 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        <TextInput value={text !== null ? text : hm(value)} onFocus={() => { setText(""); setBad(false); }} onChangeText={t => { setText(t); setBad(false); }}
          onBlur={commit} onSubmitEditing={commit} placeholder={hm(value)} placeholderTextColor={c.muted} keyboardType="numbers-and-punctuation" returnKeyType="done"
          accessibilityLabel="Arrive by time, type to change"
          style={[s.timeBig, { minWidth: 0, width: 116, textAlign: "left", paddingVertical: 2, paddingHorizontal: 8, borderRadius: 10, borderWidth: 1.5, borderColor: bad ? c.slow : text !== null ? c.accent : "transparent", backgroundColor: text !== null ? c.surface : "transparent", outlineStyle: "none" }]} />
        <View style={{ flex: 1 }}>
          <Text style={[s.body, { fontWeight: "600" }]}>{ampm(value)}{dayOff ? " tomorrow" : ""}</Text>
          <Text style={s.hint}>{bad ? "Try 8:15, 815 or 8.15pm" : text !== null ? "Type a time, then Enter" : rel || "Tap the time to type it"}</Text>
        </View>
        <View style={{ flexDirection: "row", borderRadius: 10, borderWidth: 1, borderColor: c.line }}>{[-5, 5].map(step)}</View>
      </View>

      <View onLayout={e => setW(e.nativeEvent.layout.width)} style={{ height: 44, justifyContent: "center", userSelect: "none", touchAction: "none", cursor: "pointer" }}
        onStartShouldSetResponder={() => true} onMoveShouldSetResponder={() => true} onResponderGrant={drag} onResponderMove={drag}
        accessibilityRole="adjustable" accessibilityLabel="Drag to set the arrival time" accessibilityValue={{ text: hm(value) }}>
        <View pointerEvents="none" style={{ height: 8, borderRadius: 4, backgroundColor: c.sunk, overflow: "hidden" }}>
          {w > 0 && BUSY.map(([a, b], i) => <View key={i} style={{ position: "absolute", left: xOf(a), width: xOf(b) - xOf(a), top: 0, bottom: 0, backgroundColor: c.school, opacity: .32 }} />)}
          {w > 0 && <View style={{ position: "absolute", left: 0, width: xOf(value), top: 0, bottom: 0, backgroundColor: c.accent, opacity: .28 }} />}
        </View>
        {w > 0 && <View pointerEvents="none" style={{ position: "absolute", left: xOf(value) - 11, width: 22, height: 22, borderRadius: 11, backgroundColor: c.surface, borderWidth: 3, borderColor: c.accent,
          boxShadow: "0 1px 4px rgba(0,0,0,.18)", elevation: 2 }} />}
        {w > 0 && [6, 9, 12, 15, 18, 21].map(h => <Text key={h} pointerEvents="none" style={{ position: "absolute", top: 32, left: xOf(h * 60) - 12, width: 24, textAlign: "center", fontSize: 10, color: c.muted }}>{h}</Text>)}
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: -2 }}>
        <View style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: c.school, opacity: .45 }} /><Text style={[s.hint, { fontSize: 11 }]}>busier: school runs and rush hours</Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
        {PRESETS.map(m => {
          const on = m === value;
          return <Pressable key={m} onPress={() => onChange(m)} accessibilityRole="button"
            style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, borderWidth: 1, borderColor: on ? c.accent : c.line, backgroundColor: on ? c.accentSoft : c.surface }}>
            <Text style={{ color: on ? c.accent : c.fg, fontWeight: on ? "700" : "500", fontSize: 13, fontVariant: ["tabular-nums"] }}>{hm(m)}</Text></Pressable>;
        })}
        <View style={{ flexDirection: "row", borderRadius: 999, borderWidth: 1, borderColor: c.line, marginLeft: 4 }}>{[-15, 15].map(step)}</View>
      </ScrollView>
    </View>
  );
}
