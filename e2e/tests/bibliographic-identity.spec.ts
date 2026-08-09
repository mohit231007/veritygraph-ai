import { expect, test } from "@playwright/test";

test("exact DOI identity matches across sources and survives reload", async ({ page }) => {
  const workspaceName = "E2E Bibliographic Identity";
  const normalizedDoi = "10.1000/verity.test";

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "doi-left.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Primary record DOI:10.1000/VERITY.TEST"),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");
  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");

  await expect(page.getByTestId("bibliographic-identity-status")).toContainText(
    "1 observation · 0 exact workspace matches · 0 ambiguous",
    { timeout: 10_000 },
  );

  await page.getByTestId("document-input").setInputFiles({
    name: "doi-right.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Secondary record doi:10.1000/verity.test"),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");
  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await expect(page.getByTestId("bibliographic-identity-status")).toContainText(
    "2 observations · 2 exact workspace matches · 0 ambiguous",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("bibliographic-match-count")).toContainText("2");
  await expect(page.getByTestId("bibliographic-identity-guardrail")).toContainText(
    "Identifier match ≠ citation, endorsement, authorship, dependence, or truth",
  );

  const cards = page.getByTestId("bibliographic-identifier-card");
  await expect(cards).toHaveCount(2);
  await expect(cards.nth(0)).toContainText(normalizedDoi);
  await expect(cards.nth(1)).toContainText(normalizedDoi);
  await expect(cards.nth(0)).toContainText("Exact workspace identity");
  await expect(cards.nth(1)).toContainText("Exact workspace identity");
  await expect(cards.nth(0)).toContainText("Source mention");

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");
  await expect(page.getByTestId("bibliographic-identity-status")).toContainText(
    "2 observations · 2 exact workspace matches · 0 ambiguous",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("bibliographic-identifier-card")).toHaveCount(2);
});
