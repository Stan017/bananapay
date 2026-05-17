import { Redirect } from "expo-router";
import { useStore } from "@/src/store/useStore";
import QRScreen from "@/src/screens/qr/QRScreen";

export default function QRPage() {
  const token = useStore((s) => s.token);
  if (!token) return <Redirect href="/login" />;
  return <QRScreen />;
}
