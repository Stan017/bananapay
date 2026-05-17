import { Redirect } from "expo-router";
import { useStore } from "@/src/store/useStore";
import DepositScreen from "@/src/screens/deposit/DepositScreen";

export default function DepositPage() {
  const token = useStore((s) => s.token);
  if (!token) return <Redirect href="/login" />;
  return <DepositScreen />;
}
