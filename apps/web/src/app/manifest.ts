import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SWAN market bot",
    short_name: "SWAN",
    description: "Market chat and evidence-backed insights",
    start_url: "/",
    scope: "/",
    display: "standalone",
    id: "/",
    background_color: "#ffffff",
    theme_color: "#ffffff",
    categories: ["finance", "education"],
    shortcuts: [
      { name: "Chat with SWAN", short_name: "Chat", url: "/#chat" },
      { name: "Market insights", short_name: "Insights", url: "/#insights" },
    ],
    lang: "en-IN",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
