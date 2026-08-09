import { expect, test } from "@playwright/test";

async function uploadAndAdd(page, name: string, text: string) {
  await page.getByTestId("document-input").setInputFiles({
    name,
    mimeType: "text/plain",
    buffer: Buffer.from(text),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready");
  await page.getByTestId("workspace-add-source").click();
}

test("time scope and modality block false contradiction and graph inference", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill("E2E Assertion Qualifiers");
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await uploadAndAdd(page, "past-yes.txt", "Microsoft acquired GitHub in 2018.");
  await uploadAndAdd(page, "later-no.txt", "Microsoft did not acquire GitHub in 2019.");
  await uploadAndAdd(page, "future-modal.txt", "Microsoft may acquire OpenAI in 2027.");
  await uploadAndAdd(page, "future-no.txt", "Microsoft did not acquire OpenAI in 2027.");
  await expect(page.getByTestId("workspace-source-count")).toHaveText("4 sources");

  await page.getByTestId("analyse-workspace-button").click();
  await expect(page.getByTestId("analysis-status")).toContainText("Analysis completed locally", {
    timeout: 20_000,
  });

  const relations = page.getByTestId("relation-list");
  await expect(relations).toContainText("Year 2018");
  await expect(relations).toContainText("Year 2019");
  await expect(relations).toContainText("Year 2027");
  await expect(relations).toContainText("MODAL acquire");
  await expect(relations).toContainText("MODAL");

  await expect(page.getByTestId("comparison-status")).toContainText("0 contradiction candidates", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("contradiction-count")).toContainText("0");
  await expect(page.getByTestId("comparison-guardrail")).toContainText("disjoint years");
  await expect(page.getByTestId("comparison-guardrail")).toContainText("modal language");

  const graphEdges = page.getByTestId("graph-edge-list");
  await expect(graphEdges).toContainText("MODAL acquire");
  await expect(graphEdges).toContainText("Year 2027");
  await expect(page.getByTestId("graph-qualifier-legend")).toContainText("exclude explicit NOT and MODAL");

  await page.getByTestId("path-from").selectOption({ label: "Microsoft" });
  await page.getByTestId("path-to").selectOption({ label: "OpenAI" });
  await page.getByTestId("find-path-button").click();
  await expect(page.getByTestId("path-message")).toContainText("No connection path exists");

  await page.reload();
  await expect(page.getByTestId("workspace-detail")).toContainText("E2E Assertion Qualifiers");
  await expect(page.getByTestId("analysis-status")).toContainText("restored from SQLite", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("relation-list")).toContainText("Year 2027");
  await expect(page.getByTestId("comparison-status")).toContainText("0 contradiction candidates", {
    timeout: 10_000,
  });
});
