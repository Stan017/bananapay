/**
 * Drop-in replacement de React Native's Text.
 * Mapea fontWeight → variante correcta de Outfit automáticamente.
 * Uso: import { Text } from "@/src/components/Text"
 */
import { Text as RNText, TextProps, StyleSheet } from "react-native";

const WEIGHT_MAP: Record<string, string> = {
  "100": "Outfit_100Thin",
  "200": "Outfit_200ExtraLight",
  "300": "Outfit_300Light",
  "400": "Outfit_400Regular",
  "500": "Outfit_500Medium",
  "600": "Outfit_600SemiBold",
  "700": "Outfit_700Bold",
  "800": "Outfit_800ExtraBold",
  "900": "Outfit_900Black",
  "normal": "Outfit_400Regular",
  "bold":   "Outfit_700Bold",
};

export function Text({ style, ...props }: TextProps) {
  const flat   = StyleSheet.flatten(style) ?? {};
  const weight = String(flat.fontWeight ?? "400");
  const family = WEIGHT_MAP[weight] ?? "Outfit_400Regular";

  return (
    <RNText
      style={[style, { fontFamily: family, fontWeight: undefined }]}
      {...props}
    />
  );
}
