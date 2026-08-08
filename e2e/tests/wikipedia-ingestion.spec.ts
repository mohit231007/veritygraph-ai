import { expect, test } from "@playwright/test";

test("Wikipedia search and selected sections become canonical evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("wikipedia-mode").click();
  await page.getByTestId("wikipedia-search-input").fill("NVIDIA");
  await page.getByRole("button", { name: "Search Wikipedia" }).click();

  const results = page.getByTestId("wikipedia-results");
  await expect(results.getByRole("heading", { name: "Nvidia" })).toBeVisible();
  await results.getByRole("button", { name: "Inspect sections" }).click();

  const outline = page.getByTestId("wikipedia-outline");
  await expect(outline.getByRole("heading", { name: "Nvidia" })).toBeVisible();
  await expect(outline.getByText("History", { exact: true })).toBeVisible();
  await outline.getByText("History", { exact: true }).click();
  await expect(outline.getByText("2 selected")).toBeVisible();

  await page.getByTestId("wikipedia-import-button").click();
  await expect(page.getByTestId("wikipedia-import-status")).toContainText(
    "Ready · 4 evidence spans imported.",
  );

  const preview = page.getByTestId("source-preview");
  await expect(preview.getByRole("heading", { name: "Nvidia" })).toBeVisible();
  await expect(preview.getByText("Overview · Paragraph 1")).toBeVisible();
  await expect(preview.getByText("History · Paragraph 1")).toBeVisible();
  await expect(
    preview.getByText("Nvidia was founded in 1993."),
  ).toBeVisible();
  await expect(preview.getByRole("link", { name: /Open original public source/ })).toHaveAttribute(
    "href",
    /wikipedia\.org/,
  );
});
