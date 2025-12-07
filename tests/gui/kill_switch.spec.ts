import { test, expect } from "@playwright/test";

test.describe("kill switch UI flow", () => {
  test("toggles banner text when kill switch is set/cleared", async ({ page }) => {
    await page.goto("/");

    const banner = page.getByTestId("kill-switch-banner");
    const button = page.getByTestId("toggle-kill-switch");

    await expect(banner).toContainText("Kill Switch: NONE");
    await button.click();
    await expect(banner).toContainText("SOFT_STOP");
    await button.click();
    await expect(banner).toContainText("Kill Switch: NONE");
  });
});
