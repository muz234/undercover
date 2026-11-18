import { rmSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { DB_PATH } from "./db";

test.beforeEach(() => {
  rmSync(DB_PATH, { force: true });
});

test("the queue lists the 25 claims, all waiting", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /^CLM-/ })).toHaveCount(25);
  await expect(page.locator(".chip-waiting")).toHaveCount(25);
});

test("a claim shows its details", async ({ page }) => {
  await page.goto("/#/claims/CLM-1001");
  await expect(page.getByText("Total claimed")).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "$420.00" }),
  ).toBeVisible();
  await expect(page.getByText(/Premium\s+plan/)).toBeVisible();
  await expect(page.getByText(/CLM-0412/)).toBeVisible();
});

test("the agent decides a small claim and pays it", async ({ page }) => {
  await page.goto("/#/claims/CLM-1001");
  await page.getByRole("button", { name: "Run agent" }).click();
  await expect(page.locator(".chip-decided")).toBeVisible();
  await expect(
    page.getByText("Scripted approval of the amount claimed.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("pay_claim", { exact: true })).toBeVisible();
  await expect(page.getByText(/Paid \$420\.00/)).toBeVisible();
});

test("a payout over $1,000 waits for sign-off, then pays", async ({
  page,
  request,
}) => {
  await page.goto("/#/claims/CLM-1002");
  await page.getByRole("button", { name: "Run agent" }).click();
  await expect(page.getByText("Sign-off needed")).toBeVisible();

  const blocked = await request.post("/api/claims/CLM-1002/payment", {
    data: { amount: 1150 },
  });
  expect(blocked.status()).toBe(409);

  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off and pay" }).click();
  await expect(page.getByText(/Paid \$1,150\.00/)).toBeVisible();
  await expect(page.locator(".chip-decided")).toBeVisible();
});

test("the instructions are read only", async ({ page }) => {
  await page.goto("/#/instructions");
  await expect(page.getByText(/You are the UnderCover Agent/)).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
