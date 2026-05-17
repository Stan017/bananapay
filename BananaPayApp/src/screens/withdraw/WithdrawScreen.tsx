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

import { getWithdrawInfo, withdrawCrypto, withdrawFiat } from "@/src/services/api";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";
import { fmtCrypto, fmtUSD } from "@/src/utils/format";

type Tab      = "USD" | "USDT" | "USDC";
type USDStep  = 1 | 2;
type CryptoStep = 1 | 2;

const BANKS = [
  "Banco Pichincha", "Banco Guayaquil", "Banco Pacífico",
  "Produbanco", "Banco Internacional", "Banco del Austro",
  "Banco Bolivariano", "Otro",
];

interface Limits {
  max_single: number; max_daily: number; min_fiat: number;
  cooldown_minutes: number; min_crypto: number; crypto_fee: number;
}

interface SavedBank {
  bank_name: string; account_type: string;
  account_number: string; account_holder: string;
}

export default function WithdrawScreen() {
  const router   = useRouter();
  const balances = useStore((s) => s.balances);

  const [tab,     setTab]     = useState<Tab>("USD");
  const [limits,  setLimits]  = useState<Limits | null>(null);
  const [loading, setLoading] = useState(true);

  // ── USD state ─────────────────────────────────────────────────────────────
  const [usdStep,      setUsdStep]      = useState<USDStep>(1);
  const [amount,       setAmount]       = useState("");
  const [wtype,        setWtype]        = useState<"normal" | "instant">("normal");
  const [bankName,     setBankName]     = useState("");
  const [accountType,  setAccountType]  = useState<"Ahorros" | "Corriente">("Ahorros");
  const [accountNum,   setAccountNum]   = useState("");
  const [accountHolder,setAccountHolder]= useState("");
  const [showBanks,    setShowBanks]    = useState(false);
  const [pin,          setPin]          = useState("");
  const [sending,      setSending]      = useState(false);

  // ── Crypto state ──────────────────────────────────────────────────────────
  const [cryptoStep,   setCryptoStep]   = useState<CryptoStep>(1);
  const [cryptoAmount, setCryptoAmount] = useState("");
  const [toAddress,    setToAddress]    = useState("");
  const [cryptoPin,    setCryptoPin]    = useState("");

  useEffect(() => {
    getWithdrawInfo()
      .then((data) => {
        setLimits(data.limits);
        const saved: SavedBank | null = data.saved_bank;
        if (saved) {
          setBankName(saved.bank_name);
          setAccountType(saved.account_type as "Ahorros" | "Corriente");
          setAccountNum(saved.account_number);
          setAccountHolder(saved.account_holder);
        }
      })
      .catch(() => Alert.alert("Error", "No se pudo cargar la información."))
      .finally(() => setLoading(false));
  }, []);

  // ── Fee calc ──────────────────────────────────────────────────────────────
  const usdAmount  = parseFloat(amount.replace(",", ".")) || 0;
  const instantFee = usdAmount <= 50 ? 0.50 : usdAmount <= 100 ? 0.75 : 1.00;
  const fee        = wtype === "normal" ? 0 : instantFee;
  const receives   = usdAmount - fee;

  const cryptoAmt  = parseFloat(cryptoAmount.replace(",", ".")) || 0;
  const cryptoFee  = limits?.crypto_fee ?? 1.50;
  const cryptoRecv = cryptoAmt; // fee se cobra aparte del saldo

  const availCrypto = tab === "USDT" ? (balances?.usdt ?? 0) : (balances?.usdc ?? 0);

  // ── USD Step 1 → 2 ───────────────────────────────────────────────────────
  const handleUsdNext = () => {
    if (!usdAmount || usdAmount < (limits?.min_fiat ?? 10)) {
      Alert.alert("Monto inválido", `Mínimo $${limits?.min_fiat ?? 10}.00`);
      return;
    }
    if (usdAmount > (limits?.max_single ?? 300)) {
      Alert.alert("Límite excedido", `Máximo $${limits?.max_single ?? 300}.00 por retiro.`);
      return;
    }
    if (usdAmount > (balances?.fiat ?? 0)) {
      Alert.alert("Saldo insuficiente", `Tienes ${fmtUSD(balances?.fiat ?? 0)} disponible.`);
      return;
    }
    setUsdStep(2);
  };

  // ── USD enviar ────────────────────────────────────────────────────────────
  const handleUsdSend = async () => {
    if (!bankName) { Alert.alert("Falta el banco", "Selecciona tu banco."); return; }
    if (accountNum.length < 10) { Alert.alert("Cuenta inválida", "Mínimo 10 dígitos."); return; }
    if (!accountHolder.trim()) { Alert.alert("Falta el titular", "Ingresa el nombre del titular."); return; }
    if (pin.length < 6) { Alert.alert("PIN incompleto", "Ingresa tu PIN de 6 dígitos."); return; }

    setSending(true);
    try {
      const res = await withdrawFiat({
        amount: usdAmount, withdrawal_type: wtype,
        bank_name: bankName, account_type: accountType,
        account_number: accountNum, account_holder: accountHolder, pin,
      });
      const tiempo = wtype === "normal" ? "24 horas" : "menos de 1 hora";
      Alert.alert(
        "Retiro solicitado 🍌",
        `Se transferirán ${fmtUSD(res.amount_received)} a ${bankName} en ${tiempo}.`,
        [{ text: "OK", onPress: () => router.back() }],
      );
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Error al procesar el retiro.";
      Alert.alert("Error", msg);
      if (msg === "PIN incorrecto.") setPin("");
    } finally {
      setSending(false);
    }
  };

  // ── Crypto Step 1 → 2 ────────────────────────────────────────────────────
  const handleCryptoNext = () => {
    const min = limits?.min_crypto ?? 5;
    if (!cryptoAmt || cryptoAmt < min) {
      Alert.alert("Monto inválido", `Mínimo ${min} ${tab}.`);
      return;
    }
    if (cryptoAmt + cryptoFee > availCrypto) {
      Alert.alert("Saldo insuficiente",
        `Necesitas ${fmtCrypto(cryptoAmt + cryptoFee, tab)} (incluye fee $${cryptoFee}).`);
      return;
    }
    setCryptoStep(2);
  };

  // ── Crypto enviar ─────────────────────────────────────────────────────────
  const handleCryptoSend = async () => {
    if (!toAddress.startsWith("T") || toAddress.length !== 34) {
      Alert.alert("Dirección inválida", "Debe empezar con T y tener 34 caracteres.");
      return;
    }
    if (cryptoPin.length < 6) { Alert.alert("PIN incompleto", "Ingresa tu PIN de 6 dígitos."); return; }

    setSending(true);
    try {
      await withdrawCrypto({ currency: tab, amount: cryptoAmt, to_address: toAddress, pin: cryptoPin });
      Alert.alert(
        `${tab} enviado 🍌`,
        `${fmtCrypto(cryptoAmt, tab)} en camino a tu wallet. Confirmación en ~1 minuto.`,
        [{ text: "OK", onPress: () => router.back() }],
      );
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Error al procesar el retiro.";
      Alert.alert("Error", msg);
      if (msg === "PIN incorrecto.") setCryptoPin("");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={C.accent} size="large" /></View>;
  }

  const currentStep = tab === "USD" ? usdStep : cryptoStep;
  const totalSteps  = 2;

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === "ios" ? "padding" : "height"}>

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backBtn}
          onPress={() => {
            if (tab === "USD" && usdStep === 2) return setUsdStep(1);
            if (tab !== "USD" && cryptoStep === 2) return setCryptoStep(1);
            router.back();
          }}
        >
          <Text style={styles.backText}>‹</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Retirar</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {(["USD", "USDT", "USDC"] as Tab[]).map((t) => (
          <TouchableOpacity
            key={t}
            style={[styles.tab, tab === t && styles.tabActive]}
            onPress={() => { setTab(t); setUsdStep(1); setCryptoStep(1); }}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Progress */}
      <View style={styles.progress}>
        {[1, 2].map((s) => (
          <View key={s} style={[styles.dot, currentStep >= s && styles.dotActive]} />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        {/* ══ USD ══ */}
        {tab === "USD" && usdStep === 1 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>¿Cuánto retiras?</Text>
            <Text style={styles.cardSub}>
              Disponible: <Text style={{ fontWeight: "700", color: C.text }}>{fmtUSD(balances?.fiat ?? 0)}</Text>
            </Text>

            <TextInput
              style={styles.amountInput}
              placeholder="0.00"
              placeholderTextColor={C.textTertiary}
              keyboardType="decimal-pad"
              value={amount}
              onChangeText={setAmount}
            />

            {/* Tipo de retiro */}
            <Text style={styles.label}>Velocidad</Text>
            <View style={styles.typeRow}>
              <TouchableOpacity
                style={[styles.typePill, wtype === "normal" && styles.typePillActive]}
                onPress={() => setWtype("normal")}
              >
                <Text style={[styles.typePillTitle, wtype === "normal" && styles.typePillTitleActive]}>Normal</Text>
                <Text style={[styles.typePillSub, wtype === "normal" && { color: C.success }]}>Gratis · 24h</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.typePill, wtype === "instant" && styles.typePillActive]}
                onPress={() => setWtype("instant")}
              >
                <Text style={[styles.typePillTitle, wtype === "instant" && styles.typePillTitleActive]}>⚡ Instant</Text>
                <Text style={[styles.typePillSub, wtype === "instant" && { color: C.blue }]}>
                  ${usdAmount > 0 ? instantFee.toFixed(2) : "0.50–1.00"} · &lt;1h
                </Text>
              </TouchableOpacity>
            </View>

            {/* Resumen rápido */}
            {usdAmount > 0 && (
              <View style={styles.quickSummary}>
                <Text style={styles.quickRow}>Retiras <Text style={styles.quickVal}>{fmtUSD(usdAmount)}</Text></Text>
                <Text style={styles.quickRow}>Fee <Text style={styles.quickVal}>{fmtUSD(fee)}</Text></Text>
                <Text style={[styles.quickRow, { marginTop: 4 }]}>
                  Recibes <Text style={[styles.quickVal, { color: C.success, fontSize: 18 }]}>{fmtUSD(receives)}</Text>
                </Text>
              </View>
            )}

            <TouchableOpacity style={styles.btn} onPress={handleUsdNext}>
              <Text style={styles.btnText}>Continuar</Text>
            </TouchableOpacity>

            <Text style={styles.limitNote}>
              Máx. ${limits?.max_single ?? 300} por retiro · ${limits?.max_daily ?? 500}/día
            </Text>
          </View>
        )}

        {tab === "USD" && usdStep === 2 && (
          <View style={styles.card}>
            {/* Mini resumen */}
            <View style={styles.summaryBanner}>
              <Text style={styles.summaryBannerAmount}>{fmtUSD(receives)}</Text>
              <Text style={styles.summaryBannerSub}>
                {wtype === "normal" ? "Normal · ~24h" : "⚡ Instant · <1h"}
                {fee > 0 ? `  ·  fee ${fmtUSD(fee)}` : "  ·  Sin comisión"}
              </Text>
            </View>

            <Text style={styles.cardTitle}>Datos bancarios</Text>

            {/* Banco */}
            <Text style={styles.label}>Banco</Text>
            <TouchableOpacity style={styles.selector} onPress={() => setShowBanks(!showBanks)}>
              <Text style={[styles.selectorText, !bankName && { color: C.textTertiary }]}>
                {bankName || "Selecciona tu banco"}
              </Text>
              <Text style={styles.selectorChevron}>{showBanks ? "▲" : "▼"}</Text>
            </TouchableOpacity>
            {showBanks && (
              <View style={styles.bankList}>
                {BANKS.map((b) => (
                  <TouchableOpacity key={b} style={[styles.bankOption, bankName === b && styles.bankOptionActive]}
                    onPress={() => { setBankName(b); setShowBanks(false); }}>
                    <Text style={[styles.bankOptionText, bankName === b && { fontWeight: "700" }]}>{b}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {/* Tipo */}
            <Text style={styles.label}>Tipo de cuenta</Text>
            <View style={styles.typeRow}>
              {(["Ahorros", "Corriente"] as const).map((t) => (
                <TouchableOpacity key={t}
                  style={[styles.typePill, accountType === t && styles.typePillActive]}
                  onPress={() => setAccountType(t)}>
                  <Text style={[styles.typePillTitle, accountType === t && styles.typePillTitleActive]}>{t}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Número */}
            <Text style={styles.label}>Número de cuenta</Text>
            <TextInput style={styles.input} placeholder="Mínimo 10 dígitos"
              placeholderTextColor={C.textTertiary} keyboardType="numeric"
              value={accountNum} onChangeText={setAccountNum} />

            {/* Titular */}
            <Text style={styles.label}>Titular de la cuenta</Text>
            <TextInput style={styles.input} placeholder="Nombre completo"
              placeholderTextColor={C.textTertiary} autoCapitalize="words"
              value={accountHolder} onChangeText={setAccountHolder} />

            {/* PIN */}
            <Text style={styles.label}>Confirma con tu PIN</Text>
            <TextInput style={[styles.input, styles.pinInput]} placeholder="● ● ● ● ● ●"
              placeholderTextColor={C.textTertiary} keyboardType="numeric"
              secureTextEntry value={pin} onChangeText={setPin} maxLength={6} />

            <TouchableOpacity style={[styles.btn, sending && styles.btnDisabled]}
              onPress={handleUsdSend} disabled={sending}>
              {sending ? <ActivityIndicator color="#000" /> : <Text style={styles.btnText}>Confirmar retiro</Text>}
            </TouchableOpacity>
          </View>
        )}

        {/* ══ USDT / USDC ══ */}
        {tab !== "USD" && cryptoStep === 1 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>¿Cuánto retiras?</Text>
            <Text style={styles.cardSub}>
              Disponible: <Text style={{ fontWeight: "700", color: C.text }}>{fmtCrypto(availCrypto, tab)}</Text>
            </Text>

            <TextInput
              style={styles.amountInput}
              placeholder="0.00"
              placeholderTextColor={C.textTertiary}
              keyboardType="decimal-pad"
              value={cryptoAmount}
              onChangeText={setCryptoAmount}
            />

            {cryptoAmt > 0 && (
              <View style={styles.quickSummary}>
                <Text style={styles.quickRow}>Envías <Text style={styles.quickVal}>{fmtCrypto(cryptoAmt, tab)}</Text></Text>
                <Text style={styles.quickRow}>Fee red <Text style={styles.quickVal}>${cryptoFee.toFixed(2)} {tab}</Text></Text>
                <Text style={styles.quickRow}>Total debitado <Text style={[styles.quickVal, { color: C.danger }]}>{fmtCrypto(cryptoAmt + cryptoFee, tab)}</Text></Text>
              </View>
            )}

            <TouchableOpacity style={styles.btn} onPress={handleCryptoNext}>
              <Text style={styles.btnText}>Continuar</Text>
            </TouchableOpacity>

            <Text style={styles.limitNote}>
              Mín. {limits?.min_crypto ?? 5} {tab} · Fee de red ${cryptoFee} {tab}
            </Text>
          </View>
        )}

        {tab !== "USD" && cryptoStep === 2 && (
          <View style={styles.card}>
            <View style={styles.summaryBanner}>
              <Text style={styles.summaryBannerAmount}>{fmtCrypto(cryptoAmt, tab)}</Text>
              <Text style={styles.summaryBannerSub}>Fee ${cryptoFee} · Confirmación ~1 min</Text>
            </View>

            <Text style={styles.cardTitle}>Dirección destino</Text>

            <Text style={styles.label}>Wallet TRC-20 externa</Text>
            <TextInput
              style={[styles.input, { fontFamily: "monospace", fontSize: 13 }]}
              placeholder="T... (34 caracteres)"
              placeholderTextColor={C.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              value={toAddress}
              onChangeText={setToAddress}
            />

            <View style={styles.warningBox}>
              <Text style={styles.warningText}>
                ⚠️  Verifica la dirección — las transacciones blockchain son irreversibles.
              </Text>
            </View>

            <Text style={styles.label}>Confirma con tu PIN</Text>
            <TextInput style={[styles.input, styles.pinInput]} placeholder="● ● ● ● ● ●"
              placeholderTextColor={C.textTertiary} keyboardType="numeric"
              secureTextEntry value={cryptoPin} onChangeText={setCryptoPin} maxLength={6} />

            <TouchableOpacity style={[styles.btn, sending && styles.btnDisabled]}
              onPress={handleCryptoSend} disabled={sending}>
              {sending ? <ActivityIndicator color="#000" /> : <Text style={styles.btnText}>Confirmar retiro</Text>}
            </TouchableOpacity>
          </View>
        )}

      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container:  { flex: 1, backgroundColor: C.bgAlt },
  center:     { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.bgAlt },

  header:      { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 56, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  backBtn:     { width: 40, height: 40, justifyContent: "center" },
  backText:    { fontSize: 32, color: C.text, lineHeight: 36 },
  headerTitle: { fontSize: 17, fontWeight: "600", color: C.text },

  tabs:          { flexDirection: "row", backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  tab:           { flex: 1, paddingVertical: 14, alignItems: "center" },
  tabActive:     { borderBottomWidth: 2, borderBottomColor: C.accent },
  tabText:       { fontSize: 14, color: C.textSub, fontWeight: "500" },
  tabTextActive: { color: C.text, fontWeight: "700" },

  progress:  { flexDirection: "row", justifyContent: "center", gap: 8, paddingVertical: 16, backgroundColor: C.bg },
  dot:       { width: 8, height: 8, borderRadius: 4, backgroundColor: C.border },
  dotActive: { backgroundColor: C.accent, width: 24 },

  content:   { padding: 20 },
  card:      { backgroundColor: C.bg, borderRadius: 20, padding: 24, ...C.shadow },
  cardTitle: { fontSize: 22, fontWeight: "700", color: C.text, letterSpacing: -0.3, marginBottom: 6 },
  cardSub:   { fontSize: 14, color: C.textSub, marginBottom: 8 },

  amountInput: { fontSize: 48, fontWeight: "800", color: C.text, textAlign: "center", paddingVertical: 16, letterSpacing: -1 },

  label: { fontSize: 12, fontWeight: "600", color: C.textSub, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8, marginTop: 16 },
  input: { backgroundColor: C.bgAlt, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: C.text },
  pinInput: { textAlign: "center", fontSize: 20, letterSpacing: 8 },

  typeRow:          { flexDirection: "row", gap: 10, marginTop: 4 },
  typePill:         { flex: 1, alignItems: "center", paddingVertical: 14, borderRadius: 14, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.bgAlt },
  typePillActive:   { borderColor: C.accent, backgroundColor: C.accent + "15" },
  typePillTitle:    { fontSize: 15, fontWeight: "600", color: C.textSub },
  typePillTitleActive: { color: C.text },
  typePillSub:      { fontSize: 12, color: C.textTertiary, marginTop: 2 },

  quickSummary: { backgroundColor: C.bgAlt, borderRadius: 14, padding: 16, marginTop: 20, gap: 6 },
  quickRow:     { fontSize: 14, color: C.textSub, flexDirection: "row" },
  quickVal:     { fontWeight: "700", color: C.text, fontSize: 15 },

  summaryBanner:       { backgroundColor: C.accent + "20", borderRadius: 14, padding: 16, alignItems: "center", marginBottom: 20 },
  summaryBannerAmount: { fontSize: 32, fontWeight: "800", color: C.text, letterSpacing: -0.5 },
  summaryBannerSub:    { fontSize: 13, color: C.textSub, marginTop: 4 },

  selector:        { backgroundColor: C.bgAlt, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  selectorText:    { fontSize: 16, color: C.text },
  selectorChevron: { fontSize: 12, color: C.textSub },
  bankList:        { backgroundColor: C.bgAlt, borderRadius: 12, marginTop: 4, overflow: "hidden" },
  bankOption:      { paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  bankOptionActive:{ backgroundColor: C.accent + "20" },
  bankOptionText:  { fontSize: 15, color: C.text },

  warningBox:  { backgroundColor: "#ff3b3010", borderRadius: 12, padding: 14, marginTop: 16 },
  warningText: { fontSize: 13, color: C.danger, lineHeight: 20 },

  btn:         { backgroundColor: C.accent, borderRadius: 14, paddingVertical: 17, alignItems: "center", marginTop: 24 },
  btnDisabled: { opacity: 0.6 },
  btnText:     { fontSize: 16, fontWeight: "700", color: "#000" },
  limitNote:   { fontSize: 12, color: C.textTertiary, textAlign: "center", marginTop: 14 },
});
