import { KeyboardEvent, ReactNode, useId, useRef } from "react";

// One accessible tab list (arrow keys move between tabs). Panels render only when active.
export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  label: string;
}

export function Tabs({ tabs, active, onChange, label }: TabsProps) {
  const base = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const move = (event: KeyboardEvent, index: number) => {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else return;
    event.preventDefault();
    const id = tabs[next].id;
    onChange(id);
    refs.current[id]?.focus();
  };

  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <div>
      <div role="tablist" aria-label={label} className="tabs">
        {tabs.map((tab, i) => (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[tab.id] = el;
            }}
            role="tab"
            type="button"
            id={`${base}-tab-${tab.id}`}
            aria-selected={tab.id === current.id}
            aria-controls={`${base}-panel-${tab.id}`}
            tabIndex={tab.id === current.id ? 0 : -1}
            className="tabs__tab"
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => move(e, i)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${base}-panel-${current.id}`} aria-labelledby={`${base}-tab-${current.id}`}>
        {current.content}
      </div>
    </div>
  );
}
