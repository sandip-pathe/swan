import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SWAN Trade",
  description: "Autonomous intraday options paper trading",
  appleWebApp: { capable: true, title: "SWAN Trade", statusBarStyle: "black-translucent" },
  icons: { apple: "/icon-192.png" },
};

export const viewport: Viewport = { themeColor: "#0b1218" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
