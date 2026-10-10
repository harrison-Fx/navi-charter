// Web-only stand-ins for phone features, used by the browser backup demo.
// On Android/iOS everything passes straight through to React Native.
import React, { useEffect, useState } from "react";
import { Alert as RNAlert, Share as RNShare, Platform, View, Text, Pressable } from "react-native";

const WEB = Platform.OS === "web";
let push = null;                       // set by <Toast/>
const show = t => { if (push) push(t); };

export const Alert = {
  alert(title, msg = "", buttons) {
    if (!WEB) return RNAlert.alert(title, msg, buttons);
    show({ title, msg, buttons: buttons && buttons.length > 1 ? buttons : null });
  },
};

export const Share = {
  async share({ message }) {
    if (!WEB) return RNShare.share({ message });
    try { await navigator.clipboard.writeText(message); show({ title: "Message copied", msg: "On the phone this opens WhatsApp / share. Paste it anywhere." }); }
    catch { show({ title: "Message", msg: message }); }
  },
};

export const isWeb = WEB;
export const webToast = show;

export function Toast({ c }) {
  const [t, setT] = useState(null);
  useEffect(() => { push = x => setT(x); return () => { push = null; }; }, []);
  useEffect(() => { if (t && !t.buttons) { const id = setTimeout(() => setT(null), 4000); return () => clearTimeout(id); } }, [t]);
  if (!WEB || !t) return null;
  return (
    <View style={{ position: "absolute", left: 16, right: 16, bottom: 86, backgroundColor: c.fg, borderRadius: 14, padding: 14, gap: 6, zIndex: 50 }}>
      <Text style={{ color: c.bg, fontWeight: "700", fontSize: 16 }}>{t.title}</Text>
      {t.msg ? <Text style={{ color: c.bg, fontSize: 14, lineHeight: 20 }}>{t.msg}</Text> : null}
      <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: 18, marginTop: 4 }}>
        {(t.buttons || [{ text: "OK" }]).map(b => (
          <Pressable key={b.text} onPress={() => { setT(null); b.onPress && b.onPress(); }}>
            <Text style={{ color: b.style === "destructive" ? "#F07B7B" : c.accentSoft, fontWeight: "700", fontSize: 15 }}>{b.text}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

