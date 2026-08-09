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

test("unscoped asserted opposing polarity creates one evidence-backed contradiction candidate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill("E2E Assertion Polarity");
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await uploadAndAdd(page, "affirmed-source.txt", "Microsoft acquired GitHub.");
  await uploadAndAdd(page, "negated-source.txt", "Microsoft did not acquire GitHub.");
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await page.getByTestId("analyse-workspace-button").click();
  await expect(page.getByTestId("analysis-status")).toContainText("Analysis completed locally", {
    timeout: 20_000,
  });

  const relations = page.getByTestId("relation-list");
  await expect(relations).toContainText("Microsoft");
  await expect(relations).toContainText("GitHub");
  await expect(relations).toContainText("NOT acquire");
  await expect(relations).toContainText("NEGATED");
  await expect(relations).toContainText("AFFIRMED");
  await expect(relations).toContainText("ASSERTED");
  await expect(relations).toContainText("No explicit year");

  await expect(page.getByTestId("comparison-status")).toContainText("1 contradiction candidate", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("contradiction-count")).toContainText("1");
  await expect(page.getByTestId("comparison-guardrail")).toContainText(
    "Silence, modality, or different time scope ≠ contradiction",
  );

  const candidate = page.getByTestId("contradiction-candidate");
  await expect(candidate).toHaveCount(1);
  await expect(candidate).toContainText("Microsoft");
  await expect(candidate).toContainText("acquire");
  await expect(candidate).toContainText("GitHub");
  await expect(candidate).toContainText("No explicit year");
  await expect(candidate).toContainText("AFFIRMED");
  await expect(candidate).toContainText("NEGATED");
  await expect(candidate).toContainText("affirmed-source.txt");
  await expect(candidate).toContainText("negated-source.txt");
  await expect(candidate).toContainText("Microsoft acquired GitHub.");
  await expect(candidate).toContainText("Microsoft did not acquire GitHub.");
  await expect(candidate).toContainText("not a truth verdict");

  const graphEdges = page.getByTestId("graph-edge-list");
  await expect(graphEdges).toContainText("acquire");
  await expect(graphEdges).toContainText("NOT acquire");
  await expect(graphEdges).toContainText("NEGATED");
  await expect(graphEdges).toContainText("ASSERTED");

  await page.reload();
  await expect(page.getByTestId("workspace-detail")).toContainText("E2E Assertion Polarity");
  await expect(page.getByTestId("analysis-status")).toContainText("restored from SQLite", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("comparison-status")).toContainText("1 contradiction candidate", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("contradiction-candidate")).toContainText(
    "Microsoft did not acquire GitHub.",
  );
});
