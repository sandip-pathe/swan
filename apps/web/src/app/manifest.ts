import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SWAN Trade",
    short_name: "SWAN",
    description: "Your intraday options paper trading workspace",
    start_url: "/",
    scope: "/",
    display: "standalone",
    id: "/",
    background_color: "#ffffff",
    theme_color: "#ffffff",
    categories: ["finance", "education"],
    shortcuts: [
      { name: "Chat with SWAN", short_name: "Chat", url: "/#chat" },
      { name: "Your dashboard", short_name: "Dashboard", url: "/#home" },
      { name: "Trade workspace", short_name: "Trade", url: "/#markets" },
    ],
    lang: "en-IN",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
