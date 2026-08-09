import { expect, test } from "@playwright/test";

test("real browser reaches the real VerityGraph API", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "VerityGraph AI" })).toBeVisible();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByText("veritygraph-api · v0.2.0")).toBeVisible();
});
