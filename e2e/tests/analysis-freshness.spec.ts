import { expect, test } from "@playwright/test";

async function uploadAndAdd(page, name: string, text: string) {
  await page.getByTestId("document-input").setInputFiles({
    name,
    mimeType: "text/plain",
    buffer: Buffer.from(text),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");
  await page.getByTestId("workspace-add-source").click();
}

test("persisted analysis is reused only for the exact current workspace source set", async ({ page }) => {
  const workspaceName = "E2E Analysis Freshness";

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await uploadAndAdd(page, "initial-source.txt", "Microsoft acquired GitHub.");
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await page.getByTestId("analyse-workspace-button").click();
  await expect(page.getByTestId("analysis-status")).toContainText("Analysis completed locally", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });

  await uploadAndAdd(page, "new-source.txt", "Apple acquired Beats Electronics.");
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");
  await expect(page.getByTestId("analysis-status")).toContainText(
    "Workspace sources changed since the latest completed analysis",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("analysis-results")).toHaveCount(0);

  await page.getByTestId("analyse-workspace-button").click();
  await expect(page.getByTestId("analysis-status")).toContainText("Analysis completed locally", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("comparison-status")).toContainText("Comparison ready", {
    timeout: 10_000,
  });

  await page.reload();
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("analysis-status")).toContainText(
    "restored from SQLite and matched to the current source set",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("comparison-status")).toContainText("Comparison ready", {
    timeout: 10_000,
  });
});
