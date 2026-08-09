import { expect, test } from "@playwright/test";

test("shared DOI mentions stay separate from source identity after reload", async ({ page }) => {
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
    "1 observation · 0 shared across sources · 0 resolved source identities · 0 ambiguous targets",
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
    "2 observations · 2 shared across sources · 0 resolved source identities · 0 ambiguous targets",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("bibliographic-match-count")).toContainText("2");
  await expect(page.getByTestId("resolved-identity-target-count")).toContainText("0");
  await expect(page.getByTestId("bibliographic-identity-guardrail")).toContainText(
    "Shared identifier ≠ source identity. Source identity ≠ citation, endorsement, authorship, factual support, or truth",
  );

  const cards = page.getByTestId("bibliographic-identifier-card");
  await expect(cards).toHaveCount(2);
  await expect(cards.nth(0)).toContainText(normalizedDoi);
  await expect(cards.nth(1)).toContainText(normalizedDoi);
  await expect(cards.nth(0)).toContainText("Shared by one other source");
  await expect(cards.nth(1)).toContainText("Shared by one other source");
  await expect(cards.nth(0)).toContainText("Source mention");
  await expect(page.getByTestId("identity-target")).toHaveCount(0);

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");
  await expect(page.getByTestId("bibliographic-identity-status")).toContainText(
    "2 observations · 2 shared across sources · 0 resolved source identities · 0 ambiguous targets",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("bibliographic-identifier-card")).toHaveCount(2);
  await expect(page.getByTestId("identity-target")).toHaveCount(0);
});
