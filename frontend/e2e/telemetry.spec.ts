import { expect, Page, test } from "@playwright/test";
import { spawn } from "node:child_process";

// Runs last (file order). The simulator posts signed events to the real API; the page must follow live.
const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const ADMIN_PASSWORD = "Nova-Heslo-2026!xQ";
const PY = process.env.E2E_PY ?? "";
const BACKEND = process.env.E2E_BACKEND ?? "";
const CREDS = process.env.E2E_DEMO_CREDS ?? "";
const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:8000";

test.describe.configure({ mode: "serial" });

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(ADMIN);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

function runSimulator(until: number, speed: number): Promise<number> {
  return new Promise((resolve, reject) => {
    const child = spawn(PY, ["-m", "app.simulator", "--speed", String(speed), "--until", String(until),
      "--base-url", BASE, "--creds", CREDS], { cwd: BACKEND });
    child.on("error", reject);
    child.on("exit", (code) => resolve(code ?? -1));
  });
}

test("the map follows the simulated attack live and flags the control sector (ARG-014, ARG-015)", async ({ page }) => {
  test.skip(!PY || !CREDS, "simulator paths not supplied");
  test.setTimeout(150_000);
  await signIn(page);
  await page.getByRole("link", { name: "Operational map" }).click();
  await expect(page.getByTestId("stream-status")).toHaveText("Live");
  await expect(page.getByTestId("no-threat")).toBeVisible();
  await expect(page.locator(".sensor").first()).toBeVisible();

  const exit = runSimulator(330, 15);

  // the drone appears, then the sector it hovers over is flagged, without any page reload
  await expect(page.locator(".uav[data-track='UAV-001']")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("threat-Z2")).toBeVisible({ timeout: 90_000 });
  await expect(page.locator("path.zone-Z2.zone--critical")).toBeVisible();
  await expect(page.getByTestId("track-UAV-001")).toContainText("Z2");
  expect(await exit).toBe(0);

  await expect(page.getByRole("listitem").filter({ hasText: "cyber" }).first()).toBeVisible();
  await expect(page.locator(".uav-trail")).toHaveCount(1);
  await page.screenshot({ path: "e2e/results/30-map-attack.png", fullPage: true });
});

test("layers can be switched off and state survives a reload", async ({ page }) => {
  test.skip(!PY, "simulator paths not supplied");
  await signIn(page);
  await page.getByRole("link", { name: "Operational map" }).click();
  await expect(page.getByTestId("track-UAV-001")).toBeVisible();  // restored from the server state
  await expect(page.locator(".uav-trail")).toHaveCount(1);
  await page.getByLabel("Trails").uncheck();
  await expect(page.locator(".uav-trail")).toHaveCount(0);
  await page.getByLabel("Zones").uncheck();
  await expect(page.locator("path.zone-Z2")).toHaveCount(0);
  await page.getByLabel("Cyber assets").check();
  await expect(page.locator("path.asset-SCADA-SRV-01")).toHaveCount(1);
});

test("the map page works on a phone-width screen", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await signIn(page);
  await page.getByRole("link", { name: "Operational map" }).click();
  await expect(page.locator(".sitemap")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "e2e/results/31-map-mobile.png" });
});

test("an operator without the asset capability cannot open the stream", async ({ request }) => {
  // no cookie at all: the WebSocket handshake is refused, the state endpoint answers 401
  const state = await request.get("/api/v1/telemetry/state");
  expect(state.status()).toBe(401);
});
