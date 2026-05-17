import * as Clipboard from "expo-clipboard";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { Text } from "@/src/components/Text";

import { getDepositInfo, requestFiatDeposit } from "@/src/services/api";
import { C } from "@/src/theme/colors";

type Tab = "USD" | "CRYPTO";

interface DepositInfo {
  bank: {
    name:    string | null;
    account: string | null;
    holder:  string | null;
    type:    string;
  };
  wallet_address: string | null;
}

const BANKS = [
  "Banco Pichincha",
  "Banco Guayaquil",
  "Banco Pacífico",
  "Produbanco",
  "Banco Internacional",
  "Banco del Austro",
  "Banco Bolivariano",
  "Otro",
];

export default function DepositScreen() {
  const router = useRouter();

  const [tab,       setTab]       = useState<Tab>("USD");
  const [info,      setInfo]      = useState<DepositInfo | null>(null);
  const [loading,   setLoading]   = useState(true);

  // Form USD
  const [amount,    setAmount]    = useState("");
  const [bankName,  setBankName]  = useState("");
  const [reference, setReference] = useState("");
  const [sending,   setSending]   = useState(false);
  const [showBanks, setShowBanks] = useState(false);

  useEffect(() => {
    getDepositInfo()
      .then(setInfo)
      .catch(() => Alert.alert("Error", "No se pudo cargar la información de depósito."))
      .finally(() => setLoading(false));
  }, []);

  const copyWallet = async () => {
    if (!info?.wallet_address) return;
    await Clipboard.setStringAsync(info.wallet_address);
    Alert.alert("Copiado", "Dirección copiada al portapapeles 📋");
  };

  const handleFiatDeposit = async () => {
    const val = parseFloat(amount.replace(",", "."));
    if (!val || val < 1) {
      Alert.alert("Monto inválido", "El monto mínimo es $1.00");
      return;
    }
    if (!bankName) {
      Alert.alert("Banco requerido", "Selecciona el banco desde el que transferiste.");
      return;
    }
    if (!reference.trim()) {
      Alert.alert("Referencia requerida", "Ingresa el número de referencia de tu transferencia.");
      return;
    }

    setSending(true);
    try {
      await requestFiatDeposit({
        amount:           val,
        bank_name:        bankName,
        reference_number: reference.trim(),
      });
      Alert.alert(
        "¡Solicitud enviada! 🍌",
        "Revisaremos tu depósito y lo acreditaremos en máximo 30 minutos en horario laboral.",
        [{ text: "OK", onPress: () => router.back() }],
      );
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Error al enviar la solicitud.";
      Alert.alert("Error", msg);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backText}>‹</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Depositar</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, tab === "USD" && styles.tabActive]}
          onPress={() => setTab("USD")}
        >
          <Text style={[styles.tabText, tab === "USD" && styles.tabTextActive]}>
            🏦  USD
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === "CRYPTO" && styles.tabActive]}
          onPress={() => setTab("CRYPTO")}
        >
          <Text style={[styles.tabText, tab === "CRYPTO" && styles.tabTextActive]}>
            🪙  USDT / USDC
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        {/* ── TAB USD ── */}
        {tab === "USD" && (
          <>
            {/* Datos bancarios */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Datos de transferencia</Text>
              <Text style={styles.cardSub}>Transfiere desde tu banco a esta cuenta</Text>

              {info?.bank.name ? (
                <>
                  <BankRow label="Banco"   value={info.bank.name} />
                  <BankRow label="Tipo"    value={info.bank.type} />
                  <BankRow label="Cuenta"  value={info.bank.account ?? "—"} mono />
                  <BankRow label="Titular" value={info.bank.holder ?? "—"} last />
                </>
              ) : (
                <View style={styles.noBankWrap}>
                  <Text style={styles.noBankText}>
                    ⚙️  Datos bancarios no configurados aún.{"\n"}Contacta a soporte.
                  </Text>
                </View>
              )}
            </View>

            {/* Formulario */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Notificar mi depósito</Text>
              <Text style={styles.cardSub}>
                Una vez transferido, indícanos el monto y la referencia para confirmar más rápido.
              </Text>

              {/* Monto */}
              <Text style={styles.label}>Monto depositado</Text>
              <TextInput
                style={styles.amountInput}
                placeholder="0.00"
                placeholderTextColor={C.textTertiary}
                keyboardType="decimal-pad"
                value={amount}
                onChangeText={setAmount}
              />

              {/* Banco origen */}
              <Text style={styles.label}>Tu banco</Text>
              <TouchableOpacity
                style={styles.selector}
                onPress={() => setShowBanks(!showBanks)}
              >
                <Text style={[styles.selectorText, !bankName && { color: C.textTertiary }]}>
                  {bankName || "Selecciona tu banco"}
                </Text>
                <Text style={styles.selectorChevron}>{showBanks ? "▲" : "▼"}</Text>
              </TouchableOpacity>

              {showBanks && (
                <View style={styles.bankList}>
                  {BANKS.map((b) => (
                    <TouchableOpacity
                      key={b}
                      style={[styles.bankOption, bankName === b && styles.bankOptionActive]}
                      onPress={() => { setBankName(b); setShowBanks(false); }}
                    >
                      <Text style={[styles.bankOptionText, bankName === b && styles.bankOptionTextActive]}>
                        {b}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {/* Referencia */}
              <Text style={styles.label}>Número de referencia</Text>
              <TextInput
                style={styles.input}
                placeholder="Ej: 0012345678"
                placeholderTextColor={C.textTertiary}
                keyboardType="default"
                value={reference}
                onChangeText={setReference}
              />

              <TouchableOpacity
                style={[styles.btn, sending && styles.btnDisabled]}
                onPress={handleFiatDeposit}
                disabled={sending}
              >
                {sending
                  ? <ActivityIndicator color="#000" />
                  : <Text style={styles.btnText}>Enviar solicitud</Text>
                }
              </TouchableOpacity>

              <Text style={styles.disclaimer}>
                ⏱  Revisión en máx. 30 min en horario laboral
              </Text>
            </View>
          </>
        )}

        {/* ── TAB CRYPTO ── */}
        {tab === "CRYPTO" && (
          <>
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Tu dirección TRC-20</Text>
              <Text style={styles.cardSub}>
                Envía USDT o USDC directamente a tu wallet. El saldo se acredita automáticamente.
              </Text>

              {info?.wallet_address ? (
                <>
                  <TouchableOpacity style={styles.walletBox} onPress={copyWallet} activeOpacity={0.7}>
                    <Text style={styles.walletLabel}>USDT · USDC · Red TRC-20</Text>
                    <Text style={styles.walletAddress} numberOfLines={2}>
                      {info.wallet_address}
                    </Text>
                    <View style={styles.copyRow}>
                      <Text style={styles.copyHint}>📋  Toca para copiar</Text>
                    </View>
                  </TouchableOpacity>

                  <View style={styles.infoRows}>
                    <InfoRow icon="⚡" text="Acreditación automática al confirmar la red" />
                    <InfoRow icon="✅" text="Tokens aceptados: USDT y USDC" />
                    <InfoRow icon="⚠️" text="Solo red TRC-20 — otras redes pueden perderse permanentemente" danger />
                  </View>
                </>
              ) : (
                <View style={styles.noBankWrap}>
                  <Text style={styles.noBankText}>
                    No tienes wallet TRC-20 asignada aún.{"\n"}Contacta a soporte.
                  </Text>
                </View>
              )}
            </View>
          </>
        )}

      </ScrollView>
    </KeyboardAvoidingView>
  );
}

/* ─── Componentes internos ─── */

function BankRow({ label, value, mono, last }: { label: string; value: string; mono?: boolean; last?: boolean }) {
  return (
    <View style={[styles.bankRow, last && { borderBottomWidth: 0 }]}>
      <Text style={styles.bankRowLabel}>{label}</Text>
      <Text style={[styles.bankRowValue, mono && { fontFamily: "monospace" }]}>{value}</Text>
    </View>
  );
}

function InfoRow({ icon, text, danger }: { icon: string; text: string; danger?: boolean }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoRowIcon}>{icon}</Text>
      <Text style={[styles.infoRowText, danger && { color: C.danger }]}>{text}</Text>
    </View>
  );
}

/* ─── Estilos ─── */

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bgAlt },
  center:    { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.bgAlt },

  header:      { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 56, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  backBtn:     { width: 40, height: 40, justifyContent: "center" },
  backText:    { fontSize: 32, color: C.text, lineHeight: 36 },
  headerTitle: { fontSize: 17, fontWeight: "600", color: C.text },

  // Tabs
  tabs:          { flexDirection: "row", backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  tab:           { flex: 1, paddingVertical: 14, alignItems: "center" },
  tabActive:     { borderBottomWidth: 2, borderBottomColor: C.accent },
  tabText:       { fontSize: 15, color: C.textSub, fontWeight: "500" },
  tabTextActive: { color: C.text, fontWeight: "700" },

  content: { padding: 20, gap: 16 },

  card:      { backgroundColor: C.bg, borderRadius: 20, padding: 24, ...C.shadow },
  cardTitle: { fontSize: 20, fontWeight: "700", color: C.text, letterSpacing: -0.3, marginBottom: 6 },
  cardSub:   { fontSize: 14, color: C.textSub, lineHeight: 20, marginBottom: 20 },

  // Bank rows
  bankRow:       { flexDirection: "row", justifyContent: "space-between", paddingVertical: 13, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  bankRowLabel:  { fontSize: 15, color: C.textSub },
  bankRowValue:  { fontSize: 15, color: C.text, fontWeight: "500" },

  noBankWrap:  { paddingVertical: 20, alignItems: "center" },
  noBankText:  { fontSize: 14, color: C.textSub, textAlign: "center", lineHeight: 22 },

  // Form
  label:       { fontSize: 12, fontWeight: "600", color: C.textSub, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8, marginTop: 16 },
  amountInput: { fontSize: 42, fontWeight: "800", color: C.text, textAlign: "center", paddingVertical: 12, letterSpacing: -1 },
  input:       { backgroundColor: C.bgAlt, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: C.text },

  selector:        { backgroundColor: C.bgAlt, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  selectorText:    { fontSize: 16, color: C.text },
  selectorChevron: { fontSize: 12, color: C.textSub },
  bankList:        { backgroundColor: C.bgAlt, borderRadius: 12, marginTop: 4, overflow: "hidden" },
  bankOption:      { paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  bankOptionActive:{ backgroundColor: C.accent + "20" },
  bankOptionText:  { fontSize: 15, color: C.text },
  bankOptionTextActive: { color: C.text, fontWeight: "700" },

  btn:         { backgroundColor: C.accent, borderRadius: 14, paddingVertical: 17, alignItems: "center", marginTop: 24 },
  btnDisabled: { opacity: 0.6 },
  btnText:     { fontSize: 16, fontWeight: "700", color: "#000" },
  disclaimer:  { fontSize: 12, color: C.textTertiary, textAlign: "center", marginTop: 14 },

  // Wallet crypto
  walletBox:     { backgroundColor: C.bgAlt, borderRadius: 14, padding: 20, alignItems: "center", marginBottom: 20 },
  walletLabel:   { fontSize: 12, fontWeight: "600", color: C.textSub, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 10 },
  walletAddress: { fontSize: 14, fontFamily: "monospace", color: C.text, textAlign: "center", lineHeight: 22, marginBottom: 12 },
  copyRow:       { flexDirection: "row", alignItems: "center" },
  copyHint:      { fontSize: 13, color: C.textSub },

  infoRows:    { gap: 12 },
  infoRow:     { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  infoRowIcon: { fontSize: 16, marginTop: 1 },
  infoRowText: { fontSize: 14, color: C.textSub, flex: 1, lineHeight: 20 },
});
