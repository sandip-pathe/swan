import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { validAppearance } from "@/lib/browser-preferences";
import "./globals.css";
import "./workspace.css";
import "./native.css";
import "./bot.css";
import Pwa from "./pwa";

export const metadata: Metadata = {
  title: "SWAN — Chat & insights",
  description: "Market observations, evidence and explanations",
  appleWebApp: { capable: true, title: "SWAN", statusBarStyle: "default" },
  icons: { icon: "/icon-192.png", apple: "/icon-192.png" },
};

export const viewport: Viewport = { themeColor: "#ffffff", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const appearance = (await cookies()).get("swan_appearance")?.value;
  return <html lang="en" data-theme={validAppearance(appearance) && appearance !== "system" ? appearance : undefined} suppressHydrationWarning><body><Pwa>{children}</Pwa></body></html>;
}
