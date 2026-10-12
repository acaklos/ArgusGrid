import { expect, Page, test } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// Runs after identity.spec.ts (file order), which already replaced the initial administrator password.
const ADMIN = process.env.E2E_ADMIN_USER ?? "sysadmin";
const ADMIN_PASSWORD = "Nova-Heslo-2026!xQ";
const MAIL_DIR = process.env.E2E_MAIL_DIR ?? "";
const SMTP_PORT = process.env.E2E_SMTP_PORT ?? "1025";
const NEW_USER_PASSWORD = "Zivy-Plot-2026#kR";

test.describe.configure({ mode: "serial" });

async function signIn(page: Page, user: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("User name").fill(user);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Quoted-printable decoding (the body is encoded because passwords may contain "="). */
function qpDecode(text: string): string {
  return text
    .replace(/=\r?\n/g, "")
    .replace(/=([0-9A-Fa-f]{2})/g, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
}

function mails(): { name: string; text: string }[] {
  try {
    return readdirSync(MAIL_DIR)
      .filter((f) => f.endsWith(".eml"))
      .sort()
      .map((name) => ({ name, text: qpDecode(readFileSync(join(MAIL_DIR, name), "utf8")) }));
  } catch {
    return [];
  }
}

async function createUser(page: Page, username: string, email: string, role: string, password?: string) {
  await page.getByRole("link", { name: "Users" }).click();
  await page.getByRole("button", { name: "Create user" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("User name").fill(username);
  await dialog.getByLabel("E-mail", { exact: true }).fill(email);
  await dialog.getByLabel("Full name").fill(`${username} test`);
  await dialog.getByLabel("Role").selectOption(role);
  let chosen = "";
  if (password) {
    await dialog.getByLabel("Custom password").check();
    await dialog.getByLabel("Initial password").fill(password);
    await dialog.getByLabel("Confirm password").fill(password);
    chosen = password;
  } else {
    const field = dialog.getByLabel("Initial password");
    await expect(field).not.toHaveValue("");
    chosen = await field.inputValue();
  }
  await dialog.getByRole("button", { name: "Create", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  return chosen;
}

test("administrator configures SMTP and the test message arrives (ARG-007)", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "E-mail" }).click();
  await page.getByLabel("Send e-mail").check();
  await page.getByLabel("SMTP server").fill("127.0.0.1");
  await page.getByLabel("Port").fill(SMTP_PORT);
  await page.getByLabel("Encryption").selectOption("none");
  await page.getByLabel("Sender address").fill("argus@example.test");
  await page.getByLabel("Application address").fill("http://127.0.0.1:8000/login");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Settings saved.")).toBeVisible();

  await page.getByLabel("Send to").fill("admin-inbox@example.test");
  await page.getByRole("button", { name: "Send test" }).click();
  await expect(page.getByText("The test message was delivered to the SMTP server.")).toBeVisible();
  await expect.poll(() => mails().some((m) => m.text.includes("admin-inbox@example.test"))).toBe(true);
  await page.screenshot({ path: "e2e/results/10-email-server.png", fullPage: true });
});

test("settings validation names the conflicting fields", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "E-mail" }).click();
  await page.getByLabel("Port").fill("70000");
  await page.getByRole("button", { name: "Save" }).click();
  const banner = page.getByRole("alert").filter({ hasText: "conflict" });
  await expect(banner).toBeVisible();
  await page.getByLabel("Port").fill(SMTP_PORT);
});

test("creating a user sends the credentials by e-mail and the user must change them (ARG-005, ARG-006)", async ({ page, browser }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  const generated = await createUser(page, "jana.novakova", "jana@example.test", "SOC Analyst");
  await expect(page.getByText("User jana.novakova was created.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "jana.novakova", exact: true })).toBeVisible();

  // the message the application really sent carries exactly the password the administrator saw
  await expect
    .poll(() => mails().find((m) => m.text.includes("jana@example.test") && m.text.includes(generated)) !== undefined, {
      timeout: 20_000,
    })
    .toBe(true);

  const userPage = await (await browser.newContext()).newPage();
  await signIn(userPage, "jana.novakova", generated);
  const dialog = userPage.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Set a new password" })).toBeVisible();
  await dialog.getByLabel("Current password").fill(generated);
  await dialog.getByLabel("New password").fill(NEW_USER_PASSWORD);
  await dialog.getByLabel("Confirm password").fill(NEW_USER_PASSWORD);
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(userPage.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  // an analyst has no administration area
  await expect(userPage.getByRole("link", { name: "Users" })).toHaveCount(0);
  await expect(userPage.getByRole("link", { name: "Audit log" })).toHaveCount(0);
  await userPage.context().close();

  // the outbox tab shows the delivery
  await page.getByRole("link", { name: "E-mail" }).click();
  await page.getByRole("tab", { name: "Outbox" }).click();
  await expect(page.getByRole("row").filter({ hasText: "user.created" }).first()).toContainText("Sent");
});

test("the policy is enforced when an administrator picks a custom password", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Users" }).click();
  await page.getByRole("button", { name: "Create user" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("User name").fill("weak.user");
  await dialog.getByLabel("E-mail", { exact: true }).fill("weak@example.test");
  await dialog.getByLabel("Custom password").check();
  await dialog.getByLabel("Initial password").fill("weakpass");
  await dialog.getByLabel("Confirm password").fill("weakpass");
  await expect(dialog.getByRole("button", { name: "Create", exact: true })).toBeDisabled();
  await dialog.getByRole("button", { name: "Cancel" }).click();
});

test("lower roles never see administrators (T-IDN-10)", async ({ page, browser }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  const password = await createUser(page, "marek.manager", "marek@example.test", "SOC Manager", "Marek-Manazer-2026!x");
  await page.getByRole("button", { name: "Sign out" }).click();

  const mgr = await (await browser.newContext()).newPage();
  await signIn(mgr, "marek.manager", password);
  const dialog = mgr.getByRole("dialog");
  await dialog.getByLabel("Current password").fill(password);
  await dialog.getByLabel("New password").fill("Marek-Novy-2026!yZ");
  await dialog.getByLabel("Confirm password").fill("Marek-Novy-2026!yZ");
  await dialog.getByRole("button", { name: "Change password" }).click();
  await expect(mgr.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await mgr.getByRole("link", { name: "Users" }).click();
  await expect(mgr.getByRole("cell", { name: "marek.manager", exact: true })).toBeVisible();
  await expect(mgr.getByText("sysadmin")).toHaveCount(0);
  await mgr.getByRole("searchbox", { name: "Search users" }).fill("sysadmin");
  await expect(mgr.getByText("Nothing to show.")).toBeVisible();
  await mgr.getByRole("link", { name: "Roles" }).click();
  await expect(mgr.getByRole("button", { name: /^Administrator/ })).toHaveCount(0);
  await mgr.getByRole("link", { name: "Audit log" }).click();
  await expect(mgr.getByText("sysadmin")).toHaveCount(0);
  await mgr.screenshot({ path: "e2e/results/11-manager-users.png", fullPage: true });
  await mgr.context().close();
});

test("lock and unlock from the user list (T-LCK-06)", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Users" }).click();
  const row = page.getByRole("row").filter({ hasText: "jana.novakova" });
  await row.getByRole("button", { name: "Lock" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Lock" }).click();
  await expect(row).toContainText("Locked by an administrator");
  await row.getByRole("button", { name: "Unlock" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Unlock" }).click();
  await expect(page.getByRole("row").filter({ hasText: "jana.novakova" })).toContainText("Active");
});

test("roles page edits capabilities at runtime", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Roles" }).click();
  await page.getByRole("button", { name: /^SOC Operator/ }).click();
  const box = page.getByLabel("incident.triage");
  await expect(box).toBeChecked();
  await box.uncheck();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Role saved.")).toBeVisible();
  await page.getByRole("button", { name: /^Administrator/ }).click();
  await expect(page.getByText("always holds every capability")).toBeVisible();
  await page.screenshot({ path: "e2e/results/12-roles.png", fullPage: true });
});

test("a custom e-mail template is used for the next message (ARG-008)", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "E-mail" }).click();
  await page.getByRole("tab", { name: "Templates" }).click();
  await page.getByRole("button", { name: /user\.created$/ }).click();
  await page.locator("main").getByLabel("Language").selectOption("en");
  await expect(page.getByLabel("Subject")).not.toHaveValue("");
  await page.getByLabel("Subject").fill("Custom welcome {{ username }}");
  await page.getByLabel("Text body").fill("Hello {{ username }}, your password is {{ temp_password }}.");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByRole("heading", { name: "Custom welcome jana.novakova" })).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Settings saved.")).toBeVisible();
  // wait until the editor has reloaded the saved version, otherwise the reload overwrites the next edit
  await expect(page.getByText(/Customised \(version \d+\)/)).toBeVisible();

  // the variable list rejects names that are not allowed
  await page.getByLabel("Text body").fill("Hello {{ nonsense }}");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "not allowed" })).toBeVisible();

  await page.getByRole("link", { name: "Users" }).click();
  await createUser(page, "peter.horvath", "peter@example.test", "SOC Operator");
  await expect
    .poll(() => mails().some((m) => m.text.includes("peter@example.test") && m.text.includes("Custom welcome peter.horvath")),
      { timeout: 20_000 })
    .toBe(true);
});

test("audit page: when, who, what, how and old/new values; export and integrity", async ({ page }) => {
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("columnheader", { name: "When" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Old and new values" })).toBeVisible();
  await page.getByRole("combobox", { name: "Action group" }).selectOption("role.");
  const row = page.getByRole("row").filter({ hasText: "role.update" }).first();
  await expect(row).toContainText(ADMIN);
  await expect(row).toContainText("capabilities");
  await page.getByRole("button", { name: "Verify integrity" }).click();
  await expect(page.getByText("The audit chain is intact.")).toBeVisible();

  const href = await page.getByRole("link", { name: "Export CSV" }).getAttribute("href");
  const response = await page.request.get(href!);
  expect(response.status()).toBe(200);
  const body = await response.text();
  expect(body.split("\n")[0]).toContain("timestamp_utc");
  expect(body).not.toContain(NEW_USER_PASSWORD);
  await page.screenshot({ path: "e2e/results/13-audit.png", fullPage: true });
});

test("user list is usable on a phone-width screen", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  await signIn(page, ADMIN, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: "e2e/results/14-users-mobile.png" });
});
