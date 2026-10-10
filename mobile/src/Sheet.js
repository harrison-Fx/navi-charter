// Full-screen sheet (phone): a normal Modal. The web build uses Sheet.web.js instead.
import React from "react";
import { Modal } from "react-native";
export default function Sheet({ visible, onRequestClose, children }) {
  return <Modal visible={visible} animationType="slide" onRequestClose={onRequestClose}>{children}</Modal>;
}
