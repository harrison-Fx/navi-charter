// Segmented toggle with a thumb that slides to the chosen option.
import React, { useEffect, useRef, useState } from "react";
import { View, Text, Pressable, Animated, Platform } from "react-native";

export default function Seg({ s, value, onChange, options, style }) {
  const [w, setW] = useState(0);
  const n = options.length;
  const idx = Math.max(0, options.findIndex(([v]) => v === value));
  const x = useRef(new Animated.Value(idx)).current;
  useEffect(() => {
    Animated.spring(x, { toValue: idx, useNativeDriver: Platform.OS !== "web", speed: 20, bounciness: 3 }).start();
  }, [idx]);
  const PAD = 3, itemW = w ? (w - PAD * 2) / n : 0;
  const tx = n > 1 ? x.interpolate({ inputRange: [0, n - 1], outputRange: [0, itemW * (n - 1)] }) : 0;
  return (
    <View style={[s.seg, style]} onLayout={e => setW(e.nativeEvent.layout.width)}>
      {w > 0 && <Animated.View pointerEvents="none" style={[s.segThumb, { width: itemW, transform: [{ translateX: tx }] }]} />}
      {options.map(([v, l]) => {
        const on = v === value;
        return (
          <Pressable key={String(v)} onPress={() => onChange(v)} style={s.segItem}
            accessibilityRole="radio" accessibilityState={{ selected: on }} accessibilityLabel={l}>
            <Text style={[s.segText, on && s.segTextOn]} numberOfLines={1}>{l}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}
