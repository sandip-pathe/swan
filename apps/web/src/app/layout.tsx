import type { Metadata, Viewport } from "next";
import "./globals.css";
import Pwa from "./pwa";

export const metadata: Metadata = {
  title: "SWAN Trade",
  description: "Autonomous intraday options paper trading",
  appleWebApp: { capable: true, title: "SWAN Trade", statusBarStyle: "default" },
  icons: { icon: "/icon-192.png", apple: "/icon-192.png" },
};

export const viewport: Viewport = { themeColor: "#ffffff", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}<Pwa /></body></html>;
}
