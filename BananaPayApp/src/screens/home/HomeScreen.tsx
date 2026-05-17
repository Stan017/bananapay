import * as SecureStore from "expo-secure-store";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";
import { Text } from "@/src/components/Text";

import { getBalance, getHistory, getProfile } from "@/src/services/api";
import { useStore } from "@/src/store/useStore";
import { fmtUSD, fmtCrypto } from "@/src/utils/format";
import { C } from "@/src/theme/colors";

interface Tx {
  id: string;
  type: "deposit" | "withdrawal" | "transfer";
  currency: string;
  amount: number;
  direction: "in" | "out";
  other_name: string;
  status: "completed" | "pending" | "rejected";
  created_at: string;
}

function txIcon(tx: Tx) {
  if (tx.type === "deposit")    return "📥";
  if (tx.type === "withdrawal") return "📤";
  return tx.direction === "in" ? "⬇️" : "⬆️";
}

function txColor(tx: Tx) {
  if (tx.direction === "in")     return C.success;
  if (tx.type === "withdrawal")  return C.danger;
  return "#f97316";
}

function txLabel(tx: Tx) {
  if (tx.type === "deposit")    return "Depósito";
  if (tx.type === "withdrawal") return "Retiro";
  return tx.direction === "in" ? "Recibido" : "Enviado";
}

function txSubtitle(tx: Tx) {
  if (tx.type === "transfer") {
    const name = tx.other_name?.split(" ")[0] || "Usuario";
    return tx.direction === "in" ? `De ${name}` : `A ${name}`;
  }
  return "BananaPay";
}

function fmtAmount(tx: Tx) {
  const prefix = tx.direction === "in" ? "+" : "−";
  if (tx.currency === "USD") return `${prefix}${fmtUSD(tx.amount)}`;
  return `${prefix}${fmtCrypto(tx.amount, tx.currency)}`;
}

function fmtDateShort(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 1) return "Ayer";
  return d.toLocaleDateString("es-EC", { day: "2-digit", month: "short" });
}

// ─── Acción rápida ────────────────────────────────────────────────────────────

const ACTIONS = [
  { icon: "💸", label: "Enviar",    route: "/send",     bg: "#fff3e0" },
  { icon: "⚡", label: "Cobrar",    route: "/qr",       bg: "#fff9e0" },
  { icon: "📥", label: "Depositar", route: "/deposit",  bg: "#e8f5e9" },
  { icon: "📤", label: "Retirar",   route: "/withdraw", bg: "#fce4ec" },
];

// ─── Pantalla principal ───────────────────────────────────────────────────────

export default function HomeScreen() {
  const router = useRouter();
  const { user, setAuth, setBalances, balances, logout } = useStore();
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [recentTxs,  setRecentTxs]  = useState<Tx[]>([]);

  const load = async () => {
    try {
      const [bal, profile, history] = await Promise.all([
        getBalance(),
        getProfile(),
        getHistory(5).catch(() => []),
      ]);
      setBalances(bal);
      setRecentTxs(history ?? []);
      const token = await SecureStore.getItemAsync("bp_token");
      setAuth(token || "", {
        id:     profile.id,
        name:   profile.name,
        phone:  profile.phone,
        cedula: profile.cedula,
      });
    } catch {
      await SecureStore.deleteItemAsync("bp_token");
      logout();
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  const primerNombre = user?.name?.split(" ")[0] || "";
  const iniciales    = user?.name?.split(" ").map((n: string) => n[0]).slice(0, 2).join("") || "BP";
  const hasCrypto    = (balances?.usdt ?? 0) > 0 || (balances?.usdc ?? 0) > 0;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => { setRefreshing(true); load(); }}
          tintColor={C.accent}
        />
      }
    >
      {/* ── Header ── */}
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>Hola, {primerNombre} 👋</Text>
          <Text style={styles.phone}>{user?.phone}</Text>
        </View>
        <TouchableOpacity
          style={styles.avatar}
          onPress={() => router.push("/(tabs)/profile" as any)}
          activeOpacity={0.8}
        >
          <Text style={styles.avatarText}>{iniciales}</Text>
        </TouchableOpacity>
      </View>

      {/* ── Balance card ── */}
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>Saldo disponible</Text>
        <Text style={styles.balanceAmount}>{fmtUSD(balances?.total ?? 0)}</Text>

        {hasCrypto && (
          <View style={styles.cryptoRow}>
            <View style={styles.cryptoPill}>
              <Text style={styles.cryptoPillText}>🏦 {fmtUSD(balances?.fiat ?? 0)}</Text>
            </View>
            {(balances?.usdt ?? 0) > 0 && (
              <View style={styles.cryptoPill}>
                <Text style={styles.cryptoPillText}>🪙 {fmtCrypto(balances?.usdt ?? 0, "USDT")}</Text>
              </View>
            )}
            {(balances?.usdc ?? 0) > 0 && (
              <View style={styles.cryptoPill}>
                <Text style={styles.cryptoPillText}>🔵 {fmtCrypto(balances?.usdc ?? 0, "USDC")}</Text>
              </View>
            )}
          </View>
        )}

        {/* Barra decorativa */}
        <View style={styles.cardDeco}>
          <View style={[styles.cardDecoCircle, { right: -20, top: -40, width: 120, height: 120, opacity: 0.12 }]} />
          <View style={[styles.cardDecoCircle, { right: 60,  top: -20, width: 80,  height: 80,  opacity: 0.08 }]} />
        </View>
      </View>

      {/* ── Acciones rápidas ── */}
      <View style={styles.actionsWrap}>
        {ACTIONS.map((a) => (
          <TouchableOpacity
            key={a.route}
            style={styles.actionBtn}
            onPress={() => router.push(a.route as any)}
            activeOpacity={0.7}
          >
            <View style={[styles.actionIconWrap, { backgroundColor: a.bg }]}>
              <Text style={styles.actionIcon}>{a.icon}</Text>
            </View>
            <Text style={styles.actionLabel}>{a.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Movimientos recientes ── */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Últimos movimientos</Text>
          <TouchableOpacity onPress={() => router.push("/(tabs)/history" as any)}>
            <Text style={styles.sectionLink}>Ver todo</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.txCard}>
          {recentTxs.length === 0 ? (
            <View style={styles.emptyTx}>
              <Text style={styles.emptyTxIcon}>💫</Text>
              <Text style={styles.emptyTxText}>Sin movimientos aún</Text>
              <Text style={styles.emptyTxSub}>Tus transacciones aparecerán aquí</Text>
            </View>
          ) : (
            recentTxs.map((tx, i) => {
              const color = txColor(tx);
              return (
                <View key={tx.id} style={[styles.txRow, i < recentTxs.length - 1 && styles.txRowBorder]}>
                  <View style={[styles.txIcon, { backgroundColor: color + "15" }]}>
                    <Text style={styles.txIconText}>{txIcon(tx)}</Text>
                  </View>
                  <View style={styles.txInfo}>
                    <Text style={styles.txLabel}>{txLabel(tx)}</Text>
                    <Text style={styles.txSub}>{txSubtitle(tx)}</Text>
                  </View>
                  <View style={styles.txRight}>
                    <Text style={[styles.txAmount, { color }]}>{fmtAmount(tx)}</Text>
                    <Text style={styles.txDate}>{fmtDateShort(tx.created_at)}</Text>
                  </View>
                </View>
              );
            })
          )}
        </View>
      </View>

      <Text style={styles.securityNote}>🔒 Nunca compartas tu PIN con nadie</Text>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bgAlt },
  content:   { paddingBottom: 48 },
  center:    { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.bgAlt },

  // Header
  header:     { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 24, paddingTop: 60, paddingBottom: 20, backgroundColor: C.bg },
  greeting:   { fontSize: 22, fontWeight: "800", color: C.text, letterSpacing: -0.4 },
  phone:      { fontSize: 13, color: C.textSub, marginTop: 2 },
  avatar:     { width: 42, height: 42, borderRadius: 21, backgroundColor: C.accent, justifyContent: "center", alignItems: "center" },
  avatarText: { fontSize: 14, fontWeight: "800", color: "#000" },

  // Balance card
  balanceCard: {
    margin: 20,
    backgroundColor: C.accent,
    borderRadius: 28,
    padding: 28,
    alignItems: "center",
    overflow: "hidden",
    ...C.shadow,
  },
  balanceLabel:  { fontSize: 13, fontWeight: "600", color: "#00000070", marginBottom: 6, letterSpacing: 0.3 },
  balanceAmount: { fontSize: 50, fontWeight: "900", color: "#000", letterSpacing: -2 },
  cryptoRow:     { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8, marginTop: 16 },
  cryptoPill:    { backgroundColor: "#00000015", borderRadius: 20, paddingHorizontal: 12, paddingVertical: 6 },
  cryptoPillText:{ fontSize: 12, fontWeight: "700", color: "#000000cc" },
  cardDeco:      { position: "absolute", right: 0, top: 0, bottom: 0, width: "50%" },
  cardDecoCircle:{ position: "absolute", borderRadius: 999, backgroundColor: "#000" },

  // Acciones
  actionsWrap: { flexDirection: "row", marginHorizontal: 20, gap: 12, marginBottom: 24 },
  actionBtn:   { flex: 1, alignItems: "center", backgroundColor: C.bg, borderRadius: 20, paddingVertical: 18, ...C.shadow },
  actionIconWrap:{ width: 48, height: 48, borderRadius: 16, justifyContent: "center", alignItems: "center", marginBottom: 8 },
  actionIcon:  { fontSize: 22 },
  actionLabel: { fontSize: 12, color: C.text, fontWeight: "700", letterSpacing: -0.2 },

  // Sección
  section:      { marginHorizontal: 20 },
  sectionHeader:{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  sectionTitle: { fontSize: 17, fontWeight: "800", color: C.text, letterSpacing: -0.3 },
  sectionLink:  { fontSize: 14, fontWeight: "600", color: C.accentDark },

  // Tx card
  txCard:     { backgroundColor: C.bg, borderRadius: 20, overflow: "hidden", ...C.shadow },
  txRow:      { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 14 },
  txRowBorder:{ borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  txIcon:     { width: 44, height: 44, borderRadius: 14, justifyContent: "center", alignItems: "center", marginRight: 12 },
  txIconText: { fontSize: 18 },
  txInfo:     { flex: 1 },
  txLabel:    { fontSize: 15, fontWeight: "600", color: C.text, marginBottom: 2 },
  txSub:      { fontSize: 13, color: C.textSub },
  txRight:    { alignItems: "flex-end" },
  txAmount:   { fontSize: 15, fontWeight: "700", marginBottom: 2 },
  txDate:     { fontSize: 12, color: C.textTertiary },

  // Empty txs
  emptyTx:    { alignItems: "center", paddingVertical: 32 },
  emptyTxIcon:{ fontSize: 36, marginBottom: 10 },
  emptyTxText:{ fontSize: 16, fontWeight: "700", color: C.text, marginBottom: 4 },
  emptyTxSub: { fontSize: 13, color: C.textSub },

  securityNote: { textAlign: "center", fontSize: 12, color: C.textTertiary, marginTop: 28 },
});
