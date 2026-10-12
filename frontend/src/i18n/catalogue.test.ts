import { describe, expect, it } from "vitest";
import en from "./en.json";
import sk from "./sk.json";

describe("message catalogue", () => {
  const enKeys = Object.keys(en).sort();
  const skKeys = Object.keys(sk).sort();

  it("has the same keys in every language", () => {
    expect(skKeys).toEqual(enKeys);
  });

  it("has no empty messages", () => {
    for (const [key, value] of [...Object.entries(en), ...Object.entries(sk)]) {
      expect(String(value).trim(), key).not.toBe("");
    }
  });

  it("keeps the same placeholders in every language", () => {
    const placeholders = (text: string) => (text.match(/{{\s*\w+\s*}}/g) ?? []).map((p) => p.replace(/\s/g, "")).sort();
    for (const key of enKeys) {
      expect(placeholders((sk as Record<string, string>)[key]), key).toEqual(
        placeholders((en as Record<string, string>)[key]),
      );
    }
  });
});
