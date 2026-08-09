import { expect, test } from "@playwright/test";

test("real browser reaches the real VerityGraph API", async ({ page }) => {
  const healthResponse = await page.request.get("/api/v1/health");
  expect(healthResponse.ok()).toBeTruthy();
  const health = (await healthResponse.json()) as {
    status: string;
    service: string;
    version: string;
  };

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "VerityGraph AI" })).toBeVisible();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByText(`${health.service} · v${health.version}`)).toBeVisible();
});
