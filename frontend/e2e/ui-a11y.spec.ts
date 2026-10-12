import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";

// Accessibility scan (WCAG 2.1 A and AA rules of axe-core) of every page, in both themes. Runs after the
// other specs (file order) with the administrator whose password those specs set.
const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const ADMIN_PASSWORD = "Nova-Heslo-2026!xQ";

const PAGES = ["/", "/incidents", "/map", "/assets", "/intel", "/users", "/roles", "/audit",
  "/settings/email", "/settings/password", "/settings/lockout", "/settings/sessions"];

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(ADMIN);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
}

async function scan(page: Page, label: string): Promise<string[]> {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${label}: ${v.id} (${v.impact}) ${v.help} - ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
}

test("the login page has no serious accessibility violations", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  expect(await scan(page, "/login")).toEqual([]);
});

for (const theme of ["dark", "light"] as const) {
  test(`all pages have no serious accessibility violations (${theme} theme)`, async ({ page }) => {
    test.setTimeout(180_000);
    await page.addInitScript((t) => localStorage.setItem("argus.theme", t), theme);
    await signIn(page);
    const problems: string[] = [];
    for (const path of PAGES) {
      await page.goto(path);
      await expect(page.locator("main")).toBeVisible();
      await page.waitForLoadState("networkidle");
      problems.push(...(await scan(page, `${theme} ${path}`)));
    }
    expect(problems).toEqual([]);
  });
}
