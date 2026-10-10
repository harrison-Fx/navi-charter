import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { View, Text, ScrollView, Pressable, TextInput, Switch, Modal, FlatList, Linking, ActivityIndicator, useColorScheme, useWindowDimensions, Platform, StyleSheet } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import * as Location from "expo-location";
import * as Notifications from "expo-notifications";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { advise, mapsLink, message, hm, nearest, AREAS, EXT, ROADS, NODES } from "./src/engine";
import RouteMap from "./src/RouteMap";
import Seg from "./src/Seg";
import TimePick from "./src/TimePick";
import Result from "./src/Result";
import PinMap from "./src/PinMap";
import { searchOffline, searchOnline, streetName, suggest, suggestOnline } from "./src/places";
import TripMap, { hasTripMap } from "./src/TripMap";
import { Alert, Share, Toast, isWeb, webToast } from "./src/webshim";
import Sheet from "./src/Sheet";

// ---------------------------------------------------------------- look
const LIGHT = { bg: "#EEF0EC", surface: "#FFFFFF", sunk: "#E3E6E0", line: "#D3D7D0", fg: "#1E201C", muted: "#5B6058", accent: "#2B5FAD", accentInk: "#FFFFFF", accentSoft: "#E4ECF8", thumb: "#FFFFFF", school: "#B35A00", schoolSoft: "#FBEBD9", slow: "#B03030", slowSoft: "#F8E1E1", ok: "#2E7D4F", okSoft: "#DFF1E6", road: "#C9CEC5" };
const DARK = { bg: "#151815", surface: "#1F231F", sunk: "#2A2F2A", line: "#373D37", fg: "#E8EBE6", muted: "#A3AA9F", accent: "#78A6EC", accentInk: "#0E1A2C", accentSoft: "#1E2D45", thumb: "#3A413A", school: "#F0A050", schoolSoft: "#3A2814", slow: "#F07B7B", slowSoft: "#3D1D1D", ok: "#6FCB94", okSoft: "#173326", road: "#454C44" };

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

// ---------------------------------------------------------------- storage (all on this phone; no accounts)
const load = async (k, d) => { try { const v = await AsyncStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } };
const save = (k, v) => AsyncStorage.setItem(k, JSON.stringify(v)).catch(() => {});
const nowMin = () => { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); };
const dateFor = (dayOffset, minutes) => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + dayOffset); d.setMinutes(minutes); return d; };
const isWeekend = off => { const d = dateFor(off, 0).getDay(); return d === 0 || d === 6; };
const ymd = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
const minOf = iso => { const d = new Date(iso); return d.getHours() * 60 + d.getMinutes(); };
const REPORT_MS = 2 * 3600e3;

export default function App() {
  return <SafeAreaProvider><Main /></SafeAreaProvider>;
}

function Main() {
  const dark = useColorScheme() === "dark";
  const [settings, setSettings] = useState({ nick: "", big: false, commOn: true, vansOn: true, sess: "morning", fakeHere: isWeb ? "Pending" : "" });
  const [places, setPlaces] = useState([]);
  const [trips, setTrips] = useState([]);
  const [reports, setReports] = useState([]);
  const [tab, setTab] = useState("plan");
  const [ready, setReady] = useState(false);
  const c = dark ? DARK : LIGHT;
  const f = settings.big ? 1.25 : 1;
  const s = useMemo(() => makeStyles(c, f), [dark, f]);

  useEffect(() => { (async () => {
    setSettings(await load("settings", settings)); setPlaces(await load("places", [])); setTrips(await load("trips", []));
    setReports((await load("reports", [])).filter(r => r.expires > Date.now())); setReady(true);
    if (!isWeb && Platform.OS === "android") Notifications.setNotificationChannelAsync("leave", { name: "Time to leave", importance: Notifications.AndroidImportance.HIGH }).catch(() => {});
  })(); }, []);
  const upd = (k, v) => { const n = { ...settings, [k]: v }; setSettings(n); save("settings", n); };
  const setPl = v => { setPlaces(v); save("places", v); };
  const setTr = v => { setTrips(v); save("trips", v); };
  const setRe = v => { setReports(v); save("reports", v); };

  if (!ready) return <View style={[s.fill, { justifyContent: "center" }]}><ActivityIndicator color={c.accent} /></View>;
  return (
    <SafeAreaView style={s.fill} edges={["top", "bottom"]}>
      <StatusBar style={dark ? "light" : "dark"} />
      <View style={s.header}><Text style={s.title}>Kuching Trip Advisor</Text><Text style={s.badge}>Practice version · made-up traffic</Text></View>
      <View style={{ flex: 1 }}>
        {tab === "plan" && <PlanScreen {...{ s, c, f, settings, places, setPl, reports, setRe, trips, setTr, goTest: () => setTab("test") }} />}
        {tab === "test" && <TestScreen {...{ s, c, trips, setTr, settings }} />}
        {tab === "settings" && <SettingsScreen {...{ s, c, settings, upd, places, setPl }} />}
      </View>
      <View style={s.tabs}>
        {[["plan", "Plan"], ["test", "Test trips"], ["settings", "Settings"]].map(([k, l]) => (
          <Pressable key={k} onPress={() => setTab(k)} style={s.tab} accessibilityRole="tab" accessibilityState={{ selected: tab === k }}>
            <View style={[s.tabDot, tab === k && { backgroundColor: c.accent }]} />
            <Text style={[s.tabText, tab === k && { color: c.accent, fontWeight: "700" }]}>{l}</Text>
          </Pressable>
        ))}
      </View>
      <Toast c={c} />
    </SafeAreaView>
  );
}

// "My location": real GPS, or a pretend spot chosen in Settings → Demo (for presenting indoors).
const DEMO_SPOTS = ["Pending", "Stutong", "Petra Jaya", "Samarahan", "Matang outer"];
async function getHere(settings) {
  if (settings.fakeHere && NODES[settings.fakeHere]) {
    const p = NODES[settings.fakeHere];
    return { ll: [p[0] + 0.0031, p[1] - 0.0024], demo: true };      // ~0.4 km off the area centre, like a real fix
  }
  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== "granted") throw Object.assign(new Error("denied"), { denied: true });
  const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
  return { ll: [pos.coords.latitude, pos.coords.longitude], demo: false };
}

// ---------------------------------------------------------------- plan
function PlanScreen({ s, c, f, settings, places, setPl, reports, setRe, trips, setTr, goTest }) {
  const { width: winW } = useWindowDimensions();
  const width = isWeb ? Math.min(winW, 430) : winW;
  const [from, setFrom] = useState({ kind: "area", node: "Pending", label: "Pending" });
  const [to, setTo] = useState({ kind: "area", node: "Batu Lintang", label: "Batu Lintang" });
  const [arrive, setArrive] = useState(450);
  const [dayOff, setDayOff] = useState(nowMin() > 600 ? 1 : 0);
  const [school, setSchool] = useState(!isWeekend(nowMin() > 600 ? 1 : 0));
  const [conf, setConf] = useState(.9);
  const [picker, setPicker] = useState(null);
  const [locating, setLocating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [showReport, setShowReport] = useState(false);
  const [pin, setPin] = useState(null);   // { which: "from" | "to" }
  const scroller = useRef(null), resY = useRef(0);
  useEffect(() => { if (res && !res.err) setTimeout(() => scroller.current && scroller.current.scrollTo({ y: Math.max(0, resY.current - 12), animated: true }), 80); }, [res]);

  useEffect(() => { setSchool(!isWeekend(dayOff)); }, [dayOff]);
  useEffect(() => { setRes(null); }, [from, to, arrive, dayOff, school, conf, reports, settings.commOn, settings.vansOn, settings.sess]);

  // a point chosen on the street map (web) or by GPS from the map's "Locate me"
  const setByMap = (which, ll, gps) => {
    const n = nearest(ll), km = n.km < 1 ? "under 1" : n.km.toFixed(1);
    const p = { kind: gps && which === "from" ? "here" : "spot", node: n.name, ll, label: gps ? "My location" : `Pin near ${n.name}`, note: `near ${n.name}, ${km} km away` };
    (which === "from" ? setFrom : setTo)(p);
    if (!gps) streetName(ll).then(st => { if (st) (which === "from" ? setFrom : setTo)(cur => cur.ll === ll ? { ...cur, label: `${st} (near ${n.name})` } : cur); });
  };

  const useMyLocation = async () => {
    setLocating(true);
    try {
      const here = await getHere(settings);
      const ll = here.ll; const n = nearest(ll);
      if (n.km > 15) Alert.alert("Outside the covered area", `You're about ${Math.round(n.km)} km from the nearest area this app knows (${n.name}). Advice will start from ${n.name}.`);
      setFrom({ kind: "here", node: n.name, ll, label: here.demo ? "My location (demo)" : "My location", note: `near ${n.name}, ${n.km < 1 ? "under 1" : n.km.toFixed(1)} km away` });
    } catch (e) {
      if (e.denied) Alert.alert("Location is off", "Allow location for this app, or pick the area you're starting from. For a demo indoors, use Settings → Demo.");
      else Alert.alert("Couldn't get your location", "Check that location is turned on, then try again. You can also pick an area, or use Settings → Demo."); }
    finally { setLocating(false); }
  };

  const active = reports.filter(r => r.expires > Date.now());
  const run = () => {
    setBusy(true);
    setTimeout(() => {
      const r = advise({ from: from.node, to: to.node, arriveBy: arrive, conf, day: school ? "term" : "holiday", sess: settings.sess, commOn: settings.commOn, vansOn: settings.vansOn, closed: active.filter(x => x.kind === "closed").map(x => x.road), slow: active.filter(x => x.kind === "jam").map(x => x.road) });
      setRes(r); setBusy(false);
    }, 30);
  };
  const link = res && !res.err ? mapsLink(res, from.ll, to.ll, from.kind === "here") : null;
  const msg = res && !res.err ? message(res, from.kind === "here" ? "" : from.label, to.label) : "";

  const remind = async () => {
    const when = dateFor(dayOff, res.best.leave - 5);
    if (when.getTime() < Date.now()) { Alert.alert("Too late for a reminder", `Leave-by time ${hm(res.best.leave)} is less than 5 minutes away or already passed.`); return; }
    if (isWeb) { webToast({ title: "Reminder set", msg: `${hm(res.best.leave - 5)}${dayOff ? " tomorrow" : ""}. On the phone this arrives as a notification.` }); return; }
    try {
      let { status } = await Notifications.getPermissionsAsync();
      if (status !== "granted") status = (await Notifications.requestPermissionsAsync()).status;
      if (status !== "granted") { Alert.alert("Notifications are off", "Allow notifications for this app to get a reminder."); return; }
      await Notifications.scheduleNotificationAsync({
        content: { title: `Leave in 5 minutes (${hm(res.best.leave)})`, body: `To reach ${to.label} by ${hm(arrive)}. Go via ${res.best.via.join(", ") || "the direct road"}.` },
        trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: when, channelId: "leave" },
      });
      Alert.alert("Reminder set", `We'll remind you at ${hm(res.best.leave - 5)}${dayOff ? " tomorrow" : ""}.`);
    } catch (e) { Alert.alert("Couldn't set the reminder", String(e?.message || e)); }
  };

  const startTest = mode => {
    const b = res.best;
    const t = { id: String(Date.now()), tester: settings.nick || "me", date: ymd(dateFor(dayOff, 0)), from: from.label, fromNode: from.node, to: to.label, toNode: to.node, arriveBy: hm(arrive), school, mode,
      plan: { leave: hm(b.leave), via: b.via.join(" → ") || "direct", pLate: Math.round(b.pLate * 100), etaLo: hm(b.lo), etaMid: hm(b.mid), etaHi: hm(b.hi), stop: link.stop || "", url: link.url, plain: link.plain },
      left: null, arrived: null, mapsKept: null, notes: "" };
    setTr([t, ...trips]); goTest();
  };

  const b = res && !res.err ? res.best : null;
  const pl = b ? Math.round(b.pLate * 100) : 0;
  const risk = pl <= 10 ? ["Low risk", "ok"] : pl <= 25 ? ["Medium risk", "warn"] : ["High risk", "bad"];
  const causes = b ? riskCauses(b, active) : [];
  return (
    <ScrollView ref={scroller} contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
      <View style={s.card}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <Text style={[s.label, { marginBottom: 0 }]}>From</Text>
          <Btn s={s} small kind={from.kind === "here" ? "solid" : "ghost"} onPress={useMyLocation} label={locating ? "Finding you…" : "◎ My location"} />
        </View>
        <PlaceField s={s} c={c} value={from} places={places} allowHere onHere={useMyLocation} onPick={setFrom} onMore={() => setPicker("from")} />
        <PlaceNote s={s} p={from} onPin={() => setPin({ which: "from" })} />
        <Text style={[s.label, { marginTop: 12 }]}>To</Text>
        <PlaceField s={s} c={c} value={to} places={places} onPick={setTo} onMore={() => setPicker("to")} />
        <PlaceNote s={s} p={to} onPin={() => setPin({ which: "to" })} />
        {hasTripMap && <View style={{ marginTop: 12 }}><TripMap s={s} c={c} from={from} to={to} onSet={setByMap} /></View>}

        <Text style={[s.label, { marginTop: 12 }]}>Arrive by</Text>
        <TimePick s={s} c={c} value={arrive} onChange={setArrive} dayOff={dayOff} nowMin={nowMin()} />
        <View style={[s.row, { marginTop: 8 }]}>
          <Seg s={s} value={dayOff} onChange={setDayOff} options={[[0, "Today"], [1, "Tomorrow"]]} />
          <Seg s={s} value={school} onChange={setSchool} options={[[true, "School day"], [false, "No school"]]} />
        </View>
        <Text style={[s.label, { marginTop: 12 }]}>How sure do you want to be?</Text>
        <Seg s={s} value={conf} onChange={setConf} options={[[.8, "80%"], [.9, "90%"], [.95, "95%"]]} />
        <View style={{ marginTop: 14 }}><Btn s={s} kind="solid" label={busy ? "Working it out…" : "When should I leave?"} onPress={run} /></View>
        {active.length > 0 && <Text style={[s.hint, { marginTop: 8 }]}>{active.length} road report{active.length > 1 ? "s" : ""} included.</Text>}
      </View>

      <View style={s.card}>
        <Pressable onPress={() => setShowReport(!showReport)} accessibilityRole="button"><Text style={s.h2}>Road reports {active.length ? `(${active.length})` : ""} {showReport ? "▴" : "▾"}</Text></Pressable>
        {showReport && <ReportBox {...{ s, c, active, reports, setRe }} />}
      </View>

      {res?.err && <View style={s.card}><Text style={s.body}>{res.err}</Text></View>}
      {b && (
        <View onLayout={e => { resY.current = e.nativeEvent.layout.y; }}>
          <Result {...{ s, c, res, b, from, to, arrive, dayOff, conf, school, causes, risk, pl, link, Btn, Pill, Note, RouteMap }} nowMin={nowMin()} mapWidth={Math.min(width - 64, 520)}
            onMaps={() => Linking.openURL(link.url)} onMapsPlain={() => Linking.openURL(link.plain)} onRemind={remind}
            onShare={() => Share.share({ message: msg }).catch(() => {})} onTest={startTest}
            closedNotes={active.filter(r => r.kind === "closed").length ? <Text style={[s.hint, { marginTop: 6 }]}>Avoiding {active.filter(r => r.kind === "closed").map(r => roadName(r.road)).join(", ")} (reported closed).</Text> : null} />
        </View>
      )}

      <PlacePicker visible={!!picker} s={s} c={c} places={places} allowHere={picker === "from"}
        onClose={() => setPicker(null)}
        onHere={() => { setPicker(null); useMyLocation(); }}
        onPick={p => { (picker === "from" ? setFrom : setTo)(p); setPicker(null); }}
        onPin={() => { const w = picker; setPicker(null); setPin({ which: w }); }} />
      <PinMap visible={!!pin} s={s} c={c} width={width} title={pin?.which === "to" ? "Where are you going?" : "Where are you starting?"}
        start={pin ? ((pin.which === "from" ? from : to).ll || NODES[(pin.which === "from" ? from : to).node]) : null}
        onClose={() => setPin(null)}
        onUse={ll => { const n = nearest(ll); const p = { kind: "spot", node: n.name, ll, label: `Pin near ${n.name}`, note: `near ${n.name}, ${n.km < 1 ? "under 1" : n.km.toFixed(1)} km away` }; (pin.which === "from" ? setFrom : setTo)(p); setPin(null); }} />
    </ScrollView>
  );
}
// Ranks what is driving the risk on the advised route, so the advice explains itself.
function riskCauses(b, reports) {
  const out = [];
  const closed = reports.filter(r => r.kind === "closed");
  if (closed.length) out.push({ w: 100, label: "Road closure", detail: `Avoiding ${closed.map(r => roadName(r.road)).join(", ")}, which was reported closed.` });
  const jam = b.busy.filter(x => x.reportedJam);
  if (jam.length) out.push({ w: 90, label: "Reported jam", detail: `${jam[0].road} has a reported jam; it's included in the times.` });
  if (b.schools.length) { const x = b.schools[0]; out.push({ w: 60 + 10 * b.schools.length, label: "School rush", detail: `You pass ${x.road} around ${hm(x.at)}, during school drop-off or pick-up.` }); }
  const inflow = b.busy.filter(x => x.outsideShare > .3 && x.vc > .85).sort((p, q) => q.outsideShare - p.outsideShare);
  if (inflow.length) { const x = inflow[0]; out.push({ w: 50 + 40 * x.outsideShare, label: "Traffic from outside Kuching", detail: `${x.road} is ${Math.round(x.vc * 100)}% full, about ${Math.round(x.outsideShare * 100)}% of it people driving in from ${x.outsideFrom || "nearby areas"}.` }); }
  if (b.vans >= 50) out.push({ w: 40, label: "Crowded by other planned trips", detail: `${b.vans} other planned trips use this route around your time.` });
  const busy = b.busy.filter(x => x.vc > .85 && !(x.outsideShare > .3));
  if (busy.length) { const x = busy.sort((p, q) => q.vc - p.vc)[0]; out.push({ w: 30 + 10 * x.vc, label: "Peak-hour traffic", detail: `${x.road} is ${Math.round(x.vc * 100)}% full when you pass.` }); }
  return out.sort((p, q) => q.w - p.w);
}
const roadName = i => ROADS[i] ? ROADS[i].a + "–" + ROADS[i].b : "?";

function ReportBox({ s, c, active, reports, setRe }) {
  const [road, setRoad] = useState(null);
  const [pick, setPick] = useState(false);
  const add = kind => { if (road === null) { Alert.alert("Pick a road first"); return; } setRe([...reports.filter(r => r.expires > Date.now()), { id: String(Date.now()), road, kind, at: Date.now(), expires: Date.now() + REPORT_MS }]); setRoad(null); };
  return (
    <View style={{ gap: 8, marginTop: 8 }}>
      <Pressable style={s.select} onPress={() => setPick(true)}><Text style={s.selectText}>{road === null ? "Pick a road" : roadName(road)}</Text><Text style={s.chev}>▾</Text></Pressable>
      <View style={s.row}>
        <View style={{ flex: 1 }}><Btn s={s} kind="ghost" label="Closed / accident" onPress={() => add("closed")} /></View>
        <View style={{ flex: 1 }}><Btn s={s} kind="ghost" label="Heavy jam" onPress={() => add("jam")} /></View>
      </View>
      {active.map(r => (
        <View key={r.id} style={s.listRow}>
          <Text style={[s.body, { flex: 1 }]}>{r.kind === "closed" ? "Closed" : "Jam"}: {roadName(r.road)} · {hm(new Date(r.at).getHours() * 60 + new Date(r.at).getMinutes())}</Text>
          <Pressable onPress={() => setRe(reports.filter(x => x.id !== r.id))}><Text style={s.link}>Clear</Text></Pressable>
        </View>
      ))}
      <Text style={s.hint}>Reports last 2 hours and stay on this phone for now. In the full version they're shared with everyone and also come from official notices and traffic feeds.</Text>
      <Sheet visible={pick} onRequestClose={() => setPick(false)} bg={c.bg}>
        <SafeAreaView style={s.fill}>
          <View style={s.modalHead}><Text style={s.h2}>Which road?</Text><Pressable onPress={() => setPick(false)}><Text style={s.link}>Close</Text></Pressable></View>
          <FlatList data={ROADS.map((r, i) => ({ i, name: r.a + "–" + r.b })).sort((a, b) => a.name.localeCompare(b.name))} keyExtractor={x => String(x.i)}
            renderItem={({ item }) => <Pressable style={s.pickRow} onPress={() => { setRoad(item.i); setPick(false); }}><Text style={s.body}>{item.name}</Text></Pressable>} />
        </SafeAreaView>
      </Sheet>
    </View>
  );
}

// Type a place: suggestions appear as you type. Extra words are read as context:
// "7-Eleven near Saradise", "SMK Green Road, Jalan Batu Lintang", "office tmn bdc".
function PlaceField({ s, c, value, places, allowHere, onHere, onPick, onMore }) {
  const [text, setText] = useState(null);           // null = not editing, show the chosen place
  const [online, setOnline] = useState(null);       // null | "busy" | items | { err }
  const editing = text !== null;
  const typed = (text || "").trim();
  const sug = typed.length >= 2 ? suggest(typed, places) : null;
  useEffect(() => {
    setOnline(null);
    if (typed.length < 3) return;
    const id = setTimeout(() => {
      setOnline("busy");
      suggestOnline(typed, places).then(r => setOnline(r)).catch(() => setOnline({ err: true }));
    }, 700);
    return () => clearTimeout(id);
  }, [typed]);
  const close = () => setTimeout(() => setText(null), 180);   // let a tap on a suggestion land first
  const pick = it => { onPick(it); setText(null); };
  const ctx = sug && sug.parsed;
  return (
    <View>
      <View style={[s.select, { paddingRight: 0 }]}>
        <TextInput style={[s.selectText, { minHeight: 44, outlineStyle: "none" }]} value={editing ? text : value.label}
          onFocus={() => setText("")} onBlur={close} onChangeText={setText} placeholder="Type a place, e.g. 7-Eleven near Saradise"
          placeholderTextColor={c.muted} autoCorrect={false} returnKeyType="search"
          onSubmitEditing={() => { const first = (sug && sug.list[0]) || (Array.isArray(online) && online[0]); if (first) pick(first); }} />
        <Pressable onPress={onMore} accessibilityRole="button" accessibilityLabel="Choose from the list or map" style={{ paddingHorizontal: 12, alignSelf: "stretch", justifyContent: "center" }}><Text style={s.chev}>▾</Text></Pressable>
      </View>
      {editing && (
        <View style={{ borderWidth: 1, borderColor: c.line, borderRadius: 10, marginTop: 4, overflow: "hidden", backgroundColor: c.surface }}>
          {ctx && (ctx.near || ctx.road) ? (
            <Text style={[s.hint, { paddingHorizontal: 12, paddingTop: 8 }]}>
              Looking for <Text style={{ fontWeight: "700" }}>{ctx.name || "a place"}</Text>{ctx.road ? <> on/in <Text style={{ fontWeight: "700" }}>{ctx.road}</Text></> : null}{ctx.near ? <> near <Text style={{ fontWeight: "700" }}>{ctx.near}</Text></> : null}{sug.anchor ? ` (found ${sug.anchor.label})` : ""}
            </Text>) : null}
          {!typed && allowHere ? <Pressable style={s.pickRow} onPress={() => { setText(null); onHere(); }}><Text style={[s.body, { color: c.accent, fontWeight: "700" }]}>My current location</Text></Pressable> : null}
          {!typed && places.map((p, i) => <Pressable key={"sv" + i} style={s.pickRow} onPress={() => pick({ kind: "saved", node: nearest(p.ll).name, ll: p.ll, label: p.name, note: `near ${nearest(p.ll).name}` })}><Text style={s.body}>★ {p.name}</Text></Pressable>)}
          {!typed && <Text style={[s.hint, { padding: 12 }]}>Add context to narrow it down: "near …", a road (Jalan …) or a taman.</Text>}
          {sug && sug.list.map((it, i) => <Pressable key={"s" + i} style={s.pickRow} onPress={() => pick(it)}><Text style={s.body}>{it.label}</Text>{it.note ? <Text style={s.hint}>{it.note}</Text> : null}</Pressable>)}
          {typed.length >= 3 && online === "busy" && <View style={[s.pickRow, { flexDirection: "row", gap: 8, alignItems: "center" }]}><ActivityIndicator color={c.accent} /><Text style={s.hint}>Searching OpenStreetMap…</Text></View>}
          {Array.isArray(online) && online.map((it, i) => <Pressable key={"o" + i} style={s.pickRow} onPress={() => pick(it)}><Text style={s.body}>{it.label}</Text><Text style={s.hint}>{it.note} · online</Text></Pressable>)}
          {typed.length >= 3 && online && online.err && <Text style={[s.hint, { padding: 12 }]}>Online search unavailable (no internet). Built-in suggestions only.</Text>}
          {typed ? <Pressable style={s.pickRow} onPress={() => { setText(null); onMore(); }}><Text style={[s.body, { color: c.accent }]}>More: full list or drop a pin…</Text></Pressable> : null}
        </View>
      )}
    </View>
  );
}

function PlaceNote({ s, p, onPin }) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "baseline", gap: 8, marginTop: 4 }}>
      {p.note ? <Text style={[s.hint, { flexShrink: 1 }]}>{p.note}.{p.ll ? " Google Maps uses the exact point." : ""}</Text> : null}
      <Pressable onPress={onPin} accessibilityRole="button"><Text style={[s.link, { fontSize: s.hint.fontSize }]}>{p.ll ? "Adjust pin" : "Pick exact spot"}</Text></Pressable>
    </View>
  );
}

function PlacePicker({ visible, s, c, places, allowHere, onClose, onPick, onHere, onPin }) {
  const [q, setQ] = useState("");
  const [more, setMore] = useState(false);
  const [road, setRoad] = useState("");
  const [near, setNear] = useState("");
  const [online, setOnline] = useState(null);     // null | "busy" | [] | items | { err }
  useEffect(() => { if (visible) { setQ(""); setRoad(""); setNear(""); setOnline(null); setMore(false); } }, [visible]);
  useEffect(() => { setOnline(null); }, [q, road, near]);
  const typed = (q + road + near).trim().length > 0;
  const matches = typed ? searchOffline(q, road + " " + near, places) : [];
  const goOnline = async () => {
    setOnline("busy");
    try { setOnline(await searchOnline(q, road, near)); }
    catch { setOnline({ err: true }); }
  };
  const sections = [
    ...(places.length ? [{ title: "Saved places", items: places.map(p => ({ kind: "saved", node: nearest(p.ll).name, ll: p.ll, label: p.name, note: `near ${nearest(p.ll).name}` })) }] : []),
    { title: "Kuching areas", items: Object.keys(AREAS).map(n => ({ kind: "area", node: n, label: n })) },
    { title: "Around Kuching", items: Object.keys(EXT).map(n => ({ kind: "area", node: n, label: n })) },
  ];
  const Row = ({ it, k }) => <Pressable key={k} style={s.pickRow} onPress={() => onPick(it)}><Text style={s.body}>{it.label}</Text>{it.note ? <Text style={s.hint}>{it.note}</Text> : null}</Pressable>;
  return (
    <Sheet visible={visible} onRequestClose={onClose} bg={c.bg}>
      <SafeAreaView style={s.fill}>
        <View style={s.modalHead}><Text style={s.h2}>Choose a place</Text><Pressable onPress={onClose}><Text style={s.link}>Close</Text></Pressable></View>
        <View style={{ padding: 16, paddingBottom: 4, backgroundColor: c.surface }}>
          <TextInput style={s.input} value={q} onChangeText={setQ} placeholder="Search a place, e.g. Vivacity, UNIMAS, Taman BDC" placeholderTextColor={c.muted} returnKeyType="search" onSubmitEditing={() => q.trim() && goOnline()} autoCorrect={false} />
          {more ? (
            <>
              <TextInput style={s.input} value={road} onChangeText={setRoad} placeholder="Road or taman (optional), e.g. Jalan Stutong" placeholderTextColor={c.muted} autoCorrect={false} />
              <TextInput style={s.input} value={near} onChangeText={setNear} placeholder="Near a landmark (optional), e.g. near Saradise" placeholderTextColor={c.muted} autoCorrect={false} />
            </>
          ) : <Pressable onPress={() => setMore(true)} style={{ paddingBottom: 8 }}><Text style={s.link}>+ Add road or nearby landmark</Text></Pressable>}
        </View>
        <ScrollView keyboardShouldPersistTaps="handled">
          {allowHere && !typed && <Pressable style={s.pickRow} onPress={onHere}><Text style={[s.body, { color: c.accent, fontWeight: "700" }]}>My current location</Text></Pressable>}
          <Pressable style={s.pickRow} onPress={onPin}><Text style={[s.body, { color: c.accent, fontWeight: "700" }]}>Drop a pin on the map</Text><Text style={s.hint}>Tap or drag to the exact spot</Text></Pressable>
          {typed ? (
            <View>
              <Text style={s.sectionHead}>Matches</Text>
              {matches.length ? matches.map((it, i) => <Row key={"m" + i} k={"m" + i} it={it} />) : <Text style={[s.hint, { paddingHorizontal: 16 }]}>No match in the built-in list.</Text>}
              <Text style={s.sectionHead}>Online search (OpenStreetMap)</Text>
              {online === null && <Pressable style={s.pickRow} onPress={goOnline}><Text style={[s.body, { color: c.accent, fontWeight: "700" }]}>Search online for "{[q, road, near].filter(x => x.trim()).join(", ")}"</Text><Text style={s.hint}>Needs internet. Adding a road or landmark helps find the right spot.</Text></Pressable>}
              {online === "busy" && <View style={s.pickRow}><ActivityIndicator color={c.accent} /></View>}
              {online && online.err && <Text style={[s.hint, { paddingHorizontal: 16 }]}>Couldn't search online right now. Pick a match above, an area below, or drop a pin.</Text>}
              {Array.isArray(online) && (online.length ? online.map((it, i) => <Row key={"o" + i} k={"o" + i} it={it} />) : <Text style={[s.hint, { paddingHorizontal: 16 }]}>Nothing found in Greater Kuching. Try fewer words, or drop a pin.</Text>)}
            </View>
          ) : null}
          {sections.map(sec => (
            <View key={sec.title}>
              <Text style={s.sectionHead}>{sec.title}</Text>
              {sec.items.map(it => <Row key={sec.title + it.label} k={sec.title + it.label} it={it} />)}
            </View>
          ))}
        </ScrollView>
      </SafeAreaView>
    </Sheet>
  );
}

// ---------------------------------------------------------------- test trips
function TestScreen({ s, c, trips, setTr }) {
  const open = trips.filter(t => !t.done);
  const done = trips.filter(t => t.done && t.left && t.arrived);
  const patch = (id, p) => setTr(trips.map(t => t.id === id ? { ...t, ...p } : t));
  const onTime = a => a.length ? Math.round(100 * a.filter(t => minOf(t.arrived) <= toMin(t.arriveBy)).length / a.length) + "%" : "—";
  const err = t => minOf(t.arrived) - (minOf(t.left) + toMin(t.plan.etaMid) - toMin(t.plan.leave));
  const errs = done.map(t => Math.abs(err(t))).sort((a, b) => a - b);
  const withStop = trips.filter(t => ["yes", "detour", "no"].includes(t.mapsKept));
  const exportCsv = () => {
    const head = "date,tester,from,to,mode,arrive_by,advised_leave,predicted_arrival,range,left,arrived,error_min,on_time,maps_kept_route,notes";
    const rows = trips.filter(t => t.done).map(t => [t.date, t.tester, t.from, t.to, t.mode, t.arriveBy, t.plan.leave, t.plan.etaMid, `${t.plan.etaLo}-${t.plan.etaHi}`, t.left ? hm(minOf(t.left)) : "", t.arrived ? hm(minOf(t.arrived)) : "", t.left && t.arrived ? err(t) : "", t.arrived ? (minOf(t.arrived) <= toMin(t.arriveBy) ? "yes" : "no") : "", t.mapsKept || "", (t.notes || "").replace(/[\n,]/g, " ")].join(","));
    Share.share({ message: [head, ...rows].join("\n") }).catch(() => {});
  };
  return (
    <ScrollView contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
      <View style={s.statsRow}>
        <Stat s={s} k="Trips done" v={String(done.length)} sub={`${open.length} open`} />
        <Stat s={s} k="On time" v={`${onTime(done.filter(t => t.mode === "follow"))} / ${onTime(done.filter(t => t.mode === "usual"))}`} sub="advice / usual way" />
        <Stat s={s} k="Time error" v={errs.length ? errs[Math.floor(errs.length / 2)] + " min" : "—"} sub="typical, from when you left" />
        <Stat s={s} k="Maps kept route" v={withStop.length ? Math.round(100 * withStop.filter(t => t.mapsKept === "yes").length / withStop.length) + "%" : "—"} sub={`${withStop.filter(t => t.mapsKept === "detour").length} odd detours`} />
      </View>
      {!trips.length && <View style={s.card}><Text style={s.h2}>How the test works</Text><Text style={s.body}>For about a week, swap days: one day follow the advice, the next drive your usual way. Plan the trip, press "Following advice" or "My usual way", then tap "I'm leaving" and "I've arrived" here. The app records the times for you.</Text></View>}
      {open.map(t => <OpenTrip key={t.id} {...{ s, c, t, patch, remove: () => setTr(trips.filter(x => x.id !== t.id)) }} />)}
      {done.length > 0 && (
        <View style={s.card}>
          <Text style={s.h2}>Finished trips</Text>
          {done.map(t => (
            <View key={t.id} style={s.listRow}>
              <View style={{ flex: 1 }}><Text style={s.body}>{t.date} · {t.from} → {t.to}</Text><Text style={s.hint}>{t.mode === "follow" ? "Followed advice" : "Usual way"} · left {hm(minOf(t.left))} · arrived {hm(minOf(t.arrived))} (predicted {t.plan.etaMid})</Text></View>
              <Pill s={s} c={c} tone={minOf(t.arrived) <= toMin(t.arriveBy) ? "ok" : "bad"} text={minOf(t.arrived) <= toMin(t.arriveBy) ? "On time" : "Late"} />
            </View>
          ))}
          <View style={{ marginTop: 10 }}><Btn s={s} kind="ghost" label="Send results (CSV)" onPress={exportCsv} /></View>
        </View>
      )}
    </ScrollView>
  );
}
const toMin = x => { const [h, m] = String(x).split(":").map(Number); return h * 60 + m; };

function OpenTrip({ s, c, t, patch, remove }) {
  const [notes, setNotes] = useState(t.notes || "");
  const leaveNow = async () => { patch(t.id, { left: new Date().toISOString() }); if (t.mode === "follow") Linking.openURL(t.plan.url).catch(() => {}); };
  return (
    <View style={s.card}>
      <View style={[s.row, { justifyContent: "space-between", flexWrap: "wrap" }]}>
        <Text style={s.h2}>{t.from} → {t.to}</Text>
        <Pill s={s} c={c} tone={t.mode === "follow" ? "info" : "warn"} text={t.mode === "follow" ? "Following advice" : "Usual way"} />
      </View>
      <Text style={s.hint}>{t.date} · arrive by {t.arriveBy} · advised: leave {t.plan.leave}, arrive {t.plan.etaLo}–{t.plan.etaHi} via {t.plan.via}</Text>
      {!t.left && <View style={{ marginTop: 10 }}><Btn s={s} kind="solid" label={t.mode === "follow" ? "I'm leaving (opens Google Maps)" : "I'm leaving now"} onPress={leaveNow} /></View>}
      {t.left && !t.arrived && <View style={{ marginTop: 10, gap: 6 }}><Text style={s.body}>Left at {hm(minOf(t.left))}. Drive safely.</Text><Btn s={s} kind="solid" label="I've arrived" onPress={() => patch(t.id, { arrived: new Date().toISOString() })} /></View>}
      {t.left && t.arrived && (
        <View style={{ marginTop: 10, gap: 8 }}>
          <Text style={s.body}>Left {hm(minOf(t.left))}, arrived {hm(minOf(t.arrived))}.</Text>
          {t.mode === "follow" && <>
            <Text style={s.label}>Did Google Maps keep our route?</Text>
            <View style={[s.row, { flexWrap: "wrap" }]}>
              {[["yes", "Yes"], ["detour", "Odd detour"], ["no", "Dropped it"], ["none", "No stop in link"], ["notused", "Didn't use Maps"]].map(([k, l]) => <Btn key={k} s={s} small kind={t.mapsKept === k ? "solid" : "ghost"} label={l} onPress={() => patch(t.id, { mapsKept: k })} />)}
            </View>
          </>}
          <TextInput style={s.input} placeholder="Notes: roads you took, jams, anything odd" placeholderTextColor={c.muted} value={notes} onChangeText={setNotes} multiline />
          <Btn s={s} kind="solid" label="Save trip" onPress={() => patch(t.id, { notes, done: true })} />
        </View>
      )}
      <Pressable onPress={() => Alert.alert("Remove this trip?", "", [{ text: "Keep" }, { text: "Remove", style: "destructive", onPress: remove }])} style={{ marginTop: 10 }}><Text style={[s.link, { color: c.slow }]}>Remove trip</Text></Pressable>
    </View>
  );
}

// ---------------------------------------------------------------- settings
function SettingsScreen({ s, c, settings, upd, places, setPl }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const saveHere = async () => {
    if (!name.trim()) { Alert.alert("Give the place a name first", "For example Home, Office or Mum's house."); return; }
    setBusy(true);
    try {
      const here = await getHere(settings);
      setPl([...places, { name: name.trim(), ll: here.ll }]); setName("");
    } catch (e) { e.denied ? Alert.alert("Location is off", "Allow location to save where you are.") : Alert.alert("Couldn't get your location", "Try again outdoors or with location turned on."); }
    finally { setBusy(false); }
  };
  return (
    <ScrollView contentContainerStyle={s.page} keyboardShouldPersistTaps="handled">
      <View style={s.card}>
        <Text style={s.h2}>You</Text>
        <Text style={s.label}>Nickname for test trips</Text>
        <TextInput style={s.input} value={settings.nick} onChangeText={v => upd("nick", v.slice(0, 24))} placeholder="e.g. Ming" placeholderTextColor={c.muted} />
        <View style={s.switchRow}><Text style={[s.body, { flex: 1 }]}>Large text</Text><Switch value={settings.big} onValueChange={v => upd("big", v)} /></View>
        <Text style={s.hint}>No account needed. Everything here stays on this phone.</Text>
      </View>
      <View style={s.card}>
        <Text style={s.h2}>Saved places</Text>
        {places.map((p, i) => (
          <View key={i} style={s.listRow}>
            <View style={{ flex: 1 }}><Text style={s.body}>{p.name}</Text><Text style={s.hint}>near {nearest(p.ll).name}</Text></View>
            <Pressable onPress={() => setPl(places.filter((_, j) => j !== i))}><Text style={[s.link, { color: c.slow }]}>Remove</Text></Pressable>
          </View>
        ))}
        <TextInput style={s.input} value={name} onChangeText={setName} placeholder="Name, e.g. Home" placeholderTextColor={c.muted} />
        <Btn s={s} kind="ghost" label={busy ? "Finding you…" : "Save where I am now"} onPress={saveHere} />
      </View>
      <View style={s.card}>
        <Text style={s.h2}>Made-up traffic</Text>
        <View style={s.switchRow}><Text style={[s.body, { flex: 1 }]}>People driving in from Samarahan, Siburan, Matang, Samariang, Sejingkat</Text><Switch value={settings.commOn} onValueChange={v => upd("commOn", v)} /></View>
        <View style={s.switchRow}><Text style={[s.body, { flex: 1 }]}>400 delivery vans leaving depots at 7:00</Text><Switch value={settings.vansOn} onValueChange={v => upd("vansOn", v)} /></View>
        <Text style={s.label}>School hours (not confirmed yet)</Text>
        <Seg s={s} value={settings.sess} onChange={v => upd("sess", v)} options={[["morning", "Morning only"], ["both", "Morning + afternoon"]]} />
        <Text style={[s.hint, { marginTop: 8 }]}>This practice version doesn't use live traffic. It estimates traffic from the type of road, the time of day, school hours and the settings above, to test whether the advice is useful before connecting real data.</Text>
      </View>
      <View style={s.card}>
        <Text style={s.h2}>Demo</Text>
        <Text style={s.label}>"My location" pretends I'm at</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {[["", "Off (real GPS)"], ...DEMO_SPOTS.map(n => [n, n])].map(([v, l]) => (
            <Btn key={l} s={s} small kind={(settings.fakeHere || "") === v ? "solid" : "ghost"} label={l} onPress={() => upd("fakeHere", v)} />
          ))}
        </View>
        <Text style={[s.hint, { marginTop: 8 }]}>For presenting indoors or on a laptop. Turn it off for real trips.</Text>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------- small parts
function Btn({ s, label, onPress, kind = "solid", small }) {
  return <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [kind === "solid" ? s.btn : s.btnGhost, small && s.btnSmall, pressed && { opacity: .7 }]}><Text style={[kind === "solid" ? s.btnText : s.btnGhostText, small && { fontSize: s.small.fontSize }]}>{label}</Text></Pressable>;
}
function Pill({ s, c, tone, text }) {
  const m = { ok: [c.okSoft, c.ok], warn: [c.schoolSoft, c.school], bad: [c.slowSoft, c.slow], info: [c.accentSoft, c.accent] }[tone];
  return <View style={[s.pill, { backgroundColor: m[0] }]}><Text style={[s.pillText, { color: m[1] }]}>{text}</Text></View>;
}
function Fact({ s, k, v }) { return <View style={s.fact}><Text style={s.factK}>{k}</Text><Text style={s.factV}>{v}</Text></View>; }
function Note({ s, c, t }) { return <View style={s.note}><View style={[s.dot, { backgroundColor: c }]} /><Text style={[s.body, { flex: 1 }]}>{t}</Text></View>; }
function Stat({ s, k, v, sub }) { return <View style={s.stat}><Text style={s.factK}>{k}</Text><Text style={s.statV}>{v}</Text><Text style={s.hint}>{sub}</Text></View>; }

function makeStyles(c, f) {
  const fs = n => Math.round(n * f);
  return StyleSheet.create({
    fill: { flex: 1, backgroundColor: c.bg },
    header: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6 },
    title: { fontSize: fs(20), fontWeight: "700", color: c.fg },
    badge: { fontSize: fs(12), color: c.school, marginTop: 2 },
    page: { padding: 16, gap: 14, paddingBottom: 40 },
    card: { backgroundColor: c.surface, borderRadius: 14, borderWidth: 1, borderColor: c.line, padding: 14 },
    row: { flexDirection: "row", gap: 8 },
    label: { fontSize: fs(13), color: c.muted, fontWeight: "600", marginBottom: 6 },
    h2: { fontSize: fs(17), fontWeight: "700", color: c.fg, marginBottom: 6 },
    body: { fontSize: fs(15), color: c.fg, lineHeight: fs(21) },
    hint: { fontSize: fs(12.5), color: c.muted, lineHeight: fs(18), marginTop: 4 },
    small: { fontSize: fs(13) },
    mono: { fontSize: fs(13), color: c.fg, fontVariant: ["tabular-nums"] },
    link: { fontSize: fs(15), color: c.accent, fontWeight: "600" },
    select: { flexDirection: "row", alignItems: "center", borderWidth: 1, borderColor: c.line, borderRadius: 10, paddingHorizontal: 12, minHeight: fs(46), backgroundColor: c.surface },
    selectText: { flex: 1, fontSize: fs(16), color: c.fg },
    chev: { color: c.muted, fontSize: fs(14) },
    timeBig: { fontSize: fs(30), fontWeight: "700", color: c.fg, fontVariant: ["tabular-nums"], minWidth: fs(92), textAlign: "center" },
    btn: { backgroundColor: c.accent, borderRadius: 999, minHeight: fs(48), paddingHorizontal: 16, alignItems: "center", justifyContent: "center" },
    btnText: { color: c.accentInk, fontWeight: "700", fontSize: fs(16) },
    btnGhost: { borderWidth: 1.5, borderColor: c.accent, borderRadius: 999, minHeight: fs(46), paddingHorizontal: 14, alignItems: "center", justifyContent: "center" },
    btnGhostText: { color: c.accent, fontWeight: "700", fontSize: fs(15), textAlign: "center" },
    btnSmall: { minHeight: fs(38), paddingHorizontal: 10 },
    seg: { flexDirection: "row", backgroundColor: c.sunk, borderRadius: 12, padding: 3, flex: 1, position: "relative" },
    segThumb: { position: "absolute", top: 3, bottom: 3, left: 3, borderRadius: 9, backgroundColor: c.thumb,
      ...(Platform.OS === "web" ? { boxShadow: "0 1px 2px rgba(16,24,40,.10), 0 2px 6px rgba(16,24,40,.08)" }
        : { shadowColor: "#000", shadowOpacity: .12, shadowRadius: 4, shadowOffset: { width: 0, height: 1 }, elevation: 2 }) },
    segItem: { flex: 1, borderRadius: 9, paddingVertical: fs(8), paddingHorizontal: 4, alignItems: "center", justifyContent: "center", zIndex: 1 },
    segOn: {},
    segText: { fontSize: fs(13.5), color: c.muted, fontWeight: "600", letterSpacing: .1 },
    segTextOn: { color: c.accent, fontWeight: "700" },
    cap: { fontSize: fs(13), color: c.muted, fontWeight: "700", letterSpacing: 1 },
    leave: { fontSize: fs(44), fontWeight: "800", color: c.fg, fontVariant: ["tabular-nums"], marginRight: 6 },
    via: { fontSize: fs(16), fontWeight: "600", color: c.fg, marginTop: 4 },
    pill: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3, alignSelf: "center" },
    pillText: { fontSize: fs(12.5), fontWeight: "700" },
    fact: { flex: 1, backgroundColor: c.sunk, borderRadius: 10, padding: 8 },
    factK: { fontSize: fs(11), color: c.muted, fontWeight: "700", textTransform: "uppercase", letterSpacing: .5 },
    factV: { fontSize: fs(16), fontWeight: "700", color: c.fg, fontVariant: ["tabular-nums"] },
    whyBox: { borderWidth: 1, borderRadius: 10, padding: 12, marginTop: 12, gap: 4, backgroundColor: c.accentSoft },
    notes: { borderWidth: 1, borderColor: c.line, borderRadius: 10, marginVertical: 12 },
    note: { flexDirection: "row", gap: 10, padding: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.line },
    dot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
    listRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10, paddingHorizontal: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: c.line, borderRadius: 6 },
    input: { borderWidth: 1, borderColor: c.line, borderRadius: 10, padding: 10, fontSize: fs(15), color: c.fg, marginBottom: 8, minHeight: fs(44) },
    switchRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 8 },
    statsRow: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
    stat: { backgroundColor: c.surface, borderWidth: 1, borderColor: c.line, borderRadius: 12, padding: 10, flexBasis: "47%", flexGrow: 1 },
    statV: { fontSize: fs(20), fontWeight: "800", color: c.fg, fontVariant: ["tabular-nums"] },
    tabs: { flexDirection: "row", borderTopWidth: 1, borderTopColor: c.line, backgroundColor: c.surface },
    tab: { flex: 1, alignItems: "center", paddingVertical: 10, gap: 4 },
    tabDot: { width: 22, height: 4, borderRadius: 2, backgroundColor: "transparent" },
    tabText: { fontSize: fs(13), color: c.muted },
    modalHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16, borderBottomWidth: 1, borderBottomColor: c.line, backgroundColor: c.surface },
    sectionHead: { fontSize: fs(12), fontWeight: "700", color: c.muted, textTransform: "uppercase", letterSpacing: .6, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 6 },
    pickRow: { paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: c.line, backgroundColor: c.surface },
  });
}
