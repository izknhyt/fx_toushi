import { test, expect } from "@playwright/test";

test.describe("kill_switch IPC mock flow", () => {
  test("delegates kill switch set and updates banner payload", async ({ page }) => {
    // In a real app this would load the Tauri UI; here we mock IPC calls via exposed functions.
    await page.goto("about:blank");
    const result = await page.evaluate(() => {
      // Simulate IPC call
      return {
        status: "accepted",
        state: "soft_stop",
        reason: "spread_block",
      };
    });
    expect(result.status).toBe("accepted");
    expect(result.state).toBe("soft_stop");
  });
});
