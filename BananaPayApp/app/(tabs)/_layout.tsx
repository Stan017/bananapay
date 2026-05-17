import FontAwesome from "@expo/vector-icons/FontAwesome";
import { Redirect, Tabs } from "expo-router";
import { useStore } from "@/src/store/useStore";
import { C } from "@/src/theme/colors";

function Icon(props: { name: React.ComponentProps<typeof FontAwesome>["name"]; color: string }) {
  return <FontAwesome size={22} style={{ marginBottom: -3 }} {...props} />;
}

export default function TabLayout() {
  const token = useStore((s) => s.token);

  if (!token) return <Redirect href="/login" />;

  return (
    <Tabs
      screenOptions={{
        headerShown:             false,
        tabBarStyle:             {
          backgroundColor: C.bg,
          borderTopColor:  C.border,
          borderTopWidth:  0.5,
        },
        tabBarActiveTintColor:   "#000000",
        tabBarInactiveTintColor: C.textSub,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Inicio",    tabBarIcon: ({ color }) => <Icon name="home"  color={color} /> }}
      />
      <Tabs.Screen
        name="history"
        options={{ title: "Historial", tabBarIcon: ({ color }) => <Icon name="list"  color={color} /> }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: "Perfil",    tabBarIcon: ({ color }) => <Icon name="user"  color={color} /> }}
      />
    </Tabs>
  );
}
