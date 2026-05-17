import { create } from "zustand";

interface Balances {
  fiat:  number;
  usdt:  number;
  usdc:  number;
  total: number;
}

interface User {
  id:     string;
  name:   string;
  phone:  string;
  cedula: string;
}

interface AppStore {
  token:            string | null;
  user:             User   | null;
  balances:         Balances | null;
  biometricPending: boolean;

  setAuth:             (token: string, user: User) => void;
  setBalances:         (b: Balances) => void;
  setBiometricPending: (v: boolean) => void;
  logout:              () => void;
}

export const useStore = create<AppStore>((set) => ({
  token:            null,
  user:             null,
  balances:         null,
  biometricPending: false,

  // Al setAuth siempre limpiamos biometricPending
  setAuth:             (token, user) => set({ token, user, biometricPending: false }),
  setBalances:         (balances)    => set({ balances }),
  setBiometricPending: (v)           => set({ biometricPending: v }),
  logout:              ()            => set({ token: null, user: null, balances: null, biometricPending: false }),
}));
