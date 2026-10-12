import { expect, Page, test } from "@playwright/test";
import { generateKeyPairSync, sign } from "node:crypto";

// Runs after the other specs (file order). Demo intelligence (DEMO-2026-NNNN) was created with the demo site.
const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const ADMIN_PASSWORD = "Nova-Heslo-2026!xQ";

test.describe.configure({ mode: "serial" });

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(ADMIN);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function openIntel(page: Page) {
  await page.getByRole("link", { name: "Threat intelligence" }).click();
  await expect(page.getByRole("heading", { name: "Threat intelligence" })).toBeVisible();
}

// canonical JSON as the server verifies it: sorted keys, no whitespace
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

const keys = generateKeyPairSync("ed25519");
const jwk = keys.publicKey.export({ format: "jwk" }) as { x: string };
const PUBLIC_B64 = Buffer.from(jwk.x, "base64url").toString("base64");

function makeBundle(severity: string) {
  const body = {
    format: "argusgrid-intel-bundle", version: 1, created_at: new Date().toISOString(), source: "e2e",
    records: [{
      vuln_id: "DEMO-2026-0200", title: "Bundle supplied flaw in Voltek Historian (demo)", severity, cvss: 7.5,
      kev: false, fix_status: "available", description: "Fictional bundle record.",
      affected: [{ vendor: "Voltek", product: "Historian", cpe: "", versions: { lt: "3.9.2" } }], references: [],
    }],
  };
  const signature = sign(null, Buffer.from(canonical(body)), keys.privateKey).toString("base64");
  return { ...body, key_id: "e2e-key", signature };
}

test("zero-day findings come first and the counts match (ARG-016)", async ({ page }) => {
  await signIn(page);
  await openIntel(page);
  await expect(page.getByTestId("count-zero-day")).toContainText(/[1-9]/);
  await page.getByRole("combobox", { name: "Class" }).selectOption("zero_day");
  const first = page.getByRole("row").nth(1);
  await expect(first).toContainText("DEMO-2026-0001");
  await expect(first).toContainText("SCADA-SRV-0");
  await expect(first).toContainText("No fix");
  await page.screenshot({ path: "e2e/results/40-intel-findings.png", fullPage: true });
});

test("a finding can be acknowledged with a note", async ({ page }) => {
  await signIn(page);
  await openIntel(page);
  await page.getByRole("combobox", { name: "Class" }).selectOption("zero_day");
  await page.getByRole("row").filter({ hasText: "DEMO-2026-0001" }).first().getByRole("button", { name: "Update" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Status").selectOption("acknowledged");
  await dialog.getByLabel("Note").fill("Web console isolated from the operator network");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Finding updated.")).toBeVisible();
  await page.getByRole("combobox", { name: "Status" }).selectOption("acknowledged");
  await expect(page.getByRole("row").filter({ hasText: "DEMO-2026-0001" }).first()).toContainText("Acknowledged");
});

test("a vulnerability shows its affected versions and assets", async ({ page }) => {
  await signIn(page);
  await openIntel(page);
  await page.getByRole("tab", { name: "Vulnerabilities" }).click();
  await page.getByRole("searchbox", { name: "Search vulnerabilities" }).fill("DEMO-2026-0001");
  await page.getByRole("button", { name: "DEMO-2026-0001" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("SCADA Web Console");
  await expect(dialog).toContainText("4.3.0");
  await expect(dialog).toContainText("SCADA-SRV-01");
});

test("a signed bundle is accepted only from a trusted key and not when altered", async ({ page }) => {
  await signIn(page);
  await openIntel(page);

  // not trusted yet
  await page.getByRole("tab", { name: "Sources" }).click();
  await page.getByRole("button", { name: "Import intelligence" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("File").setInputFiles({
    name: "bundle.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(makeBundle("high"))),
  });
  await dialog.getByRole("button", { name: "Import", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("not trusted");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  // trust the key
  await page.getByRole("tab", { name: "Policy and trust" }).click();
  await page.getByLabel("Key ID").fill("e2e-key");
  await page.getByLabel("Public key (base64)").fill(PUBLIC_B64);
  await page.getByRole("button", { name: "Add key" }).click();
  await expect(page.getByText("Settings saved.")).toBeVisible();
  await expect(page.getByText("e2e-key").first()).toBeVisible();

  // accepted
  await page.getByRole("tab", { name: "Sources" }).click();
  await page.getByRole("button", { name: "Import intelligence" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("File").setInputFiles({
    name: "bundle.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(makeBundle("high"))),
  });
  await dialog.getByRole("button", { name: "Import", exact: true }).click();
  await expect(page.getByText(/Imported: 1 new/)).toBeVisible();

  // altered after signing
  const altered = makeBundle("high");
  altered.records[0].severity = "critical";
  await page.getByRole("button", { name: "Import intelligence" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("File").setInputFiles({
    name: "bundle.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(altered)),
  });
  await dialog.getByRole("button", { name: "Import", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("signature is not valid");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  // the accepted record produced findings on the historians
  await page.getByRole("tab", { name: "Findings" }).click();
  await page.getByRole("searchbox", { name: "Search findings" }).fill("DEMO-2026-0200");
  await expect(page.getByRole("row").filter({ hasText: "HIST-01" }).first()).toBeVisible();
});

test("policy values are validated and offline-only blocks online sources", async ({ page }) => {
  await signIn(page);
  await openIntel(page);
  await page.getByRole("tab", { name: "Policy and trust" }).click();
  await page.getByLabel("EPSS threshold").fill("3");
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByRole("alert").filter({ hasText: "EPSS threshold must be between" })).toBeVisible();
  await page.getByLabel("EPSS threshold").fill("0.5");
  await page.getByLabel("Offline only").check();
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByText("Settings saved.")).toBeVisible();

  await page.getByRole("tab", { name: "Sources" }).click();
  await page.locator("tr[data-source='kev']").getByLabel("Enabled").click(); // the server refuses: the box stays off
  await expect(page.getByText("offline only").first()).toBeVisible();

  await page.getByRole("tab", { name: "Policy and trust" }).click();
  await page.getByLabel("Offline only").uncheck();
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByText("Settings saved.").first()).toBeVisible();
});

test("the intelligence page works on a phone-width screen", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await signIn(page);
  await openIntel(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "e2e/results/41-intel-mobile.png" });
});
