import axios from "axios";
import * as SecureStore from "expo-secure-store";

// Configura EXPO_PUBLIC_API_URL en .env (ver .env.example)
// En producción debe ser HTTPS — nunca HTTP con datos financieros
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "https://api.bananapay.ec";

const api = axios.create({
  baseURL: API_URL,
  timeout: 15_000, // 15 s — evita loading infinito en redes lentas
});

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync("bp_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const login = (cedula: string, phone: string, pin: string) =>
  api.post("/app/auth/login", { cedula, phone, pin }).then((r) => r.data);

export const getBalance = () =>
  api.get("/app/me/balance").then((r) => r.data);

export const getHistory = (limit = 20) =>
  api.get(`/app/me/history?limit=${limit}`).then((r) => r.data);

export const getProfile = () =>
  api.get("/app/me/profile").then((r) => r.data);

export const validateRecipient = (cedula: string, phone: string) =>
  api.get(`/app/transfer/validate?cedula=${cedula}&phone=${phone}`).then((r) => r.data);

export const sendTransfer = (body: {
  to_cedula: string;
  to_phone:  string;
  amount:    number;
  currency:  string;
  pin:       string;
}) => api.post("/app/transfer/send", body).then((r) => r.data);

export const getDepositInfo = () =>
  api.get("/app/deposit/info").then((r) => r.data);

export const requestFiatDeposit = (body: {
  amount:           number;
  bank_name:        string;
  reference_number: string;
}) => api.post("/app/deposit/fiat", body).then((r) => r.data);

export const getWithdrawInfo = () =>
  api.get("/app/withdraw/info").then((r) => r.data);

export const withdrawFiat = (body: {
  amount:          number;
  withdrawal_type: string;
  bank_name:       string;
  account_type:    string;
  account_number:  string;
  account_holder:  string;
  pin:             string;
}) => api.post("/app/withdraw/fiat", body).then((r) => r.data);

export const withdrawCrypto = (body: {
  currency:   string;
  amount:     number;
  to_address: string;
  pin:        string;
}) => api.post("/app/withdraw/crypto", body).then((r) => r.data);

export const updatePushToken = (token: string) =>
  api.patch("/app/me/push-token", { token }).then((r) => r.data);

export default api;
