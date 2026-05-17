import * as SecureStore from "expo-secure-store";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";
import { Text } from "@/src/components/Text";

import { authenticate, getBiometricType } from "@/src/utils/biometrics";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";

export default function BiometricScreen() {
  const router                       = useRouter();
  const { setAuth, setBiometricPending } = useStore();

  const [bioType,  setBioType]  = useState<"face" | "fingerprint" | "none">("fingerprint");
  const [loading,  setLoading]  = useState(true);
  const [failed,   setFailed]   = useState(false);
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    getBiometricType().then((t) => {
      setBioType(t);
      setLoading(false);
      triggerAuth();
    });
  }, []);

  const triggerAuth = async () => {
    setFailed(false);
    const success = await authenticate();
    if (success) {
      const token = await SecureStore.getItemAsync("bp_token");
      if (token) {
        setAuth(token, { id: "", name: "", phone: "" });
        router.replace("/(tabs)");
      } else {
        goToLogin();
      }
    } else {
      setFailed(true);
      setAttempts((a) => a + 1);
    }
  };

  const goToLogin = () => {
    setBiometricPending(false);
    router.replace("/login");
  };

  const icon  = bioType === "face" ? "🤳" : "👆";
  const label = bioType === "face" ? "Rostro"        : "Huella digital";
  const hint  = bioType === "face" ? "Mira a la cámara para entrar" : "Toca el sensor para entrar";

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>

      <Image
        source={require("@/assets/images/logo.png")}
        style={styles.logo}
        resizeMode="contain"
      />
      <Text style={styles.brand}>BananaPay</Text>

      <View style={[styles.circle, failed && styles.circleFailed]}>
        <Text style={styles.icon}>{icon}</Text>
      </View>

      <Text style={styles.title}>
        {failed ? "No se pudo verificar" : label}
      </Text>
      <Text style={styles.subtitle}>
        {failed
          ? attempts >= 3
            ? "Demasiados intentos. Usa tu PIN."
            : "Inténtalo de nuevo o usa tu PIN."
          : hint}
      </Text>

      {attempts < 3 && (
        <TouchableOpacity style={styles.primaryBtn} onPress={triggerAuth}>
          <Text style={styles.primaryBtnText}>
            {failed ? "Reintentar" : `Usar ${label}`}
          </Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity style={styles.secondaryBtn} onPress={goToLogin}>
        <Text style={styles.secondaryBtnText}>Iniciar sesión con PIN</Text>
      </TouchableOpacity>

    </View>
  );
}

const styles = StyleSheet.create({
  container:      { flex: 1, backgroundColor: C.bg, alignItems: "center", justifyContent: "center", paddingHorizontal: 36 },
  logo:           { width: 80, height: 80, marginBottom: 8 },
  brand:          { fontSize: 20, fontWeight: "700", color: C.text, marginBottom: 56, letterSpacing: -0.3 },

  circle:         { width: 112, height: 112, borderRadius: 56, backgroundColor: C.bgAlt, borderWidth: 2, borderColor: C.accent, justifyContent: "center", alignItems: "center", marginBottom: 28, ...C.shadow },
  circleFailed:   { borderColor: C.danger },
  icon:           { fontSize: 52 },

  title:          { fontSize: 22, fontWeight: "700", color: C.text, marginBottom: 10, textAlign: "center", letterSpacing: -0.3 },
  subtitle:       { fontSize: 15, color: C.textSub, textAlign: "center", marginBottom: 48, lineHeight: 22 },

  primaryBtn:     { backgroundColor: C.accent, borderRadius: 14, paddingVertical: 16, paddingHorizontal: 52, marginBottom: 14 },
  primaryBtnText: { fontSize: 16, fontWeight: "700", color: "#000" },

  secondaryBtn:     { paddingVertical: 12 },
  secondaryBtnText: { fontSize: 15, color: C.textSub },
});
