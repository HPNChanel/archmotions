// Theme styles for the Studio UI + canvas, mirroring archmotion ThemeConfig so
// what the user sees in the editor matches the exported video/Lottie.

export interface ThemeStyle {
  id: string;
  label: string;
  bg: string;
  nodeFill: string;
  nodeBorder: string;
  text: string;
  connStroke: string;
}

// Colors derived from archmotion/renderer/theme.py ThemeConfig values.
export const THEMES: ThemeStyle[] = [
  {
    id: "dark_terminal",
    label: "Dark Terminal",
    bg: "#12121c",
    nodeFill: "#1e1e2e",
    nodeBorder: "#45475a",
    text: "#cdd6f4",
    connStroke: "#585b70",
  },
  {
    id: "neon_cyber",
    label: "Neon Cyber",
    bg: "#08050f",
    nodeFill: "#0d0b18",
    nodeBorder: "#ff007f",
    text: "#39ff14",
    connStroke: "#00ffff",
  },
  {
    id: "blueprint",
    label: "Blueprint",
    bg: "#0d244d",
    nodeFill: "#0a2240",
    nodeBorder: "#ffffffbb",
    text: "#e2e8f0",
    connStroke: "#ffffff88",
  },
  {
    id: "light_paper",
    label: "Light Paper",
    bg: "#fafaf5",
    nodeFill: "#ffffff",
    nodeBorder: "#2d3748",
    text: "#1a202c",
    connStroke: "#4a5568",
  },
];

export function getTheme(id: string): ThemeStyle {
  return THEMES.find((t) => t.id === id) ?? THEMES[0];
}
