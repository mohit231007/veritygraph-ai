import { expect, test } from "@playwright/test";

test("TXT upload keeps source provenance from browser to preview", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("document-input").setInputFiles({
    name: "evidence.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "NVIDIA acquired Mellanox Technologies.\n\nMellanox expanded NVIDIA networking capabilities.",
    ),
  });

  await page.getByRole("button", { name: "Analyse document" }).click();

  await expect(page.getByTestId("upload-status")).toContainText(
    "Ready · 2 evidence spans extracted.",
  );
  const preview = page.getByTestId("source-preview");
  await expect(preview.getByRole("heading", { name: "evidence.txt" })).toBeVisible();
  await expect(preview.getByText("Page 1 · Paragraph 1")).toBeVisible();
  await expect(preview.getByText("Page 1 · Paragraph 2")).toBeVisible();
  await expect(preview.getByText("NVIDIA acquired Mellanox Technologies.")).toBeVisible();
  await expect(
    preview.getByText("Mellanox expanded NVIDIA networking capabilities."),
  ).toBeVisible();
});
