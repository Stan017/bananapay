import { Redirect } from "expo-router";
import { useStore } from "@/src/store/useStore";
import LoginScreen from "@/src/screens/auth/LoginScreen";
import BiometricScreen from "@/src/screens/auth/BiometricScreen";

export default function LoginPage() {
  const token            = useStore((s) => s.token);
  const biometricPending = useStore((s) => s.biometricPending);

  if (token)            return <Redirect href="/(tabs)" />;
  if (biometricPending) return <BiometricScreen />;
  return <LoginScreen />;
}
