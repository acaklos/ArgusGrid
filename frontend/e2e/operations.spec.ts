import { expect, Page, test } from "@playwright/test";
import { createHash, createHmac } from "node:crypto";

// Runs after identity.spec.ts and management.spec.ts (file order): the administrator password is already set.
const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const ADMIN_PASSWORD = "Nova-Heslo-2026!xQ";
const HEARTBEAT = "/api/v1/ingest/heartbeat";

test.describe.configure({ mode: "serial" });

async function signIn(page: Page, user = ADMIN, password = ADMIN_PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(user);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

function signedHeaders(keyId: string, secret: string, body: string, offsetSeconds = 0): Record<string, string> {
  const ts = Math.floor(Date.now() / 1000) + offsetSeconds;
  const bodyHash = createHash("sha256").update(body).digest("hex");
  const signature = createHmac("sha256", secret).update(`POST\n${HEARTBEAT}\n${ts}\n${bodyHash}`).digest("hex");
  return {
    "Content-Type": "application/json",
    "X-Device-Key": keyId,
    "X-Device-Timestamp": String(ts),
    "X-Device-Signature": signature,
  };
}

let keyId = "";
let secret = "";

test("the demo site is in the registry and can be filtered (ARG-012)", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Assets" }).click();
  await expect(page.getByRole("heading", { name: "Assets" })).toBeVisible();
  await expect(page.getByText("57 in total")).toBeVisible();
  await page.getByRole("combobox", { name: "Zone" }).selectOption({ label: "Z4 Switchyard 110/22 kV" });
  await expect(page.getByRole("button", { name: "PLC-SW1" })).toBeVisible();
  await expect(page.getByRole("button", { name: "PLC-GT1" })).toHaveCount(0);
  await page.getByRole("combobox", { name: "Zone" }).selectOption("");
  await page.getByRole("searchbox", { name: "Search assets" }).fill("scada");
  await expect(page.getByRole("button", { name: "SCADA-SRV-01" })).toBeVisible();
  await page.screenshot({ path: "e2e/results/20-assets.png", fullPage: true });
});

test("asset detail shows software, exposure and the dependency chain", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Assets" }).click();
  await page.getByRole("searchbox", { name: "Search assets" }).fill("SCADA-SRV-01");
  await page.getByRole("button", { name: "SCADA-SRV-01", exact: true }).click();
  await expect(page.getByRole("heading", { name: /SCADA-SRV-01/ })).toBeVisible();
  await page.getByRole("tab", { name: "Software" }).click();
  await expect(page.getByRole("textbox", { name: "Software" }).first()).toHaveValue("Voltek SCADA Server");
  await expect(page.locator("input[value='Voltek SCADA Web Console']")).toBeVisible();
  await page.getByRole("tab", { name: "Relations" }).click();
  await expect(page.getByText("PLC-SW1")).toBeVisible();
  await expect(page.getByText("PLC-GT1")).toBeVisible();
  await expect(page.getByText("HMI-03")).toBeVisible(); // reached by
  await page.screenshot({ path: "e2e/results/21-asset-relations.png", fullPage: true });
});

test("creating a sensor, relating it and issuing a device key shows the secret once (ARG-013)", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Assets" }).click();
  await page.getByRole("button", { name: "Create asset" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Code").fill("RF-UI1");
  await dialog.getByLabel("Name").fill("UI test RF detector");
  await dialog.getByLabel("Type").selectOption("sensor");
  await dialog.getByLabel("IP address").fill("10.20.50.201");
  await dialog.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("heading", { name: /RF-UI1/ })).toBeVisible();

  await page.getByRole("tab", { name: "Relations" }).click();
  await page.getByLabel("Other asset (code)").fill("SENS-GW-01");
  await page.getByRole("button", { name: "Add relation" }).last().click();
  await expect(page.getByText("SENS-GW-01")).toBeVisible();

  await page.getByRole("tab", { name: "Device credentials" }).click();
  await page.getByRole("button", { name: "Create credential" }).click();
  const create = page.getByRole("dialog");
  await create.getByLabel("ingest:rf").check();
  await create.getByLabel("Allowed networks").fill("127.0.0.0/8");
  await create.getByRole("button", { name: "Create", exact: true }).click();

  const once = page.getByRole("dialog");
  await expect(once.getByRole("heading", { name: "Save the secret now" })).toBeVisible();
  keyId = await once.getByLabel("Key ID").inputValue();
  secret = await once.getByLabel("Secret").inputValue();
  expect(keyId).toMatch(/^dk_[0-9a-f]{16}$/);
  expect(secret).toMatch(/^ds_/);
  await page.keyboard.press("Escape");
  await expect(once).toBeVisible(); // cannot be dismissed without confirming
  await once.getByRole("button", { name: "I have stored the secret" }).click();

  await expect(page.getByRole("cell", { name: keyId })).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "Device credentials" }).click();
  await expect(page.getByRole("cell", { name: keyId })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(secret); // never shown again
  await page.screenshot({ path: "e2e/results/22-credentials.png", fullPage: true });
});

test("the device key works for its own asset, tampering and replay do not", async ({ request }) => {
  test.skip(!keyId, "no credential from the previous test");
  const body = JSON.stringify({ status: "ok" });
  const ok = await request.post(HEARTBEAT, { data: body, headers: signedHeaders(keyId, secret, body) });
  expect(ok.status()).toBe(200);
  expect((await ok.json()).asset).toBe("RF-UI1");

  const stale = await request.post(HEARTBEAT, { data: body, headers: signedHeaders(keyId, secret, body, -900) });
  expect(stale.status()).toBe(401);
  const wrong = await request.post(HEARTBEAT, { data: body, headers: signedHeaders(keyId, "ds_not-the-secret", body) });
  expect(wrong.status()).toBe(401);
  expect(await wrong.json()).toEqual({ code: "device_auth_failed" });
  const noHeaders = await request.post(HEARTBEAT, { data: body, headers: { "Content-Type": "application/json" } });
  expect(noHeaders.status()).toBe(401);
});

test("the asset shows when it was last seen; rotating the key ends the old one", async ({ page, request }) => {
  test.skip(!keyId, "no credential from the previous test");
  await signIn(page);
  await page.getByRole("link", { name: "Assets" }).click();
  await page.getByRole("searchbox", { name: "Search assets" }).fill("RF-UI1");
  await page.getByRole("button", { name: "RF-UI1" }).click();
  await expect(page.getByText(/Last seen/)).toBeVisible();

  await page.getByRole("tab", { name: "Device credentials" }).click();
  await page.getByRole("row").filter({ hasText: keyId }).getByRole("button", { name: "Rotate" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Rotate", exact: true }).click();
  const once = page.getByRole("dialog");
  const newKey = await once.getByLabel("Key ID").inputValue();
  const newSecret = await once.getByLabel("Secret").inputValue();
  await once.getByRole("button", { name: "I have stored the secret" }).click();
  expect(newKey).not.toBe(keyId);

  const body = JSON.stringify({ status: "ok" });
  const old = await request.post(HEARTBEAT, { data: body, headers: signedHeaders(keyId, secret, body) });
  expect(old.status()).toBe(401);
  const fresh = await request.post(HEARTBEAT, { data: body, headers: signedHeaders(newKey, newSecret, body) });
  expect(fresh.status()).toBe(200);
  await expect(page.getByRole("row").filter({ hasText: keyId })).toContainText("Revoked");
});

test("decommission and delete an asset (lifecycle)", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Assets" }).click();
  await page.getByRole("searchbox", { name: "Search assets" }).fill("RF-UI1");
  await page.getByRole("button", { name: "RF-UI1" }).click();
  await expect(page.getByRole("button", { name: "Delete asset" })).toHaveCount(0); // active assets are not deletable
  await page.getByLabel("Status").selectOption("decommissioned");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Asset saved.")).toBeVisible();
  await page.getByRole("button", { name: "Delete asset" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete asset" }).click();
  await expect(page.getByRole("heading", { name: "Assets" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search assets" }).fill("RF-UI1");
  await expect(page.getByText("Nothing to show.")).toBeVisible();
});

test("the registry is usable on a phone-width screen", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await signIn(page);
  await page.getByRole("link", { name: "Assets" }).click();
  await expect(page.getByRole("heading", { name: "Assets" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "e2e/results/23-assets-mobile.png" });
});
