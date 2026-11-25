import { MessageSquare, LayoutDashboard, ChartCandlestick, UserRound } from "lucide-react";

export type NavigationIconName = "chat" | "dashboard" | "trade" | "account";
const outlines = { chat: MessageSquare, dashboard: LayoutDashboard, trade: ChartCandlestick, account: UserRound };
export default function NavigationIcon({ name, active }: { name: NavigationIconName; active: boolean }) {
  const className = `icon nav-icon-${name}`;
  const Outline = outlines[name];
  if (!active) return <Outline className={className} size={21} strokeWidth={1.65} aria-hidden="true" />;
  return <svg className={className} width="21" height="21" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" data-variant="filled">
    {name === "chat" && <path d="M5 3a3 3 0 0 0-3 3v15a1 1 0 0 0 1.7.7L7.4 18H19a3 3 0 0 0 3-3V6a3 3 0 0 0-3-3Z" />}
    {name === "dashboard" && <><rect x="3" y="3" width="7" height="11" rx="1.6" /><rect x="14" y="3" width="7" height="7" rx="1.6" /><rect x="14" y="14" width="7" height="7" rx="1.6" /><rect x="3" y="18" width="7" height="3" rx="1.3" /></>}
    {name === "trade" && <><path d="M4 3v18h17M9 5v14m7-16v14" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" /><rect x="6.5" y="9" width="5" height="7" rx="1" /><rect x="13.5" y="6" width="5" height="7" rx="1" /></>}
    {name === "account" && <><circle cx="12" cy="7.5" r="4.5" /><path d="M3 21v-1a9 7 0 0 1 18 0v1a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z" /></>}
  </svg>;
}
