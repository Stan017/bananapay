import { Redirect } from "expo-router";
import { useStore } from "@/src/store/useStore";
import SendScreen from "@/src/screens/send/SendScreen";

export default function SendPage() {
  const token = useStore((s) => s.token);
  if (!token) return <Redirect href="/login" />;
  return <SendScreen />;
}
