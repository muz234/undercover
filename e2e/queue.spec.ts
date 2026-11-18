import { expect, test } from "@playwright/test";

test("the queue lists the claims", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /^CLM-/ })).toHaveCount(25);
});
