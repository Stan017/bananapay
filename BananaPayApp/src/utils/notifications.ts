/**
 * Gestión de push notifications con expo-notifications.
 *
 * NOTA: Las push notifications NO funcionan en Expo Go (SDK 53+).
 * Solo funcionan en development builds y production builds.
 *
 * IMPORTANTE: expo-notifications se carga con require() dinámico DENTRO
 * de la función para evitar que sus side effects se ejecuten en Expo Go.
 * Un import estático en el top-level dispara DevicePushTokenAutoRegistration
 * incluso antes de que nuestro guard isExpoGo pueda actuar.
 */

import Constants from "expo-constants";
import * as Device from "expo-device";
import { Platform } from "react-native";
import api from "@/src/services/api";

// Detectar si corremos dentro de Expo Go
const isExpoGo = Constants.appOwnership === "expo";

/**
 * Registra el dispositivo para push notifications.
 * Llama a esta función después de que el usuario inicia sesión.
 * Es idempotente y silenciosa — nunca bloquea el flujo principal.
 */
export async function registerForPushNotifications(): Promise<void> {
  // En Expo Go no funciona desde SDK 53 — salir silenciosamente
  if (isExpoGo) return;

  // Solo en dispositivo físico
  if (!Device.isDevice) return;

  try {
    // require() dinámico: el módulo (y sus side effects) solo se carga
    // si llegamos hasta aquí, es decir, nunca en Expo Go.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Notifications = require("expo-notifications");

    // Configurar el handler
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert:  true,
        shouldPlaySound:  true,
        shouldSetBadge:   true,
        shouldShowBanner: true,
        shouldShowList:   true,
      }),
    });

    // Canal de Android (requerido para Android 8+)
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("bananapay", {
        name:             "BananaPay",
        importance:       Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor:       "#FFD700",
        sound:            "default",
      });
    }

    // Pedir permiso
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== "granted") return;

    // Obtener token de Expo
    const tokenData = await Notifications.getExpoPushTokenAsync({
      projectId: Constants.expoConfig?.extra?.eas?.projectId,
    });

    const token = tokenData.data;
    if (!token) return;

    // Enviarlo al backend
    await api.patch("/app/me/push-token", { token });

  } catch {
    // No crítico — la app funciona perfectamente sin push
  }
}
