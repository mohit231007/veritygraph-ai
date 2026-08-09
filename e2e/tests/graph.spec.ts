import { expect, test } from "@playwright/test";

test("analysis becomes an inspectable evidence graph with connection paths", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill("E2E Evidence Graph");
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "graph-evidence.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Microsoft acquired GitHub. GitHub partnered with OpenAI.",
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

  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("graph-node-list")).toContainText("Microsoft");
  await expect(page.getByTestId("graph-node-list")).toContainText("GitHub");
  await expect(page.getByTestId("graph-node-list")).toContainText("OpenAI");
  await expect(page.getByTestId("graph-edge-list")).toContainText("acquire");
  await expect(page.getByTestId("graph-edge-list")).toContainText("partner with");

  const acquisition = page
    .getByTestId("graph-edge-list")
    .getByRole("button")
    .filter({ hasText: "acquire" });
  await acquisition.click();
  await expect(page.getByTestId("graph-edge-detail")).toContainText("Microsoft");
  await expect(page.getByTestId("graph-edge-detail")).toContainText("GitHub");
  await expect(page.getByTestId("graph-edge-detail")).toContainText(
    "Microsoft acquired GitHub.",
  );
  await expect(page.getByTestId("graph-edge-detail")).toContainText("graph-evidence.txt");

  await page.getByTestId("path-from").selectOption({ label: "Microsoft" });
  await page.getByTestId("path-to").selectOption({ label: "OpenAI" });
  await page.getByTestId("find-path-button").click();
  await expect(page.getByTestId("path-message")).toContainText("2 hops");
  await expect(page.getByTestId("path-result")).toContainText("Microsoft");
  await expect(page.getByTestId("path-result")).toContainText("GitHub");
  await expect(page.getByTestId("path-result")).toContainText("OpenAI");

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("analysis-status")).toContainText("restored from SQLite", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("graph-status")).toContainText("Graph ready", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("graph-edge-list")).toContainText("acquire");
});
