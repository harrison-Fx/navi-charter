// Drop or drag a pin to set a start or destination. Tap anywhere on the map, or drag.
import React, { useMemo, useState } from "react";
import { View, Text, Pressable, ScrollView } from "react-native";
import Sheet from "./Sheet";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Line, Circle, Rect, Text as SvgText, G, Path } from "react-native-svg";
import { AREAS, EXT, NODES, ROADS, nearest } from "./engine";

function boundsOf(names, pad) {
  const p = names.map(n => NODES[n]);
  return { la0: Math.min(...p.map(x => x[0])) - pad, la1: Math.max(...p.map(x => x[0])) + pad,
           lo0: Math.min(...p.map(x => x[1])) - pad, lo1: Math.max(...p.map(x => x[1])) + pad };
}
const VIEWS = { city: boundsOf(Object.keys(AREAS), 0.008), greater: boundsOf(Object.keys(NODES), 0.012) };

export default function PinMap({ visible, s, c, width, start, title, onUse, onClose }) {
  const [ll, setLl] = useState(start || NODES["City Centre"]);
  const [view, setView] = useState(start && nearest(start).name in EXT ? "greater" : "city");
  React.useEffect(() => { if (visible) { const p = start || NODES["City Centre"]; setLl(p); setView(nearest(p).name in EXT ? "greater" : "city"); } }, [visible]);

  const B = VIEWS[view];
  const W = Math.min(width - 32, 520);
  const H = Math.round(W * (B.la1 - B.la0) / ((B.lo1 - B.lo0) * Math.cos(1.55 * Math.PI / 180)));
  const xy = p => [(p[1] - B.lo0) / (B.lo1 - B.lo0) * W, (B.la1 - p[0]) / (B.la1 - B.la0) * H];
  const toLL = (x, y) => [B.la1 - Math.max(0, Math.min(H, y)) / H * (B.la1 - B.la0), B.lo0 + Math.max(0, Math.min(W, x)) / W * (B.lo1 - B.lo0)];
  const move = e => { const { locationX, locationY } = e.nativeEvent; setLl(toLL(locationX, locationY)); };
  const n = nearest(ll);
  const [px, py] = xy(ll);
  const shown = useMemo(() => Object.keys(NODES).filter(k => view === "greater" || AREAS[k]), [view]);

  return (
    <Sheet visible={visible} onRequestClose={onClose} bg={c.bg}>
      <SafeAreaView style={s.fill}>
        <View style={s.modalHead}><Text style={s.h2}>{title || "Drop a pin"}</Text><Pressable onPress={onClose}><Text style={s.link}>Close</Text></Pressable></View>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }} scrollEnabled={false}>
          <View style={s.seg}>
            {[["city", "Kuching"], ["greater", "Greater Kuching"]].map(([v, l]) => (
              <Pressable key={v} onPress={() => setView(v)} style={[s.segItem, view === v && s.segOn]} accessibilityRole="radio" accessibilityState={{ selected: view === v }}><Text style={[s.segText, view === v && s.segTextOn]}>{l}</Text></Pressable>
            ))}
          </View>
          <Text style={s.hint}>Tap the map or drag the pin. Positions are approximate; the advice uses the nearest area.</Text>
          <View style={{ width: W, height: H, borderRadius: 12, overflow: "hidden", backgroundColor: c.sunk, alignSelf: "center", userSelect: "none", touchAction: "none", cursor: "crosshair" }}
            onStartShouldSetResponder={() => true} onMoveShouldSetResponder={() => true}
            onResponderGrant={move} onResponderMove={move}>
            <Svg width={W} height={H} pointerEvents="none">
              {ROADS.filter(r => shown.includes(r.a) && shown.includes(r.b)).map((r, i) => {
                const [x1, y1] = xy(NODES[r.a]), [x2, y2] = xy(NODES[r.b]);
                return <Line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={c.road} strokeWidth={r.cls === "trunk" || r.cls === "primary" ? 4 : 2.5} strokeLinecap="round" />;
              })}
              {shown.map(k => {
                const [x, y] = xy(NODES[k]); const near = k === n.name;
                return (
                  <G key={k}>
                    {EXT[k] ? <Rect x={x - 4} y={y - 4} width={8} height={8} rx={2} fill={near ? c.accent : c.surface} stroke={c.muted} />
                            : <Circle cx={x} cy={y} r={near ? 5 : 3} fill={near ? c.accent : c.surface} stroke={near ? c.accent : c.muted} strokeWidth={1.5} />}
                    <SvgText x={x + 6} y={y - 6} fontSize={10} fill={near ? c.fg : c.muted} fontWeight={near ? "700" : "400"}>{k}</SvgText>
                  </G>
                );
              })}
              <Line x1={px} y1={py} x2={xy(NODES[n.name])[0]} y2={xy(NODES[n.name])[1]} stroke={c.accent} strokeWidth={1.5} strokeDasharray="4 4" />
              <G>
                <Path d={`M${px},${py} l-9,-18 a10,10 0 1,1 18,0 z`} fill={c.slow} stroke={c.surface} strokeWidth={2} />
                <Circle cx={px} cy={py - 22} r={3.5} fill={c.surface} />
              </G>
            </Svg>
          </View>
          <Text style={s.body}>Near <Text style={{ fontWeight: "700" }}>{n.name}</Text>, {n.km < 1 ? "under 1" : n.km.toFixed(1)} km from its centre</Text>
          <Text style={s.hint}>{ll[0].toFixed(4)}, {ll[1].toFixed(4)} · Google Maps will use this exact point.</Text>
          <Pressable onPress={() => onUse(ll)} accessibilityRole="button" style={({ pressed }) => [s.btn, pressed && { opacity: .7 }]}><Text style={s.btnText}>Use this spot</Text></Pressable>
        </ScrollView>
      </SafeAreaView>
    </Sheet>
  );
}
