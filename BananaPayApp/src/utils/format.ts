export const fmtUSD = (n: number) =>
  "$" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

export const fmtCrypto = (n: number, currency: string) =>
  `${n.toFixed(2)} ${currency}`;

export const fmtDate = (iso: string) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("es-EC", {
    day: "2-digit", month: "short", year: "numeric",
  });
};
