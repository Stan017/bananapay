import * as LocalAuthentication from "expo-local-authentication";
import * as SecureStore from "expo-secure-store";

export const BIOMETRIC_KEY = "bp_biometric_enabled";

/** ¿El dispositivo tiene hardware biométrico Y tiene datos enrollados? */
export async function isBiometricAvailable(): Promise<boolean> {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  if (!hasHardware) return false;
  return LocalAuthentication.isEnrolledAsync();
}

/** ¿El usuario activó el biométrico en BananaPay? */
export async function isBiometricEnabled(): Promise<boolean> {
  const val = await SecureStore.getItemAsync(BIOMETRIC_KEY);
  return val === "true";
}

export async function enableBiometric(): Promise<void> {
  await SecureStore.setItemAsync(BIOMETRIC_KEY, "true");
}

export async function disableBiometric(): Promise<void> {
  await SecureStore.deleteItemAsync(BIOMETRIC_KEY);
}

/** Tipo de biométrico disponible en el dispositivo */
export async function getBiometricType(): Promise<"face" | "fingerprint" | "none"> {
  const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
  if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) return "face";
  if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT))        return "fingerprint";
  return "none";
}

/** Lanza el prompt nativo del OS. Devuelve true si el usuario pasó. */
export async function authenticate(): Promise<boolean> {
  const result = await LocalAuthentication.authenticateAsync({
    promptMessage:         "Ingresa a BananaPay",
    cancelLabel:           "Usar PIN de BananaPay",
    // true → solo biométrico puro. Si falla, el usuario vuelve al login
    // con su PIN de BananaPay — nunca el PIN del dispositivo que puede
    // conocer otra persona con acceso físico al teléfono.
    disableDeviceFallback: true,
  });
  return result.success;
}
