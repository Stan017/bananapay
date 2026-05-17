import * as SecureStore from "expo-secure-store";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Text } from "@/src/components/Text";

import { login } from "@/src/services/api";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";
import {
  authenticate,
  enableBiometric,
  getBiometricType,
  isBiometricAvailable,
} from "@/src/utils/biometrics";
import { registerForPushNotifications } from "@/src/utils/notifications";

// ─── Credenciales de desarrollo (solo visibles en __DEV__) ───────────────────
const DEV_CEDULA = "0928732494";
const DEV_PHONE  = "0997097262";
const DEV_PIN    = "001704";

export default function LoginScreen() {
  const router  = useRouter();
  const setAuth = useStore((s) => s.setAuth);

  const [cedula,  setCedula]  = useState("");
  const [phone,   setPhone]   = useState("");
  const [pin,     setPin]     = useState("");
  const [loading, setLoading] = useState(false);

  const offerBiometric = async () => {
    const available = await isBiometricAvailable();
    if (!available) return;
    const bioType = await getBiometricType();
    const label   = bioType === "face" ? "rostro (Face ID)" : "huella digital";
    Alert.alert(
      "Acceso más rápido",
      `¿Quieres entrar con tu ${label} la próxima vez?`,
      [
        { text: "Ahora no", style: "cancel" },
        {
          text: "Activar",
          onPress: async () => {
            const ok = await authenticate();
            if (ok) {
              await enableBiometric();
              Alert.alert("Activado", `Desde ahora entra con tu ${label}.`);
            }
          },
        },
      ],
    );
  };

  const handleLogin = async () => {
    const cleanCedula = cedula.trim();
    const cleanPhone  = phone.trim();
    const cleanPin    = pin.replace(/\D/g, ""); // solo dígitos, sin espacios ni puntos

    if (!cleanCedula || !cleanPhone || cleanPin.length < 6) {
      Alert.alert("Campos incompletos", "Ingresa tu cédula, teléfono y PIN de 6 dígitos.");
      return;
    }
    setLoading(true);
    try {
      const data = await login(cleanCedula, cleanPhone, cleanPin);
      await SecureStore.setItemAsync("bp_token", data.token);
      setAuth(data.token, { id: data.user_id, name: data.name, phone: data.phone });
      registerForPushNotifications().catch(() => {});
      offerBiometric();
      router.replace("/(tabs)");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Error al iniciar sesión";
      Alert.alert("Error", msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* ── Top amarillo ── */}
        <View style={styles.topSection}>
          {/* Círculos decorativos */}
          <View style={[styles.circle, { width: 200, height: 200, top: -80, right: -60, opacity: 0.15 }]} />
          <View style={[styles.circle, { width: 140, height: 140, top: 20,  right: 60,  opacity: 0.10 }]} />

          <Image
            source={require("@/assets/images/logo.png")}
            style={styles.logo}
            resizeMode="contain"
          />
          <Text style={styles.brand}>BananaPay</Text>
          <Text style={styles.tagline}>Tu plata, donde la necesitas.</Text>
        </View>

        {/* ── Card blanca con form ── */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Ingresar</Text>
          <Text style={styles.cardSub}>Accede con tus datos de registro</Text>

          {/* Cédula */}
          <Text style={styles.label}>Cédula</Text>
          <View style={styles.inputWrap}>
            <Text style={styles.inputIcon}>🪪</Text>
            <TextInput
              style={styles.input}
              placeholder="10 dígitos"
              placeholderTextColor={C.textTertiary}
              keyboardType="numeric"
              value={cedula}
              onChangeText={setCedula}
              maxLength={10}
            />
          </View>

          {/* Teléfono */}
          <Text style={styles.label}>Teléfono</Text>
          <View style={styles.inputWrap}>
            <Text style={styles.inputIcon}>📱</Text>
            <TextInput
              style={styles.input}
              placeholder="09XXXXXXXX"
              placeholderTextColor={C.textTertiary}
              keyboardType="phone-pad"
              value={phone}
              onChangeText={setPhone}
              maxLength={13}
            />
          </View>

          {/* PIN */}
          <Text style={styles.label}>PIN de seguridad</Text>
          <View style={styles.inputWrap}>
            <Text style={styles.inputIcon}>🔑</Text>
            <TextInput
              style={[styles.input, styles.pinInput]}
              placeholder="● ● ● ● ● ●"
              placeholderTextColor={C.textTertiary}
              keyboardType="number-pad"
              secureTextEntry
              value={pin}
              onChangeText={(t) => setPin(t.replace(/\D/g, ""))}
              maxLength={6}
              textContentType="oneTimeCode"
            />
          </View>

          {/* Botón */}
          <TouchableOpacity
            style={[styles.btn, loading && styles.btnDisabled]}
            onPress={handleLogin}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading
              ? <ActivityIndicator color="#000" />
              : <Text style={styles.btnText}>Ingresar →</Text>
            }
          </TouchableOpacity>

          {/* Botón dev — solo en desarrollo */}
          {__DEV__ && (
            <TouchableOpacity
              style={styles.devBtn}
              onPress={() => {
                setCedula(DEV_CEDULA);
                setPhone(DEV_PHONE);
                setPin(DEV_PIN);
              }}
              activeOpacity={0.7}
            >
              <Text style={styles.devBtnText}>⚡ Dev Login</Text>
            </TouchableOpacity>
          )}

          <Text style={styles.hint}>
            ¿No tienes cuenta? Escríbenos por{" "}
            <Text
              style={styles.hintLink}
              onPress={() =>
                Linking.openURL(
                  "https://wa.me/593989006527?text=Hola%2C+quiero+registrarme+en+BananaPay"
                )
              }
            >
              WhatsApp
            </Text>{" "}
            para registrarte.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root:   { flex: 1, backgroundColor: C.accent },
  scroll: { flexGrow: 1 },

  // Top amarillo
  topSection: {
    backgroundColor: C.accent,
    paddingTop:      72,
    paddingBottom:   48,
    paddingHorizontal: 32,
    alignItems:      "center",
    overflow:        "hidden",
    position:        "relative",
  },
  circle: {
    position:     "absolute",
    borderRadius: 999,
    backgroundColor: "#000",
  },
  logo:    { width: 80, height: 80, marginBottom: 14, zIndex: 1 },
  brand:   { fontSize: 32, fontWeight: "900", color: "#000", letterSpacing: -1, zIndex: 1 },
  tagline: { fontSize: 15, color: "#00000080", marginTop: 4, fontWeight: "500", zIndex: 1 },

  // Card blanca
  card: {
    flex:             1,
    backgroundColor:  C.bg,
    borderTopLeftRadius:  32,
    borderTopRightRadius: 32,
    paddingHorizontal: 28,
    paddingTop:        36,
    paddingBottom:     40,
    minHeight:         480,
  },
  cardTitle: { fontSize: 26, fontWeight: "900", color: C.text, letterSpacing: -0.8, marginBottom: 4 },
  cardSub:   { fontSize: 14, color: C.textSub, marginBottom: 28 },

  label: {
    fontSize:    12,
    fontWeight:  "700",
    color:       C.textSub,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom:  8,
    marginTop:     16,
  },

  inputWrap: {
    flexDirection:    "row",
    alignItems:       "center",
    backgroundColor:  C.bgAlt,
    borderRadius:     14,
    paddingHorizontal: 14,
    borderWidth:       1.5,
    borderColor:       C.border,
  },
  inputIcon: { fontSize: 18, marginRight: 10 },
  input: {
    flex:          1,
    paddingVertical: 15,
    fontSize:      16,
    color:         C.text,
  },
  pinInput: { letterSpacing: 6 },

  btn: {
    backgroundColor: C.accent,
    borderRadius:    16,
    paddingVertical: 18,
    alignItems:      "center",
    marginTop:       28,
    ...C.shadow,
  },
  btnDisabled: { opacity: 0.6 },
  btnText:     { fontSize: 17, fontWeight: "800", color: "#000", letterSpacing: -0.3 },

  hint:     { fontSize: 13, color: C.textSub, textAlign: "center", marginTop: 20, lineHeight: 20 },
  hintLink: { color: C.accentDark, fontWeight: "700" },

  // Dev only
  devBtn:     { marginTop: 12, borderWidth: 1.5, borderColor: "#e5e5e5", borderRadius: 12, paddingVertical: 10, alignItems: "center", borderStyle: "dashed" },
  devBtnText: { fontSize: 13, fontWeight: "700", color: C.textTertiary, letterSpacing: 0.3 },
});
