import { expect, test } from "@playwright/test";

test("public URL import becomes traceable canonical evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("public-url-mode").click();
  await page
    .getByTestId("public-url-input")
    .fill("https://example.com/research/nvidia-networking");
  await page.getByTestId("public-url-import-button").click();

  await expect(page.getByTestId("public-url-status")).toContainText("Ready ·");

  const preview = page.getByTestId("source-preview");
  await expect(
    preview.getByRole("heading", { name: "NVIDIA Networking Research" }),
  ).toBeVisible();
  await expect(preview.getByText("public url", { exact: true })).toBeVisible();
  await expect(
    preview.getByText(/NVIDIA acquired Mellanox Technologies/),
  ).toBeVisible();
  await expect(
    preview.getByText(/Mellanox technology connects accelerated computing systems/),
  ).toBeVisible();
  await expect(preview.getByRole("link", { name: /Open original public source/ })).toHaveAttribute(
    "href",
    "https://example.com/research/nvidia-networking",
  );
});
