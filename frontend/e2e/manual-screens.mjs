// Screenshots for the manuals (DOC-010): taken from a clean install of the demo package with normal login.
// Not part of the test suite. Run by devtools/manual_screens.py with:
//   BASE_URL, ADMIN_USER, ADMIN_PASSWORD (initial, generated), NEW_PASSWORD, OUT_DIR
// Fields that could show a password are masked (DOC-012).
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const BASE = process.env.BASE_URL;
const USER = process.env.ADMIN_USER ?? "sysadmin";
const INITIAL = process.env.ADMIN_PASSWORD;
const NEW_PASSWORD = process.env.NEW_PASSWORD;
const OUT = process.env.OUT_DIR;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "sk-SK" });
await context.addInitScript(() => {
  localStorage.setItem("argus.lang", "sk");
  localStorage.setItem("argus.theme", "light");
});
const page = await context.newPage();
const shot = async (name, options = {}) => {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, `${name}.png`), maskColor: "#8b87a8", ...options });
  console.log("screen", name);
};
const maskPasswords = () => page.locator("input[type=password], input[readonly]");
const go = async (path) => {
  await page.goto(BASE + path);
  await page.locator("main").waitFor();
};

// 1. login
await page.goto(BASE + "/login");
await page.locator("form").waitFor();
await shot("01-prihlasenie");

// 2. first login: the forced change of the generated password
await page.locator("input[autocomplete=username], input[type=text]").first().fill(USER);
await page.locator("input[type=password]").first().fill(INITIAL);
await page.locator("form button[type=submit]").click();
const dialog = page.getByRole("dialog");
await dialog.waitFor();
await dialog.locator("input[type=password]").first().fill(INITIAL);
await page.waitForTimeout(600);
await shot("02-prva-zmena-hesla", { mask: [maskPasswords()] });
// custom password: three fields
await dialog.getByRole("checkbox").check();
const fields = dialog.locator("input[type=password]");
await fields.nth(0).fill(INITIAL);
await fields.nth(1).fill(NEW_PASSWORD);
await fields.nth(2).fill(NEW_PASSWORD);
await page.waitForTimeout(500);
await shot("03-vlastne-heslo", { mask: [maskPasswords()] });
await dialog.locator("button.btn--primary, button[type=submit]").last().click();
await page.locator("main").waitFor();

// 3. dashboard with the incident
await go("/");
await page.locator("[data-testid^='incident-chip-']").first().waitFor({ timeout: 30000 });
await page.locator("[data-testid^='incident-chip-']").first().click();
await page.locator("[data-testid=topology]").waitFor();
await page.waitForTimeout(1200);
await shot("04-operatorsky-panel");
await shot("05-incident-detail", { fullPage: true });

// 4. incident workflow dialog
await page.locator("[data-testid=incident-to-triaged]").click();
await page.getByRole("dialog").waitFor();
await shot("06-incident-zmena-stavu");
await page.keyboard.press("Escape");

// 5. lists and registers
await go("/incidents");
await shot("07-incidenty");
await go("/map");
await page.locator(".sitemap").waitFor();
await page.waitForTimeout(1000);
await shot("08-mapa");
await go("/assets");
await shot("09-aktiva");
await page.locator("main input").first().fill("SCADA-SRV-01");
await page.waitForTimeout(900);
await page.locator("table button.mono").first().click();
await page.locator("main h1").waitFor();
await shot("10-detail-aktiva", { fullPage: true });
await go("/intel");
await shot("11-hrozby-nalezy");
await page.getByRole("tab").nth(1).click();
await shot("12-hrozby-zranitelnosti");
await page.getByRole("tab").nth(2).click();
await shot("13-hrozby-zdroje");
await page.getByRole("tab").nth(3).click();
await shot("14-hrozby-politika");

// 6. administration
await go("/users");
await shot("15-pouzivatelia");
await page.locator("main button.btn--primary").first().click();
await page.getByRole("dialog").waitFor();
await page.waitForTimeout(500);
await shot("16-novy-pouzivatel", { mask: [maskPasswords()] });
await page.keyboard.press("Escape");
await go("/roles");
await page.getByText("SOC Analyst").first().click();
await page.waitForTimeout(500);
await shot("17-roly", { fullPage: true });
await go("/audit");
await shot("18-audit");
await go("/settings/email");
await shot("19-email-server");
await page.getByRole("tab").nth(1).click();
await page.locator("button", { hasText: "user.created" }).first().click();
await page.waitForTimeout(600);
await shot("20-email-sablony", { fullPage: true });
await go("/settings/password");
await shot("21-politika-hesiel", { fullPage: true });
await go("/settings/lockout");
await shot("22-zamykanie", { fullPage: true });
await go("/settings/sessions");
await shot("23-relacie");

// 7. phone layout
await page.setViewportSize({ width: 390, height: 800 });
await go("/");
await page.locator("[data-testid^='incident-chip-']").first().waitFor();
await shot("24-mobil-panel");
await page.getByRole("tab").nth(1).click();
await page.waitForTimeout(800);
await shot("25-mobil-graf");

await browser.close();
