import { expect, Page, test } from "@playwright/test";

// Runs after telemetry.spec.ts (file order): the simulated attack already produced a hybrid incident.
const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const ADMIN_PASSWORD = "Nova-Heslo-2026!xQ";

test.describe.configure({ mode: "serial" });

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(ADMIN);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("the dashboard shows map and topology of the hybrid incident side by side (ARG-017..019)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signIn(page);
  await expect(page.getByTestId("incident-strip")).toBeVisible();
  const chip = page.locator("[data-testid^='incident-chip-']").first();
  await expect(chip).toBeVisible({ timeout: 30_000 });
  await chip.click();

  // both panes are on screen at once
  const map = page.getByTestId("pane-map");
  const graph = page.getByTestId("pane-graph");
  await expect(map).toBeVisible();
  await expect(graph).toBeVisible();
  const [m, g] = [await map.boundingBox(), await graph.boundingBox()];
  expect(m && g && m.x + m.width <= g.x + 2).toBeTruthy();

  // the domino effect: event -> exposed asset -> SCADA server -> controllers
  const nodes = (await page.getByTestId("topology").getAttribute("data-nodes")) ?? "";
  expect(nodes).toContain("UAV-001:physical_event");
  expect(nodes).toContain("SCADA-SRV-01:compromised");
  expect(nodes).toContain("PLC-SW1:at_risk");
  expect(nodes).toContain("PLC-GT1:at_risk");
  await expect(page.locator(".hybrid-link").first()).toBeVisible();
  await expect(page.getByTestId("blast-radius")).toContainText("PLC-SW1");
  await expect(page.getByTestId("recommendations")).toContainText("Dispatch security");
  await page.screenshot({ path: "e2e/results/40-dashboard-split.png", fullPage: true });
});

test("the incident workflow changes the state and keeps a timeline", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Incidents" }).click();
  await page.getByRole("button", { name: /^HYB-/ }).first().click();
  const panel = page.getByTestId("incident-panel");
  await expect(panel).toBeVisible();
  await panel.getByTestId("incident-to-triaged").click();
  await page.getByLabel("Note").fill("Checked by the shift lead");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(panel.getByTestId("incident-status")).toHaveText("Triaged");
  await expect(panel).toContainText("Checked by the shift lead");
  // a transition that is not allowed is not offered
  await expect(panel.getByTestId("incident-to-new")).toHaveCount(0);
});

test("the dashboard is usable on a tablet and on a phone", async ({ page }) => {
  await signIn(page);
  await page.setViewportSize({ width: 900, height: 900 });
  await expect(page.getByTestId("pane-map")).toBeVisible();
  await expect(page.getByTestId("pane-graph")).toBeVisible();
  const [m, g] = [await page.getByTestId("pane-map").boundingBox(), await page.getByTestId("pane-graph").boundingBox()];
  expect(m && g && m.y + m.height <= g.y + 2).toBeTruthy();   // stacked
  await page.screenshot({ path: "e2e/results/41-dashboard-tablet.png", fullPage: true });

  await page.setViewportSize({ width: 375, height: 740 });
  await expect(page.getByRole("tab", { name: "Graph" })).toBeVisible();
  await page.getByRole("tab", { name: "Graph" }).click();
  await expect(page.getByTestId("topology")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "e2e/results/42-dashboard-mobile.png" });
});
