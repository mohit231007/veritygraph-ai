import { expect, test } from "@playwright/test";

test("workspace analysis extracts a qualified relation and restores it after reload", async ({ page }) => {
  const workspaceName = "E2E NLP Evidence";
  const sentence = "Microsoft acquired GitHub in 2018.";

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "microsoft-github.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(sentence),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");

  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");

  const analysisPanel = page.getByTestId("analysis-panel");
  await analysisPanel.getByTestId("analyse-workspace-button").click();
  await expect(analysisPanel.getByTestId("analysis-status")).toContainText(
    "Analysis completed locally",
  );

  const relationList = analysisPanel.getByTestId("relation-list");
  await expect(relationList.getByText("Microsoft", { exact: true })).toBeVisible();
  await expect(relationList.getByText("acquire", { exact: true })).toBeVisible();
  await expect(relationList.getByText("GitHub", { exact: true })).toBeVisible();
  await expect(relationList.getByText(`“${sentence}”`, { exact: true })).toBeVisible();
  await expect(relationList.getByText("Rule score 92", { exact: true })).toBeVisible();
  await expect(relationList.getByText("AFFIRMED", { exact: true })).toBeVisible();
  await expect(relationList.getByText("ASSERTED", { exact: true })).toBeVisible();
  await expect(relationList.getByText("Year 2018", { exact: true })).toBeVisible();
  await expect(
    analysisPanel.getByText("Polarity · modality · explicit year scope · rule score ≠ truth"),
  ).toBeVisible();
  await expect(analysisPanel.getByText("Qualifier guardrail", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail").getByText(workspaceName, { exact: true })).toBeVisible();
  await expect(page.getByTestId("analysis-status")).toContainText(
    "Latest completed analysis restored from SQLite",
  );
  await expect(page.getByTestId("analysis-status")).toContainText(
    "matched to the current source set",
  );
  const restoredRelations = page.getByTestId("relation-list");
  await expect(restoredRelations.getByText("acquire", { exact: true })).toBeVisible();
  await expect(restoredRelations.getByText("AFFIRMED", { exact: true })).toBeVisible();
  await expect(restoredRelations.getByText("ASSERTED", { exact: true })).toBeVisible();
  await expect(restoredRelations.getByText("Year 2018", { exact: true })).toBeVisible();
});
