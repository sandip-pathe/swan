export type IconName = "home" | "markets" | "orders" | "history" | "account" | "arrow" | "refresh" | "shield" | "wallet" | "download" | "logout" | "signal";
const paths: Record<IconName, string> = {
  home: "m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z",
  markets: "M4 20V10m5 10V4m6 16v-8m5 8V7M2 20h20",
  orders: "M8 3H5v18h14V3h-3M9 3h6v4H9ZM8 12h8m-8 4h5",
  history: "M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2",
  account: "M20 21v-2a6 6 0 0 0-6-6h-4a6 6 0 0 0-6 6v2M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  arrow: "M5 12h14m-6-6 6 6-6 6",
  refresh: "M20 7a9 9 0 0 0-15-2L2 8m0-6v6h6m-4 9a9 9 0 0 0 15 2l3-3m0 6v-6h-6",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Zm-4 9 3 3 5-6",
  wallet: "M20 7V4H5a2 2 0 0 0 0 4h16v12H5a2 2 0 0 1-2-2V6m18 6h-6v4h6",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  logout: "M9 3H4v18h5m5-14 5 5-5 5m-6-5h14",
  signal: "M4 19v-3m5 3v-7m5 7V8m5 11V4",
};
export default function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return <svg className={`icon ${className}`} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
