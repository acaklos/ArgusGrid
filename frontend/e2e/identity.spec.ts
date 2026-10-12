import { expect, Page, test } from "@playwright/test";

const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const INITIAL = process.env.E2E_ADMIN_PASSWORD ?? "";
const OWNER_ID = process.env.E2E_OWNER_ID ?? "";
const OWNER_SECRET = process.env.E2E_OWNER_SECRET ?? "";
const NEW_PASSWORD = "Nova-Heslo-2026!xQ";

test.describe.configure({ mode: "serial" });

async function signIn(page: Page, user: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(user);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("login page: generic failure message and TAB reaches the password field (T-PWD-08)", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("User name").focus();
  await page.keyboard.press("Tab");
  // the reveal control has no focus, so TAB lands on the password input itself
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();

  await signIn(page, ADMIN, "definitely-not-the-password");
  await expect(page.getByRole("alert")).toHaveText("The user name or password is not correct.");
  await signIn(page, "no-such-user", "definitely-not-the-password");
  await expect(page.getByRole("alert")).toHaveText("The user name or password is not correct.");
  await page.screenshot({ path: "e2e/results/01-login.png" });
});

test("first login forces a password change that cannot be dismissed (T-IDN-02)", async ({ page }) => {
  expect(INITIAL.length).toBeGreaterThan(10);
  await signIn(page, ADMIN, INITIAL);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Set a new password" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible(); // cannot be dismissed
  await expect(dialog.getByRole("button", { name: "Cancel" })).toHaveCount(0);

  await dialog.getByLabel("Current password").fill(INITIAL);
  // custom mode by default in the change dialog: two fields (T-PWD-07)
  await expect(dialog.locator("input[type=password]")).toHaveCount(3);
  await dialog.getByLabel("New password").fill("short");
  await expect(dialog.getByRole("button", { name: "Change password" })).toBeDisabled();
  await expect(dialog.getByText("At least 12 characters").locator("xpath=ancestor::li")).toHaveAttribute("data-ok", "false");

  await dialog.getByLabel("New password").fill(NEW_PASSWORD);
  await dialog.getByLabel("Confirm password").fill(NEW_PASSWORD);
  await page.screenshot({ path: "e2e/results/02-forced-change.png" });
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
});

test("generated mode: one field, switching back to generated generates immediately (T-PWD-07)", async ({ page }) => {
  await signIn(page, ADMIN, NEW_PASSWORD);
  await page.getByRole("button", { name: "Change password" }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator("input[type=password]")).toHaveCount(3); // current + new + confirm
  await dialog.getByLabel("Custom password").uncheck();
  await expect(dialog.locator("input[type=password]")).toHaveCount(2); // current + one generated field
  const generated = dialog.getByLabel("New password");
  await expect(generated).not.toHaveValue("");
  const first = await generated.inputValue();
  await dialog.getByRole("button", { name: "Generate new" }).click();
  await expect(generated).not.toHaveValue(first);
  const reveal = dialog.getByRole("button", { name: "Show password" }).nth(1);
  await expect(reveal).toHaveAttribute("tabindex", "-1");
  await dialog.getByRole("button", { name: "Cancel" }).click();
});

test("settings: defaults shown, inconsistent values named, valid change saved (T-PWD-01, T-PWD-03)", async ({ page }) => {
  await signIn(page, ADMIN, NEW_PASSWORD);
  await page.getByRole("link", { name: "Password complexity" }).click();
  await expect(page.getByLabel("Minimum length")).toHaveValue("12");
  await expect(page.getByLabel("Maximum length")).toHaveValue("128");
  await expect(page.getByLabel("Password history (number of previous passwords)")).toHaveValue("5");

  await page.getByLabel("Minimum length").fill("200");
  await page.getByRole("button", { name: "Save" }).click();
  const banner = page.getByRole("alert").filter({ hasText: "conflict" });
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("Minimum length");

  await page.getByLabel("Minimum length").fill("14");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Settings saved.")).toBeVisible();
  await page.screenshot({ path: "e2e/results/03-password-policy.png" });

  // restore the default so the remaining tests see the standard profile
  await page.getByLabel("Minimum length").fill("12");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Settings saved.").first()).toBeVisible();
});

test("lockout page describes the effective behaviour in plain words", async ({ page }) => {
  await signIn(page, ADMIN, NEW_PASSWORD);
  await page.getByRole("link", { name: "Account lockout" }).click();
  const effective = page.getByLabel("Effective behaviour");
  await expect(effective).toContainText("Administrator: locked after 5 failed attempts within 15 minutes");
  await expect(effective).toContainText("1, 2, 5, 10, 15 minutes");
  await expect(effective).not.toContainText(/owner/i);
  await page.screenshot({ path: "e2e/results/04-lockout.png", fullPage: true });
});

test("responsive: navigation moves to the bottom on a phone-width screen", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await signIn(page, ADMIN, NEW_PASSWORD);
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  const main = page.locator("main");
  await expect(nav).toBeVisible();
  const navBox = await nav.boundingBox();
  const mainBox = await main.boundingBox();
  expect(navBox!.y).toBeGreaterThan(mainBox!.y);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "e2e/results/05-mobile.png" });
});

test("language and theme switches work", async ({ page }) => {
  await signIn(page, ADMIN, NEW_PASSWORD);
  await page.getByLabel("Language").selectOption("sk");
  await expect(page.getByRole("heading", { name: "Prehľad" })).toBeVisible();
  await page.getByLabel("Jazyk").selectOption("en");
  // the initial theme follows the browser preference; the toggle must flip it both ways
  const html = page.locator("html");
  const before = (await html.getAttribute("data-theme")) as "dark" | "light";
  const other = before === "dark" ? "light" : "dark";
  await page.getByRole("button", { name: before === "dark" ? "Light theme" : "Dark theme" }).click();
  await expect(html).toHaveAttribute("data-theme", other);
  await page.getByRole("button", { name: other === "dark" ? "Light theme" : "Dark theme" }).click();
  await expect(html).toHaveAttribute("data-theme", before);
});

test("logout ends the session; the previous page is no longer reachable (T-IDN-01)", async ({ page }) => {
  await signIn(page, ADMIN, NEW_PASSWORD);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/settings/password");
  await expect(page).toHaveURL(/\/login$/);
});

test("owner path works through the UI and is not visible to the user (T-OWN-02)", async ({ page }) => {
  test.skip(!OWNER_ID, "no owner credential supplied");
  await signIn(page, OWNER_ID, OWNER_SECRET);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Password complexity" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Account lockout" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change password" })).toHaveCount(0); // nothing to change
  await page.getByRole("button", { name: "Sign out" }).click();
});

test("wrong owner secret looks like any failed login (T-OWN-03)", async ({ page }) => {
  test.skip(!OWNER_ID, "no owner credential supplied");
  await signIn(page, OWNER_ID, "not-the-secret");
  await expect(page.getByRole("alert")).toHaveText("The user name or password is not correct.");
});
