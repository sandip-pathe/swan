export type Appearance = "system" | "light" | "dark";
export function validAppearance(value: unknown): value is Appearance {
  return value === "system" || value === "light" || value === "dark";
}
export function readAppearance(): Appearance {
  try {
    const cookie = document.cookie
      .split("; ")
      .find((row) => row.startsWith("swan_appearance="))
      ?.split("=")[1];
    if (validAppearance(cookie)) return cookie;
  } catch {
    /* Cookie access can be disabled. */
  }
  try {
    const saved = localStorage.getItem("swan.appearance");
    if (validAppearance(saved)) return saved;
  } catch {
    /* Device storage is optional. */
  }
  return "system";
}
export function saveAppearance(value: Appearance) {
  try {
    document.cookie = `swan_appearance=${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  } catch {
    /* Local storage is the fallback. */
  }
  try {
    localStorage.setItem("swan.appearance", value);
  } catch {
    /* Cookie remains the preference fallback. */
  }
}
