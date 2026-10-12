// SOL-011: fails when UI code bypasses a shared component. Run: npm run check:shared
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

const rules = [
  {
    name: "password input outside PasswordField",
    pattern: /type\s*=\s*["']password["']|type\s*:\s*["']password["']|"password"\s*:\s*"password"/,
    allowed: ["components/PasswordField.tsx"],
    ignoreTests: true,
  },
  {
    name: "browser-native alert, confirm or prompt",
    pattern: /\b(?:window\.)?(?:alert|confirm|prompt)\s*\(/,
    allowed: [],
    ignoreTests: true,
  },
  {
    name: "dialog implemented outside Dialog",
    pattern: /@radix-ui\/react-dialog|<dialog[\s>]/,
    allowed: ["components/Dialog.tsx"],
    ignoreTests: true,
  },
  {
    name: "raw fetch outside ApiClient",
    pattern: /\bfetch\s*\(/,
    allowed: ["api/client.ts"],
    ignoreTests: true,
  },
  {
    name: "scrollable table area outside TableWrap (keyboard access)",
    pattern: /className\s*=\s*["'](?:card )?table-wrap["']/,
    allowed: ["components/TableWrap.tsx"],
    ignoreTests: true,
  },
  {
    name: "raw <input> in a page (use the Field components)",
    pattern: /<input[\s>]/,
    allowed: [],
    onlyUnder: "pages/",
    ignoreTests: true,
  },
];

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

const files = walk(ROOT).filter((f) => /\.(ts|tsx)$/.test(f));
const problems = [];

for (const file of files) {
  const rel = relative(ROOT, file).split(sep).join("/");
  const isTest = /\.test\.tsx?$/.test(rel) || rel.startsWith("test/");
  const text = readFileSync(file, "utf8");
  for (const rule of rules) {
    if (rule.ignoreTests && isTest) continue;
    if (rule.onlyUnder && !rel.startsWith(rule.onlyUnder)) continue;
    if (rule.allowed.includes(rel)) continue;
    text.split(/\r?\n/).forEach((line, i) => {
      if (/^\s*(\/\/|\/\*|\*)/.test(line)) return; // comments are not code
      if (rule.pattern.test(line)) problems.push(`${rel}:${i + 1}  ${rule.name}: ${line.trim()}`);
    });
  }
}

if (problems.length > 0) {
  console.error("Shared-component check FAILED:\n" + problems.join("\n"));
  process.exit(1);
}
console.log(`Shared-component check passed (${files.length} files scanned).`);
