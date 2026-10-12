import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

// One search box for every list. Typing is debounced so the server is not asked on every keystroke.
interface SearchFilterProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  delayMs?: number;
}

export function SearchFilter({ value, onChange, label, delayMs = 300 }: SearchFilterProps) {
  const { t } = useTranslation();
  const [text, setText] = useState(value);

  useEffect(() => setText(value), [value]);
  useEffect(() => {
    if (text === value) return;
    const timer = window.setTimeout(() => onChange(text), delayMs);
    return () => window.clearTimeout(timer);
  }, [text, value, onChange, delayMs]);

  const caption = label ?? t("common.search");
  return (
    <label className="searchfilter">
      <span className="sr-only">{caption}</span>
      <input
        type="search"
        className="input"
        placeholder={caption}
        value={text}
        onChange={(e) => setText(e.target.value)}
        autoComplete="off"
      />
    </label>
  );
}
