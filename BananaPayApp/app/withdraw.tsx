import { Redirect } from "expo-router";
import { useStore } from "@/src/store/useStore";
import WithdrawScreen from "@/src/screens/withdraw/WithdrawScreen";

export default function WithdrawPage() {
  const token = useStore((s) => s.token);
  if (!token) return <Redirect href="/login" />;
  return <WithdrawScreen />;
}
