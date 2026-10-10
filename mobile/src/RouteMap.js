import React from "react";
import Svg, { Line, Circle, Rect, Text as SvgText, Polyline } from "react-native-svg";
import { AREAS, EXT, NODES, ROADS, DEPOTS } from "./engine";

// Simplified map: areas and main roads, positions approximate. Shows Greater Kuching
// when the trip starts or ends outside the city.
export default function RouteMap({ res, colors, width }) {
  const greater = !!(res && (EXT[res.from] || EXT[res.to]));
  const pts = Object.values(greater ? NODES : AREAS);
  const lats = pts.map(p => p[0]), lons = pts.map(p => p[1]);
  const [la0, la1, lo0, lo1] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const W = 340, H = 300, px = 40, py = 28;
  const xy = n => {
    const [la, lo] = NODES[n];
    if (!greater && EXT[n]) { // draw outside areas as short stubs pointing the right way
      const g = EXT[n][3][0][0]; const [gx, gy] = xy(g);
      const tx = px + (lo - lo0) / (lo1 - lo0) * (W - 2 * px), ty = py + (la1 - la) / (la1 - la0) * (H - 2 * py);
      const dx = tx - gx, dy = ty - gy, L = Math.hypot(dx, dy) || 1;
      return [Math.min(W - 8, Math.max(8, gx + dx / L * 34)), Math.min(H - 8, Math.max(8, gy + dy / L * 34))];
    }
    return [px + (lo - lo0) / (lo1 - lo0) * (W - 2 * px), py + (la1 - la) / (la1 - la0) * (H - 2 * py)];
  };
  const on = new Set(res ? res.best.roads : []);
  const slow = new Set(res ? res.best.busy.filter(b => b.vc > .85).map(b => b.c) : []);
  const route = res ? [res.from, ...res.best.via, res.to].map(xy) : [];
  const label = n => n === res?.from || n === res?.to || (DEPOTS.some(d => d[0] === n) && !greater) || (EXT[n] && greater);
  return (
    <Svg width={width} height={width * H / W} viewBox={`0 0 ${W} ${H}`}>
      {ROADS.map((r, i) => {
        const [x1, y1] = xy(r.a), [x2, y2] = xy(r.b);
        return <Line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={slow.has(i) ? colors.slow : colors.road} strokeWidth={r.cls === "trunk" || r.cls === "primary" ? 4 : 2.5} strokeLinecap="round" opacity={on.has(i) ? 1 : .8} />;
      })}
      {route.length > 1 && <Polyline points={route.map(p => p.join(",")).join(" ")} fill="none" stroke={colors.accent} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" />}
      {Object.keys(NODES).map(n => {
        const [x, y] = xy(n), end = n === res?.from || n === res?.to;
        return EXT[n]
          ? <Rect key={n} x={x - 5} y={y - 5} width={10} height={10} rx={2} fill={end ? colors.accent : colors.sunk} stroke={colors.muted} strokeWidth={1.2} />
          : <Circle key={n} cx={x} cy={y} r={end ? 6 : 3.2} fill={end ? colors.accent : colors.surface} stroke={end ? colors.accent : colors.muted} strokeWidth={1.5} />;
      })}
      {Object.keys(NODES).filter(label).map(n => {
        const [x, y] = xy(n); const right = x < W - 90;
        return <SvgText key={"t" + n} x={x + (right ? 8 : -8)} y={y - 7} fontSize={11} fontWeight={n === res?.from || n === res?.to ? "700" : "400"} fontStyle={EXT[n] ? "italic" : "normal"} fill={colors.fg} textAnchor={right ? "start" : "end"}>{n}</SvgText>;
      })}
    </Svg>
  );
}
