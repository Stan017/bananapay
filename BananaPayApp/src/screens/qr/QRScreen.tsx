/**
 * QRScreen — dos modos:
 *   "show"  → muestra el QR del usuario para que otros le paguen
 *   "scan"  → abre la cámara para escanear el QR de otro usuario
 */

import { CameraView, useCameraPermissions } from "expo-camera";
import * as Clipboard from "expo-clipboard";
import { useRouter } from "expo-router";
import { useRef, useState } from "react";
import {
  Alert,
  Modal,
  ScrollView,
  Share,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
  Platform,
} from "react-native";
import QRCode from "react-native-qrcode-svg";
import { Text } from "@/src/components/Text";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";

type Mode     = "show" | "scan";
type Currency = "USD" | "USDT" | "USDC";

const CURRENCIES: { value: Currency; label: string; icon: string }[] = [
  { value: "USD",  label: "USD",  icon: "🏦" },
  { value: "USDT", label: "USDT", icon: "🪙" },
  { value: "USDC", label: "USDC", icon: "🔵" },
];

export default function QRScreen() {
  const router = useRouter();
  const user   = useStore((s) => s.user);

  const [mode,        setMode]        = useState<Mode>("show");
  const [amountInput, setAmountInput] = useState("");
  const [currency,    setCurrency]    = useState<Currency>("USD");
  const [scannerOpen, setScannerOpen] = useState(false);

  // ── Datos del QR ────────────────────────────────────────────────────────────
  const buildQrData = () => {
    const base = `bananapay://pay?cedula=${user?.cedula ?? ""}&currency=${currency}`;
    const amt  = parseFloat(amountInput.replace(",", "."));
    if (amt > 0) return `${base}&amount=${amt.toFixed(2)}`;
    return base;
  };

  const handleShare = async () => {
    try {
      const currencyLabel = currency === "USD" ? "dólares" : currency;
      const amtText = parseFloat(amountInput) > 0
        ? ` $${parseFloat(amountInput).toFixed(2)} en ${currencyLabel}`
        : ` en ${currencyLabel}`;
      await Share.share({
        message: `Págame${amtText} con BananaPay 🍌\n${buildQrData()}`,
        title:   "Mi QR BananaPay",
      });
    } catch {
      // usuario canceló
    }
  };

  const handleCopyLink = async () => {
    await Clipboard.setStringAsync(buildQrData());
    Alert.alert("Copiado", "Link de pago copiado al portapapeles");
  };

  // ── UI ───────────────────────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backText}>‹</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>QR BananaPay</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        <TouchableOpacity
          style={[styles.tab, mode === "show" && styles.tabActive]}
          onPress={() => setMode("show")}
        >
          <Text style={[styles.tabText, mode === "show" && styles.tabTextActive]}>
            Mi QR
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, mode === "scan" && styles.tabActive]}
          onPress={() => setMode("scan")}
        >
          <Text style={[styles.tabText, mode === "scan" && styles.tabTextActive]}>
            Escanear
          </Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {mode === "show" ? (
          <ShowMyQR
            qrData={buildQrData()}
            amountInput={amountInput}
            setAmountInput={setAmountInput}
            currency={currency}
            setCurrency={setCurrency}
            onShare={handleShare}
            onCopy={handleCopyLink}
          />
        ) : (
          <ScanQR onScannerOpen={() => setScannerOpen(true)} />
        )}
      </ScrollView>

      {/* Modal scanner a pantalla completa */}
      <Modal visible={scannerOpen} animationType="slide" onRequestClose={() => setScannerOpen(false)}>
        <ScannerModal
          onClose={() => setScannerOpen(false)}
          onScanned={(data) => {
            setScannerOpen(false);
            handleQRScanned(data, router);
          }}
        />
      </Modal>
    </View>
  );
}


// ─── Panel: mostrar mi QR ─────────────────────────────────────────────────────

function ShowMyQR({
  qrData, amountInput, setAmountInput, currency, setCurrency, onShare, onCopy,
}: {
  qrData:         string;
  amountInput:    string;
  setAmountInput: (v: string) => void;
  currency:       Currency;
  setCurrency:    (c: Currency) => void;
  onShare:        () => void;
  onCopy:         () => void;
}) {
  const user = useStore((s) => s.user);

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Comparte tu QR para cobrar</Text>
      <Text style={styles.cardSub}>
        Elige la moneda, el monto (opcional) y comparte.
      </Text>

      {/* ── Selector de moneda ── */}
      <Text style={styles.label}>Moneda a cobrar</Text>
      <View style={styles.currencyRow}>
        {CURRENCIES.map((c) => (
          <TouchableOpacity
            key={c.value}
            style={[styles.currencyChip, currency === c.value && styles.currencyChipActive]}
            onPress={() => setCurrency(c.value)}
            activeOpacity={0.7}
          >
            <Text style={styles.currencyIcon}>{c.icon}</Text>
            <Text style={[styles.currencyLabel, currency === c.value && styles.currencyLabelActive]}>
              {c.label}
            </Text>
            {currency === c.value && (
              <Text style={styles.currencyCheck}>✓</Text>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* ── QR (se regenera al cambiar moneda o monto) ── */}
      <View style={styles.qrWrap}>
        <QRCode
          value={qrData}
          size={200}
          color="#000000"
          backgroundColor="#ffffff"
        />
        {/* Badge de moneda sobre el QR */}
        <View style={styles.currencyBadge}>
          <Text style={styles.currencyBadgeText}>
            {CURRENCIES.find(c => c.value === currency)?.icon} {currency}
          </Text>
        </View>
      </View>

      <Text style={styles.qrName}>{user?.name}</Text>
      <Text style={styles.qrCedula}>Cédula: {user?.cedula}</Text>

      {/* ── Monto opcional ── */}
      <Text style={[styles.label, { marginTop: 20 }]}>Monto a cobrar (opcional)</Text>
      <View style={styles.amountRow}>
        <Text style={styles.dollarSign}>$</Text>
        <TextInput
          style={styles.amountInput}
          placeholder="0.00"
          placeholderTextColor={C.textTertiary}
          keyboardType="decimal-pad"
          value={amountInput}
          onChangeText={setAmountInput}
        />
        <Text style={styles.amountCurrency}>{currency}</Text>
      </View>
      {amountInput.length > 0 && parseFloat(amountInput) > 0 && (
        <Text style={styles.amountHint}>
          El QR incluirá ${parseFloat(amountInput).toFixed(2)} {currency}
        </Text>
      )}

      {/* ── Acciones ── */}
      <TouchableOpacity style={styles.btnPrimary} onPress={onShare} activeOpacity={0.85}>
        <Text style={styles.btnPrimaryText}>📤  Compartir QR</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.btnSecondary} onPress={onCopy} activeOpacity={0.85}>
        <Text style={styles.btnSecondaryText}>🔗  Copiar link de pago</Text>
      </TouchableOpacity>
    </View>
  );
}


// ─── Panel: escanear QR ───────────────────────────────────────────────────────

function ScanQR({ onScannerOpen }: { onScannerOpen: () => void }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Escanear QR</Text>
      <Text style={styles.cardSub}>
        Apunta la cámara al QR de otro usuario para enviarle dinero al instante.
      </Text>

      <View style={styles.scanIllustration}>
        <Text style={styles.scanIcon}>📷</Text>
      </View>

      <TouchableOpacity style={styles.btnPrimary} onPress={onScannerOpen}>
        <Text style={styles.btnPrimaryText}>Abrir cámara</Text>
      </TouchableOpacity>

      <Text style={styles.scanNote}>
        Solo funciona con QR generados en BananaPay.
      </Text>
    </View>
  );
}


// ─── Modal: cámara a pantalla completa ────────────────────────────────────────

function ScannerModal({
  onClose,
  onScanned,
}: {
  onClose:    () => void;
  onScanned:  (data: string) => void;
}) {
  const [permission, requestPermission] = useCameraPermissions();
  const scannedRef = useRef(false);

  if (!permission) return null;

  if (!permission.granted) {
    return (
      <View style={styles.permContainer}>
        <Text style={styles.permTitle}>Permiso de cámara</Text>
        <Text style={styles.permSub}>
          BananaPay necesita acceso a la cámara para escanear QR.
        </Text>
        <TouchableOpacity style={styles.btnPrimary} onPress={requestPermission}>
          <Text style={styles.btnPrimaryText}>Dar permiso</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.btnSecondary, { marginTop: 12 }]} onPress={onClose}>
          <Text style={styles.btnSecondaryText}>Cancelar</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: "#000" }}>
      <CameraView
        style={{ flex: 1 }}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
        onBarcodeScanned={(result) => {
          if (scannedRef.current) return;
          const data = result.data;
          if (!data.startsWith("bananapay://pay")) {
            Alert.alert("QR no válido", "Este QR no es de BananaPay.");
            return;
          }
          scannedRef.current = true;
          onScanned(data);
        }}
      />

      {/* Overlay con marco */}
      <View style={styles.scanOverlay} pointerEvents="none">
        <View style={styles.scanFrame} />
        <Text style={styles.scanLabel}>Apunta al QR de BananaPay</Text>
      </View>

      {/* Botón cerrar */}
      <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
        <Text style={styles.closeBtnText}>✕</Text>
      </TouchableOpacity>
    </View>
  );
}


// ─── Parsear y navegar tras escaneo ──────────────────────────────────────────

function handleQRScanned(data: string, router: ReturnType<typeof useRouter>) {
  try {
    const url      = new URL(data);
    const cedula   = url.searchParams.get("cedula");
    const amount   = url.searchParams.get("amount");
    const currency = url.searchParams.get("currency") ?? "USD";

    if (!cedula) {
      Alert.alert("QR inválido", "Este QR no contiene información de destinatario.");
      return;
    }

    // Navegar a SendScreen con datos pre-rellenos (cedula, monto y moneda)
    router.push({
      pathname: "/send" as any,
      params: {
        prefill_cedula:   cedula,
        prefill_amount:   amount   ?? "",
        prefill_currency: currency,
      },
    });
  } catch {
    Alert.alert("QR inválido", "No se pudo leer el contenido del QR.");
  }
}


// ─── Estilos ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:  { flex: 1, backgroundColor: C.bgAlt },

  header:       { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 56, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  backBtn:      { width: 40, height: 40, justifyContent: "center" },
  backText:     { fontSize: 32, color: C.text, lineHeight: 36 },
  headerTitle:  { fontSize: 17, fontWeight: "600", color: C.text },

  tabs:          { flexDirection: "row", backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  tab:           { flex: 1, paddingVertical: 14, alignItems: "center" },
  tabActive:     { borderBottomWidth: 2, borderBottomColor: C.accent },
  tabText:       { fontSize: 15, color: C.textSub, fontWeight: "500" },
  tabTextActive: { color: C.text, fontWeight: "700" },

  content:  { padding: 20 },
  card:     { backgroundColor: C.bg, borderRadius: 20, padding: 24, ...C.shadow },
  cardTitle:{ fontSize: 22, fontWeight: "700", color: C.text, letterSpacing: -0.3, marginBottom: 6 },
  cardSub:  { fontSize: 14, color: C.textSub, marginBottom: 20, lineHeight: 20 },

  // Selector de moneda
  label:       { fontSize: 12, fontWeight: "600", color: C.textSub, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 10 },
  currencyRow: { flexDirection: "row", gap: 10, marginBottom: 24 },
  currencyChip:{ flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4, paddingVertical: 12, borderRadius: 14, borderWidth: 1.5, borderColor: C.border, backgroundColor: C.bgAlt },
  currencyChipActive: { borderColor: C.accent, backgroundColor: C.accent + "20" },
  currencyIcon:  { fontSize: 16 },
  currencyLabel: { fontSize: 13, fontWeight: "600", color: C.textSub },
  currencyLabelActive: { color: C.text, fontWeight: "700" },
  currencyCheck: { fontSize: 12, color: C.accentDark, fontWeight: "800" },

  // QR
  qrWrap:   { alignItems: "center", padding: 20, backgroundColor: "#fff", borderRadius: 16, marginBottom: 12, borderWidth: 1, borderColor: C.border },
  currencyBadge:     { marginTop: 12, backgroundColor: C.accent, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 5 },
  currencyBadgeText: { fontSize: 13, fontWeight: "700", color: "#000" },
  qrName:   { textAlign: "center", fontSize: 17, fontWeight: "700", color: C.text, marginBottom: 4 },
  qrCedula: { textAlign: "center", fontSize: 13, color: C.textSub },

  // Monto
  amountRow:    { flexDirection: "row", alignItems: "center", backgroundColor: C.bgAlt, borderRadius: 12, paddingHorizontal: 16, marginBottom: 6 },
  dollarSign:   { fontSize: 20, fontWeight: "700", color: C.text, marginRight: 4 },
  amountInput:  { flex: 1, fontSize: 26, fontWeight: "800", color: C.text, paddingVertical: 12 },
  amountCurrency:{ fontSize: 14, fontWeight: "600", color: C.textSub },
  amountHint:   { fontSize: 12, color: C.textSub, marginBottom: 4 },

  // Botones
  btnPrimary:      { backgroundColor: C.accent, borderRadius: 14, paddingVertical: 17, alignItems: "center", marginTop: 20 },
  btnPrimaryText:  { fontSize: 16, fontWeight: "700", color: "#000" },
  btnSecondary:    { backgroundColor: C.bgAlt, borderRadius: 14, paddingVertical: 15, alignItems: "center", marginTop: 10 },
  btnSecondaryText:{ fontSize: 15, fontWeight: "600", color: C.text },

  // Scan panel
  scanIllustration: { alignItems: "center", justifyContent: "center", paddingVertical: 40 },
  scanIcon:         { fontSize: 72 },
  scanNote:         { fontSize: 13, color: C.textTertiary, textAlign: "center", marginTop: 16, lineHeight: 18 },

  // Scanner modal
  scanOverlay: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center" },
  scanFrame:   { width: 240, height: 240, borderRadius: 20, borderWidth: 3, borderColor: C.accent, marginBottom: 20 },
  scanLabel:   { color: "#fff", fontSize: 15, fontWeight: "600", textShadowColor: "#000", textShadowRadius: 4, textShadowOffset: { width: 0, height: 1 } },
  closeBtn:    { position: "absolute", top: Platform.OS === "ios" ? 56 : 24, right: 20, width: 40, height: 40, borderRadius: 20, backgroundColor: "#00000080", alignItems: "center", justifyContent: "center" },
  closeBtnText:{ color: "#fff", fontSize: 18, fontWeight: "700" },

  // Permiso
  permContainer: { flex: 1, justifyContent: "center", alignItems: "center", padding: 32, backgroundColor: C.bgAlt },
  permTitle:     { fontSize: 22, fontWeight: "700", color: C.text, marginBottom: 12 },
  permSub:       { fontSize: 15, color: C.textSub, textAlign: "center", lineHeight: 22, marginBottom: 32 },
});
