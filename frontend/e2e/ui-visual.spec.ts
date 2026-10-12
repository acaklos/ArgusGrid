import { expect, test } from "@playwright/test";

// Visual regression of stable screens (baselines are stored next to the spec and reviewed in the pull request).
// A deliberate design change is accepted with `npx playwright test ui-visual --update-snapshots`.
test.use({ colorScheme: "dark" });

for (const theme of ["dark", "light"] as const) {
  test(`login page looks as before (${theme}, desktop)`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem("argus.theme", t), theme);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expect(page).toHaveScreenshot(`login-${theme}-desktop.png`, { maxDiffPixelRatio: 0.02, animations: "disabled" });
  });
}

test("login page looks as before (dark, phone)", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("argus.theme", "dark"));
  await page.setViewportSize({ width: 375, height: 740 });
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  await expect(page).toHaveScreenshot("login-dark-phone.png", { maxDiffPixelRatio: 0.02, animations: "disabled" });
});
