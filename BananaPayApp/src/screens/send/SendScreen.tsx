import { useLocalSearchParams, useRouter } from "expo-router";
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

import { sendTransfer, validateRecipient } from "@/src/services/api";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";
import { fmtCrypto, fmtUSD } from "@/src/utils/format";

type Currency = "USD" | "USDT" | "USDC";
type Step = 1 | 2 | 3;

const CURRENCY_CONFIG: Record<Currency, { label: string; icon: string; color: string }> = {
  USD:  { label: "USD",  icon: "🏦", color: C.success },
  USDT: { label: "USDT", icon: "🪙", color: C.blue    },
  USDC: { label: "USDC", icon: "🔵", color: C.indigo  },
};

export default function SendScreen() {
  const router  = useRouter();
  const params  = useLocalSearchParams<{ prefill_cedula?: string; prefill_amount?: string }>();
  const balances = useStore((s) => s.balances);

  // ── Step 1: destinatario ──────────────────────────────────────────────────
  const [cedula,        setCedula]        = useState(params.prefill_cedula ?? "");
  const [phone,         setPhone]         = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [validating,    setValidating]    = useState(false);

  // Si viene de un QR con cédula ya conocida, auto-validar en cuanto el usuario
  // ingrese el teléfono. Si además trae amount, saltar al paso 3 tras validar.
  const prefillAmount = params.prefill_amount ?? "";

  // ── Step 2: monto ─────────────────────────────────────────────────────────
  const [currency, setCurrency] = useState<Currency>("USD");
  const [amount,   setAmount]   = useState(prefillAmount);

  // ── Step 3: PIN ───────────────────────────────────────────────────────────
  const [pin,      setPin]      = useState("");
  const [sending,  setSending]  = useState(false);

  const [step, setStep] = useState<Step>(1);

  // ── Helpers ───────────────────────────────────────────────────────────────

  const availableBalance = () => {
    if (!balances) return 0;
    if (currency === "USD")  return balances.fiat;
    if (currency === "USDT") return balances.usdt;
    return balances.usdc;
  };

  const fmtAvailable = () => {
    const bal = availableBalance();
    if (currency === "USD") return fmtUSD(bal);
    return fmtCrypto(bal, currency);
  };

  // ── Paso 1 → validar destinatario ─────────────────────────────────────────

  const handleValidate = async () => {
    if (cedula.length < 10) {
      Alert.alert("Cédula incompleta", "Ingresa los 10 dígitos de la cédula.");
      return;
    }
    if (phone.length < 10) {
      Alert.alert("Teléfono incompleto", "Ingresa el número de teléfono.");
      return;
    }
    setValidating(true);
    try {
      const data = await validateRecipient(cedula.trim(), phone.trim());
      setRecipientName(data.name);
      setStep(2);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "No encontramos esa cuenta.";
      Alert.alert("No encontrado", msg);
    } finally {
      setValidating(false);
    }
  };

  // ── Paso 2 → validar monto ────────────────────────────────────────────────

  const handleAmountNext = () => {
    const val = parseFloat(amount.replace(",", "."));
    if (!val || val <= 0) {
      Alert.alert("Monto inválido", "Ingresa un monto mayor a 0.");
      return;
    }
    if (val > availableBalance()) {
      Alert.alert("Saldo insuficiente", `Solo tienes ${fmtAvailable()} disponible.`);
      return;
    }
    setStep(3);
  };

  // ── Paso 3 → enviar ───────────────────────────────────────────────────────

  const handleSend = async () => {
    if (pin.length < 6) {
      Alert.alert("PIN incompleto", "Ingresa tu PIN de 6 dígitos.");
      return;
    }
    setSending(true);
    try {
      const val = parseFloat(amount.replace(",", "."));
      await sendTransfer({
        to_cedula: cedula.trim(),
        to_phone:  phone.trim(),
        amount:    val,
        currency,
        pin,
      });

      // Éxito
      Alert.alert(
        "¡Enviado! 🍌",
        `${currency === "USD" ? fmtUSD(val) : fmtCrypto(val, currency)} enviado a ${recipientName.split(" ")[0]}.`,
        [{ text: "OK", onPress: () => router.back() }],
      );
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Error al enviar. Intenta de nuevo.";
      Alert.alert("Error", msg);
      if (msg === "PIN incorrecto.") setPin("");
    } finally {
      setSending(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => (step > 1 ? setStep((step - 1) as Step) : router.back())} style={styles.backBtn}>
          <Text style={styles.backText}>‹</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Enviar dinero</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Progress dots */}
      <View style={styles.progress}>
        {([1, 2, 3] as Step[]).map((s) => (
          <View key={s} style={[styles.dot, step >= s && styles.dotActive]} />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        {/* ── STEP 1: Destinatario ── */}
        {step === 1 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>¿A quién envías?</Text>
            <Text style={styles.cardSub}>Cédula y teléfono del destinatario</Text>

            {/* Botón escanear QR */}
            <TouchableOpacity
              style={styles.qrScanBtn}
              onPress={() => router.push("/qr" as any)}
            >
              <Text style={styles.qrScanIcon}>📷</Text>
              <Text style={styles.qrScanText}>Escanear QR BananaPay</Text>
            </TouchableOpacity>

            <View style={styles.dividerRow}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>o ingresa manualmente</Text>
              <View style={styles.dividerLine} />
            </View>

            <Text style={styles.label}>Cédula</Text>
            <TextInput
              style={styles.input}
              placeholder="10 dígitos"
              placeholderTextColor={C.textTertiary}
              keyboardType="numeric"
              value={cedula}
              onChangeText={setCedula}
              maxLength={10}
            />

            <Text style={styles.label}>Teléfono</Text>
            <TextInput
              style={styles.input}
              placeholder="09XXXXXXXX"
              placeholderTextColor={C.textTertiary}
              keyboardType="phone-pad"
              value={phone}
              onChangeText={setPhone}
              maxLength={13}
            />

            <TouchableOpacity
              style={[styles.btn, validating && styles.btnDisabled]}
              onPress={handleValidate}
              disabled={validating}
            >
              {validating
                ? <ActivityIndicator color="#000" />
                : <Text style={styles.btnText}>Buscar destinatario</Text>
              }
            </TouchableOpacity>
          </View>
        )}

        {/* ── STEP 2: Monto ── */}
        {step === 2 && (
          <View style={styles.card}>
            <View style={styles.recipientBadge}>
              <Text style={styles.recipientIcon}>👤</Text>
              <Text style={styles.recipientName}>{recipientName}</Text>
            </View>

            <Text style={styles.cardTitle}>¿Cuánto envías?</Text>

            {/* Selector de moneda */}
            <View style={styles.currencyRow}>
              {(["USD", "USDT", "USDC"] as Currency[]).map((c) => {
                const cfg = CURRENCY_CONFIG[c];
                const active = currency === c;
                return (
                  <TouchableOpacity
                    key={c}
                    style={[styles.currencyPill, active && { backgroundColor: cfg.color + "18", borderColor: cfg.color }]}
                    onPress={() => { setCurrency(c); setAmount(""); }}
                  >
                    <Text style={styles.currencyPillIcon}>{cfg.icon}</Text>
                    <Text style={[styles.currencyPillText, active && { color: cfg.color, fontWeight: "700" }]}>
                      {cfg.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={styles.availableText}>
              Disponible: <Text style={styles.availableAmount}>{fmtAvailable()}</Text>
            </Text>

            <TextInput
              style={styles.amountInput}
              placeholder="0.00"
              placeholderTextColor={C.textTertiary}
              keyboardType="decimal-pad"
              value={amount}
              onChangeText={setAmount}
            />

            <TouchableOpacity style={styles.btn} onPress={handleAmountNext}>
              <Text style={styles.btnText}>Continuar</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── STEP 3: Confirmar + PIN ── */}
        {step === 3 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Confirmar envío</Text>

            {/* Resumen */}
            <View style={styles.summary}>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Para</Text>
                <Text style={styles.summaryValue}>{recipientName}</Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Monto</Text>
                <Text style={[styles.summaryValue, styles.summaryAmount]}>
                  {currency === "USD"
                    ? fmtUSD(parseFloat(amount))
                    : fmtCrypto(parseFloat(amount), currency)}
                </Text>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Moneda</Text>
                <Text style={styles.summaryValue}>
                  {CURRENCY_CONFIG[currency].icon} {currency}
                </Text>
              </View>
              <View style={[styles.summaryRow, { borderBottomWidth: 0 }]}>
                <Text style={styles.summaryLabel}>Comisión</Text>
                <Text style={[styles.summaryValue, { color: C.success, fontWeight: "700" }]}>
                  Gratis 🍌
                </Text>
              </View>
            </View>

            <Text style={styles.label}>Confirma con tu PIN</Text>
            <TextInput
              style={[styles.input, styles.pinInput]}
              placeholder="● ● ● ● ● ●"
              placeholderTextColor={C.textTertiary}
              keyboardType="numeric"
              secureTextEntry
              value={pin}
              onChangeText={setPin}
              maxLength={6}
            />

            <TouchableOpacity
              style={[styles.btn, sending && styles.btnDisabled]}
              onPress={handleSend}
              disabled={sending}
            >
              {sending
                ? <ActivityIndicator color="#000" />
                : <Text style={styles.btnText}>Confirmar envío</Text>
              }
            </TouchableOpacity>
          </View>
        )}

      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bgAlt },

  // Header
  header:      { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 56, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  backBtn:     { width: 40, height: 40, justifyContent: "center" },
  backText:    { fontSize: 32, color: C.text, lineHeight: 36 },
  headerTitle: { fontSize: 17, fontWeight: "600", color: C.text },

  // Progress
  progress:    { flexDirection: "row", justifyContent: "center", gap: 8, paddingVertical: 20, backgroundColor: C.bg },
  dot:         { width: 8, height: 8, borderRadius: 4, backgroundColor: C.border },
  dotActive:   { backgroundColor: C.accent, width: 24 },

  content:     { padding: 20 },

  // Card contenedor de cada step
  card:        { backgroundColor: C.bg, borderRadius: 20, padding: 24, ...C.shadow },

  cardTitle:   { fontSize: 22, fontWeight: "700", color: C.text, letterSpacing: -0.3, marginBottom: 6 },
  cardSub:     { fontSize: 14, color: C.textSub, marginBottom: 24 },

  label:       { fontSize: 12, fontWeight: "600", color: C.textSub, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8, marginTop: 16 },
  input:       { backgroundColor: C.bgAlt, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: C.text },
  pinInput:    { textAlign: "center", fontSize: 20, letterSpacing: 8 },

  btn:         { backgroundColor: C.accent, borderRadius: 14, paddingVertical: 17, alignItems: "center", marginTop: 24 },
  btnDisabled: { opacity: 0.6 },
  btnText:     { fontSize: 16, fontWeight: "700", color: "#000" },

  // QR scan
  qrScanBtn:    { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, backgroundColor: C.bgAlt, borderRadius: 14, paddingVertical: 16, borderWidth: 1.5, borderColor: C.border, borderStyle: "dashed" },
  qrScanIcon:   { fontSize: 22 },
  qrScanText:   { fontSize: 15, fontWeight: "600", color: C.text },
  dividerRow:   { flexDirection: "row", alignItems: "center", gap: 10, marginVertical: 20 },
  dividerLine:  { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: C.border },
  dividerText:  { fontSize: 12, color: C.textTertiary },

  // Step 2
  recipientBadge: { flexDirection: "row", alignItems: "center", backgroundColor: C.success + "15", borderRadius: 12, padding: 12, marginBottom: 20 },
  recipientIcon:  { fontSize: 20, marginRight: 10 },
  recipientName:  { fontSize: 16, fontWeight: "600", color: C.success },

  currencyRow:     { flexDirection: "row", gap: 10, marginTop: 8 },
  currencyPill:    { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 12, borderRadius: 12, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.bgAlt },
  currencyPillIcon:{ fontSize: 16 },
  currencyPillText:{ fontSize: 14, color: C.textSub },

  availableText:   { fontSize: 13, color: C.textSub, marginTop: 16, marginBottom: 4 },
  availableAmount: { fontWeight: "700", color: C.text },

  amountInput: { fontSize: 48, fontWeight: "800", color: C.text, textAlign: "center", paddingVertical: 16, letterSpacing: -1 },

  // Step 3
  summary:      { backgroundColor: C.bgAlt, borderRadius: 14, overflow: "hidden", marginBottom: 8 },
  summaryRow:   { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  summaryLabel: { fontSize: 15, color: C.textSub },
  summaryValue: { fontSize: 15, color: C.text, fontWeight: "500" },
  summaryAmount:{ fontWeight: "800", fontSize: 17, color: C.text },
});
