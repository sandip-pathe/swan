import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SWAN Trade",
    short_name: "SWAN",
    description: "Your intraday options paper trading workspace",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#0b1218",
    theme_color: "#0b1218",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
