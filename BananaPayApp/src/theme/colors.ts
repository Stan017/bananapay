export const C = {
  // Fondos
  bg:          "#ffffff",
  bgAlt:       "#f2f2f7",   // fondo de secciones agrupadas (Apple)
  surface:     "#ffffff",

  // Bordes
  border:      "#e5e5ea",
  separator:   "#c6c6c8",

  // Texto
  text:        "#1c1c1e",
  textSub:     "#8e8e93",
  textTertiary:"#aeaeb2",

  // Acento banana — nunca cambia
  accent:      "#facc15",
  accentDark:  "#b45309",   // texto sobre amarillo claro

  // Sistema Apple
  success:     "#34c759",
  danger:      "#ff3b30",
  blue:        "#007aff",
  indigo:      "#5856d6",

  // Sombra estándar
  shadow: {
    shadowColor:   "#000",
    shadowOffset:  { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius:  12,
    elevation:     3,
  },
} as const;
