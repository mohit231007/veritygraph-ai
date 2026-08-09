import { expect, test } from "@playwright/test";

test("legal organization aliases consolidate before graph projection", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill("E2E Entity Resolution");
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "aliases.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Microsoft Corporation acquired GitHub. Microsoft acquired OpenAI.",
    ),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready");

  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");

  await page.getByTestId("analyse-workspace-button").click();
  await expect(page.getByTestId("analysis-status")).toContainText("Analysis completed locally", {
    timeout: 20_000,
  });

  const entityList = page.getByTestId("entity-list");
  const microsoftEntity = entityList.getByRole("article").filter({ hasText: "Microsoft" });
  await expect(microsoftEntity).toHaveCount(1);
  await expect(microsoftEntity).toContainText("Microsoft");
  await expect(microsoftEntity).toContainText("2 mentions");
  await expect(microsoftEntity.getByTestId("entity-aliases")).toContainText(
    "Microsoft Corporation",
  );

  await expect(page.getByTestId("analysis-results")).toContainText(
    "deterministic-org-aliases-v1",
  );
  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });

  const microsoftGraphNodes = page
    .getByTestId("graph-node-list")
    .getByRole("button")
    .filter({ hasText: "Microsoft" });
  await expect(microsoftGraphNodes).toHaveCount(1);

  await page.reload();
  await expect(page.getByTestId("workspace-detail")).toContainText("E2E Entity Resolution");
  await expect(page.getByTestId("analysis-status")).toContainText("restored from SQLite", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("entity-list")).toContainText("Microsoft Corporation");
  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });
});
