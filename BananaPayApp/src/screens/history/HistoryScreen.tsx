import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";
import { Text } from "@/src/components/Text";

import { getHistory } from "@/src/services/api";
import { C } from "@/src/theme/colors";
import { fmtCrypto, fmtUSD } from "@/src/utils/format";

// ─── Tipos ────────────────────────────────────────────────────────────────────

interface Tx {
  id:         string;
  type:       "deposit" | "withdrawal" | "transfer";
  currency:   string;
  amount:     number;
  fee:        number;
  direction:  "in" | "out";
  other_name: string;
  status:     "completed" | "pending" | "rejected";
  created_at: string;
}

type Filter = "all" | "deposit" | "withdrawal" | "transfer";

// ─── Helpers visuales ─────────────────────────────────────────────────────────

function txIcon(tx: Tx): string {
  if (tx.type === "deposit")    return "📥";
  if (tx.type === "withdrawal") return "📤";
  return tx.direction === "in" ? "💸" : "💸";
}

function txColor(tx: Tx): string {
  if (tx.direction === "in")  return C.success;
  if (tx.type === "withdrawal") return C.danger;
  return "#f97316";  // naranja para transferencias salientes
}

function txLabel(tx: Tx): string {
  if (tx.type === "deposit")    return "Depósito";
  if (tx.type === "withdrawal") return "Retiro";
  return tx.direction === "in" ? "Recibido" : "Enviado";
}

function txSubtitle(tx: Tx): string {
  if (tx.type === "transfer") {
    const name = tx.other_name?.split(" ")[0] || "Usuario";
    return tx.direction === "in" ? `De ${name}` : `A ${name}`;
  }
  return "BananaPay";
}

function fmtAmount(tx: Tx): string {
  const prefix = tx.direction === "in" ? "+" : "−";
  if (tx.currency === "USD") return `${prefix}${fmtUSD(tx.amount)}`;
  return `${prefix}${fmtCrypto(tx.amount, tx.currency)}`;
}

function fmtDate(iso: string): string {
  if (!iso) return "";
  const d   = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);

  if (diffDays === 0) return "Hoy " + d.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 1) return "Ayer " + d.toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString("es-EC", { day: "2-digit", month: "short", year: diffDays > 365 ? "numeric" : undefined });
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all",        label: "Todos"      },
  { key: "transfer",   label: "Envíos"     },
  { key: "deposit",    label: "Depósitos"  },
  { key: "withdrawal", label: "Retiros"    },
];

// ─── Componente principal ─────────────────────────────────────────────────────

export default function HistoryScreen() {
  const [txs,        setTxs]        = useState<Tx[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter,     setFilter]     = useState<Filter>("all");
  const [limit,      setLimit]      = useState(20);
  const [loadingMore,setLoadingMore]= useState(false);

  const load = async (lim = limit, reset = false) => {
    try {
      const data = await getHistory(lim);
      // reset=true reemplaza la lista (pull-to-refresh)
      // reset=false reemplaza también porque la API siempre retorna los últimos N
      setTxs(data);
    } catch {
      // silencioso — el usuario puede pulsar refresh
    } finally {
      setLoading(false);
      setRefreshing(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => { load(); }, []);

  const onRefresh = () => {
    setRefreshing(true);
    setLimit(20);
    load(20, true);
  };

  const loadMore = () => {
    if (loadingMore) return;
    setLoadingMore(true);
    const newLimit = limit + 20;
    setLimit(newLimit);
    load(newLimit);
  };

  const filtered = filter === "all" ? txs : txs.filter((t) => t.type === filter);

  // ── Empty state ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.accent} size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Historial</Text>
      </View>

      {/* Filtros */}
      <View style={styles.filtersWrap}>
        <FlatList
          data={FILTERS}
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filters}
          keyExtractor={(f) => f.key}
          renderItem={({ item: f }) => (
            <TouchableOpacity
              style={[styles.filterPill, filter === f.key && styles.filterPillActive]}
              onPress={() => setFilter(f.key)}
            >
              <Text style={[styles.filterText, filter === f.key && styles.filterTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          )}
        />
      </View>

      {/* Lista */}
      <FlatList
        data={filtered}
        keyExtractor={(tx) => tx.id}
        contentContainerStyle={filtered.length === 0 ? styles.emptyContainer : styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.accent} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>📋</Text>
            <Text style={styles.emptyTitle}>Sin movimientos</Text>
            <Text style={styles.emptySub}>
              {filter === "all"
                ? "Tus transacciones aparecerán aquí."
                : "No hay transacciones de este tipo aún."}
            </Text>
          </View>
        }
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        onEndReached={txs.length >= limit ? loadMore : undefined}
        onEndReachedThreshold={0.3}
        ListFooterComponent={
          loadingMore ? (
            <View style={styles.loadMoreWrap}>
              <ActivityIndicator color={C.accent} size="small" />
            </View>
          ) : null
        }
        renderItem={({ item: tx }) => <TxRow tx={tx} />}
      />

    </View>
  );
}

// ─── Fila de transacción ──────────────────────────────────────────────────────

function TxRow({ tx }: { tx: Tx }) {
  const color = txColor(tx);

  return (
    <View style={styles.txRow}>
      {/* Ícono */}
      <View style={[styles.txIconWrap, { backgroundColor: color + "15" }]}>
        <Text style={styles.txIcon}>{txIcon(tx)}</Text>
      </View>

      {/* Info */}
      <View style={styles.txInfo}>
        <Text style={styles.txLabel}>{txLabel(tx)}</Text>
        <Text style={styles.txSub}>{txSubtitle(tx)}</Text>
        <Text style={styles.txDate}>{fmtDate(tx.created_at)}</Text>
      </View>

      {/* Monto + status */}
      <View style={styles.txRight}>
        <Text style={[styles.txAmount, { color }]}>{fmtAmount(tx)}</Text>
        {tx.status !== "completed" && (
          <View style={[styles.statusBadge, tx.status === "pending" ? styles.badgePending : styles.badgeRejected]}>
            <Text style={[styles.statusText, tx.status === "pending" ? styles.statusPending : styles.statusRejected]}>
              {tx.status === "pending" ? "Pendiente" : "Rechazado"}
            </Text>
          </View>
        )}
        {tx.currency !== "USD" && tx.status === "completed" && (
          <Text style={styles.txCurrency}>{tx.currency}</Text>
        )}
      </View>
    </View>
  );
}

// ─── Estilos ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bgAlt },
  center:    { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.bgAlt },

  header:      { paddingTop: 60, paddingHorizontal: 24, paddingBottom: 16, backgroundColor: C.bg },
  headerTitle: { fontSize: 28, fontWeight: "800", color: C.text, letterSpacing: -0.5 },

  filtersWrap: { backgroundColor: C.bg, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  filters:     { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  filterPill:       { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: C.bgAlt, borderWidth: 1, borderColor: C.border },
  filterPillActive: { backgroundColor: C.accent, borderColor: C.accent },
  filterText:       { fontSize: 14, color: C.textSub, fontWeight: "500" },
  filterTextActive: { color: "#000", fontWeight: "700" },

  listContent:    { paddingVertical: 12, paddingHorizontal: 16 },
  emptyContainer: { flex: 1 },
  separator:      { height: StyleSheet.hairlineWidth, backgroundColor: C.border, marginLeft: 76 },

  // Transaction row
  txRow:     { flexDirection: "row", alignItems: "center", paddingVertical: 14, backgroundColor: C.bg, borderRadius: 0 },
  txIconWrap:{ width: 48, height: 48, borderRadius: 24, justifyContent: "center", alignItems: "center", marginRight: 12 },
  txIcon:    { fontSize: 20 },
  txInfo:    { flex: 1 },
  txLabel:   { fontSize: 15, fontWeight: "600", color: C.text, marginBottom: 2 },
  txSub:     { fontSize: 13, color: C.textSub, marginBottom: 2 },
  txDate:    { fontSize: 12, color: C.textTertiary },
  txRight:   { alignItems: "flex-end", gap: 4 },
  txAmount:  { fontSize: 16, fontWeight: "700" },
  txCurrency:{ fontSize: 11, color: C.textTertiary },

  statusBadge:    { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgePending:   { backgroundColor: "#f59e0b20" },
  badgeRejected:  { backgroundColor: C.danger + "15" },
  statusText:     { fontSize: 11, fontWeight: "600" },
  statusPending:  { color: "#f59e0b" },
  statusRejected: { color: C.danger },

  // Empty
  empty:      { flex: 1, alignItems: "center", justifyContent: "center", paddingTop: 80 },
  emptyIcon:  { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: "700", color: C.text, marginBottom: 8 },
  emptySub:   { fontSize: 14, color: C.textSub, textAlign: "center", paddingHorizontal: 32 },

  loadMoreWrap: { paddingVertical: 20, alignItems: "center" },
});
