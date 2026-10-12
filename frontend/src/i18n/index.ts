import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import sk from "./sk.json";

export const LANGUAGES = ["en", "sk"] as const;
export type Language = (typeof LANGUAGES)[number];

function initialLanguage(): Language {
  try {
    const stored = localStorage.getItem("argus.lang");
    if (stored && (LANGUAGES as readonly string[]).includes(stored)) return stored as Language;
  } catch {
    /* storage may be unavailable */
  }
  return navigator.language?.toLowerCase().startsWith("sk") ? "sk" : "en";
}

// Flat catalogue: keys contain dots (for example "errors.password.too_short"), so no key separator.
void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, sk: { translation: sk } },
  lng: initialLanguage(),
  fallbackLng: "en",
  keySeparator: false,
  interpolation: { escapeValue: false },
});

export function setLanguage(lang: Language): void {
  void i18n.changeLanguage(lang);
  try {
    localStorage.setItem("argus.lang", lang);
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang;
}

export default i18n;
