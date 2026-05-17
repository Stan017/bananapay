import * as Clipboard from "expo-clipboard";
import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";
import { Text } from "@/src/components/Text";

import { getProfile } from "@/src/services/api";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";
import {
  authenticate,
  disableBiometric,
  enableBiometric,
  getBiometricType,
  isBiometricAvailable,
  isBiometricEnabled,
} from "@/src/utils/biometrics";

interface Profile {
  id:             string;
  name:           string;
  phone:          string;
  cedula:         string;
  email:          string | null;
  kyc_level:      number;
  custody_mode:   string;
  wallet_address: string | null;
  created_at:     string;
}

const KYC_LABELS: Record<number, { label: string; color: string }> = {
  0: { label: "Básico",     color: "#f59e0b" },
  1: { label: "Verificado", color: C.success  },
  2: { label: "Premium",    color: C.indigo   },
};

export default function ProfileScreen() {
  const { logout } = useStore();
  const [profile,      setProfile]      = useState<Profile | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [bioEnabled,   setBioEnabled]   = useState(false);
  const [bioAvailable, setBioAvailable] = useState(false);

  useEffect(() => {
    getProfile()
      .then(setProfile)
      .catch(() => Alert.alert("Error", "No se pudo cargar el perfil"))
      .finally(() => setLoading(false));

    Promise.all([isBiometricAvailable(), isBiometricEnabled()]).then(
      ([available, enabled]) => {
        setBioAvailable(available);
        setBioEnabled(enabled);
      },
    );
  }, []);

  const handleLogout = () => {
    Alert.alert("Cerrar sesión", "¿Seguro que quieres salir?", [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Salir",
        style: "destructive",
        onPress: async () => {
          await SecureStore.deleteItemAsync("bp_token");
          logout();
        },
      },
    ]);
  };

  const copyWallet = async () => {
    if (!profile?.wallet_address) return;
    await Clipboard.setStringAsync(profile.wallet_address);
    Alert.alert("Copiado", "Dirección copiada al portapapeles");
  };

  const toggleBiometric = async () => {
    if (bioEnabled) {
      Alert.alert(
        "Desactivar biométrico",
        "¿Seguro? Necesitarás cédula + PIN para entrar.",
        [
          { text: "Cancelar", style: "cancel" },
          {
            text: "Desactivar",
            style: "destructive",
            onPress: async () => { await disableBiometric(); setBioEnabled(false); },
          },
        ],
      );
    } else {
      const bioType = await getBiometricType();
      const label   = bioType === "face" ? "rostro" : "huella digital";
      const ok      = await authenticate();
      if (ok) {
        await enableBiometric();
        setBioEnabled(true);
        Alert.alert("Activado", `Ahora puedes entrar con tu ${label}.`);
      }
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  if (!profile) return null;

  const kyc    = KYC_LABELS[profile.kyc_level] ?? KYC_LABELS[0];
  const joined = new Date(profile.created_at).toLocaleDateString("es-EC", {
    day: "2-digit", month: "long", year: "numeric",
  });

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>

      {/* Avatar + nombre */}
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {profile.name?.charAt(0).toUpperCase()}
          </Text>
        </View>
        <Text style={styles.name}>{profile.name}</Text>
        <Text style={styles.phone}>{profile.phone}</Text>
        <View style={[styles.kycBadge, { backgroundColor: kyc.color + "18", borderColor: kyc.color + "40" }]}>
          <Text style={[styles.kycText, { color: kyc.color }]}>
            KYC {kyc.label}
          </Text>
        </View>
      </View>

      {/* Info personal */}
      <Text style={styles.sectionTitle}>Información personal</Text>
      <View style={styles.section}>
        <Row label="Nombre"        value={profile.name} />
        <Row label="Cédula"        value={profile.cedula} mono />
        <Row label="Teléfono"      value={profile.phone} mono />
        <Row label="Email"         value={profile.email || "No registrado"} />
        <Row label="Tipo de cuenta" value={profile.custody_mode === "custodial" ? "Custodial" : "Self-custody"} />
        <Row label="Miembro desde" value={joined} last />
      </View>

      {/* Wallet crypto */}
      {profile.wallet_address && (
        <>
          <Text style={styles.sectionTitle}>Wallet TRC-20</Text>
          <View style={styles.section}>
            <TouchableOpacity style={styles.walletBox} onPress={copyWallet} activeOpacity={0.7}>
              <Text style={styles.walletLabel}>USDT / USDC · Red TRC-20</Text>
              <Text style={styles.walletAddress} numberOfLines={1} ellipsizeMode="middle">
                {profile.wallet_address}
              </Text>
              <Text style={styles.walletCopy}>Toca para copiar 📋</Text>
            </TouchableOpacity>
            <View style={styles.warningRow}>
              <Text style={styles.warningText}>
                ⚠️  Solo envía desde la red TRC-20. Otra red puede resultar en pérdida permanente.
              </Text>
            </View>
          </View>
        </>
      )}

      {/* Seguridad */}
      <Text style={styles.sectionTitle}>Seguridad</Text>
      <View style={styles.section}>
        {bioAvailable && (
          <MenuItem
            icon="👆"
            label={bioEnabled ? "Desactivar biométrico" : "Activar huella / rostro"}
            right={bioEnabled ? <Text style={styles.onBadge}>Activo</Text> : undefined}
            onPress={toggleBiometric}
          />
        )}
        <MenuItem icon="🔑" label="Cambiar PIN" />
        <MenuItem icon="🆘" label="Contactar soporte" last />
      </View>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Cerrar sesión</Text>
      </TouchableOpacity>

      <Text style={styles.version}>BananaPay v1.0.0 🍌</Text>

    </ScrollView>
  );
}

/* ─── Componentes internos ─── */

function Row({ label, value, mono, last }: { label: string; value: string; mono?: boolean; last?: boolean }) {
  return (
    <View style={[styles.row, last && styles.rowLast]}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, mono && styles.rowMono]} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function MenuItem({
  icon, label, right, onPress, last,
}: {
  icon: string; label: string; right?: React.ReactNode; onPress?: () => void; last?: boolean;
}) {
  return (
    <TouchableOpacity style={[styles.menuItem, last && styles.rowLast]} onPress={onPress} activeOpacity={0.6}>
      <Text style={styles.menuIcon}>{icon}</Text>
      <Text style={styles.menuLabel}>{label}</Text>
      <View style={styles.menuRight}>
        {right ?? <Text style={styles.chevron}>›</Text>}
      </View>
    </TouchableOpacity>
  );
}

/* ─── Estilos ─── */

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: C.bgAlt },
  content:     { paddingBottom: 48 },
  center:      { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.bgAlt },

  // Header
  header:      { alignItems: "center", paddingTop: 60, paddingBottom: 28, paddingHorizontal: 24, backgroundColor: C.bg, marginBottom: 28 },
  avatar:      { width: 84, height: 84, borderRadius: 42, backgroundColor: C.accent, justifyContent: "center", alignItems: "center", marginBottom: 14, ...C.shadow },
  avatarText:  { fontSize: 38, fontWeight: "800", color: "#000" },
  name:        { fontSize: 22, fontWeight: "700", color: C.text, letterSpacing: -0.3, marginBottom: 4 },
  phone:       { fontSize: 14, color: C.textSub, marginBottom: 12 },
  kycBadge:    { borderWidth: 1, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5 },
  kycText:     { fontSize: 13, fontWeight: "600" },

  // Secciones
  sectionTitle:{ fontSize: 13, fontWeight: "600", color: C.textSub, marginHorizontal: 24, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.4 },
  section:     { backgroundColor: C.bg, borderRadius: 16, marginHorizontal: 20, marginBottom: 28, overflow: "hidden", ...C.shadow },

  // Rows de info
  row:         { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  rowLast:     { borderBottomWidth: 0 },
  rowLabel:    { fontSize: 15, color: C.text },
  rowValue:    { fontSize: 15, color: C.textSub, maxWidth: "55%", textAlign: "right" },
  rowMono:     { fontFamily: "monospace", fontSize: 13 },

  // Wallet
  walletBox:   { padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  walletLabel: { fontSize: 12, fontWeight: "600", color: C.textSub, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.3 },
  walletAddress:{ fontSize: 14, color: C.text, fontFamily: "monospace", marginBottom: 6 },
  walletCopy:  { fontSize: 12, color: C.textSub },
  warningRow:  { paddingHorizontal: 16, paddingVertical: 12 },
  warningText: { fontSize: 12, color: C.textSub, lineHeight: 18 },

  // Menu items de seguridad
  menuItem:    { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  menuIcon:    { fontSize: 18, marginRight: 12 },
  menuLabel:   { fontSize: 15, color: C.text, flex: 1 },
  menuRight:   { alignItems: "flex-end" },
  chevron:     { fontSize: 20, color: C.textTertiary },
  onBadge:     { fontSize: 13, fontWeight: "600", color: C.success },

  // Logout
  logoutBtn:   { margin: 20, backgroundColor: C.bg, borderRadius: 16, paddingVertical: 17, alignItems: "center", ...C.shadow },
  logoutText:  { fontSize: 16, color: C.danger, fontWeight: "600" },

  version:     { textAlign: "center", fontSize: 12, color: C.textTertiary, marginBottom: 16 },
});
