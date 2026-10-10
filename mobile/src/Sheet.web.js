// Full-screen sheet (browser demo): drawn over the app's own root so it stays inside the
// phone frame and always covers the screen, whatever is scrolled underneath.
import React from "react";
import { createPortal } from "react-dom";
import { View } from "react-native";
export default function Sheet({ visible, bg, children }) {
  if (!visible || typeof document === "undefined") return null;
  const host = document.querySelector("#root > div") || document.body;
  return createPortal(
    <View style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, zIndex: 100, backgroundColor: bg }}>{children}</View>, host);
}
