import { Stack } from "expo-router";
import * as Device from "expo-device";
import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";
import { Alert, BackHandler, Platform } from "react-native";
import {
  Outfit_400Regular,
  Outfit_500Medium,
  Outfit_600SemiBold,
  Outfit_700Bold,
  Outfit_800ExtraBold,
  Outfit_900Black,
} from "@expo-google-fonts/outfit";
import { useFonts } from "expo-font";

import { isBiometricAvailable, isBiometricEnabled } from "@/src/utils/biometrics";
import { registerForPushNotifications } from "@/src/utils/notifications";
import { useStore } from "@/src/store/useStore";

export default function RootLayout() {
  const { setAuth, setBiometricPending } = useStore();
  const [ready,        setReady]        = useState(false);
  const [compromised,  setCompromised]  = useState(false);

  const [fontsLoaded] = useFonts({
    Outfit_400Regular,
    Outfit_500Medium,
    Outfit_600SemiBold,
    Outfit_700Bold,
    Outfit_800ExtraBold,
    Outfit_900Black,
  });

  useEffect(() => {
    (async () => {
      // ── Jailbreak / root detection ────────────────────────────────────────
      // Solo en dispositivo físico — simuladores siempre devuelven false
      if (Device.isDevice) {
        const rooted = await Device.isRootedExperimentalAsync();
        if (rooted) {
          setCompromised(true);
          Alert.alert(
            "Dispositivo no seguro",
            "BananaPay no puede ejecutarse en dispositivos con jailbreak o root. " +
            "Tus datos financieros podrían estar en riesgo.",
            [{
              text: "Cerrar app",
              style: "destructive",
              onPress: () => {
                if (Platform.OS === "android") BackHandler.exitApp();
                // En iOS no se puede cerrar programáticamente — el alert persiste
              },
            }],
            { cancelable: false },
          );
          setReady(true);
          return; // No inicializar sesión en dispositivo comprometido
        }
      }

      // ── Sesión existente ──────────────────────────────────────────────────
      const token = await SecureStore.getItemAsync("bp_token");

      if (token) {
        const bioEnabled   = await isBiometricEnabled();
        const bioAvailable = await isBiometricAvailable();

        if (bioEnabled && bioAvailable) {
          setBiometricPending(true);
        } else {
          setAuth(token, { id: "", name: "", phone: "" });
          // Registrar push token después de restaurar sesión
          registerForPushNotifications().catch(() => {});
        }
      }

      setReady(true);
    })();
  }, []);

  // Pantalla en blanco mientras detectamos — no renderizar nada en dispositivo comprometido
  if (!ready || !fontsLoaded || compromised) return null;

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="login"    />
      <Stack.Screen name="(tabs)"   />
      <Stack.Screen name="send"     />
      <Stack.Screen name="qr"       />
      <Stack.Screen name="deposit"  />
      <Stack.Screen name="withdraw" />
    </Stack>
  );
}
