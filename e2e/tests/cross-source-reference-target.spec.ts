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

test("shared external reference targets are review signals, not citation edges", async ({ page }) => {
  const workspaceName = "E2E Shared Reference Target";
  const sharedTarget = "https://example.com/research/shared-study";

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await uploadAndAdd(page, "left-source.txt", `Left source cites ${sharedTarget}.`);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await uploadAndAdd(page, "right-source.txt", `Right source also cites ${sharedTarget}.`);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await expect(page.getByTestId("reference-lineage-status")).toContainText(
    "2 explicit references · 0 uniquely resolved · 0 ambiguous · 2 external",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("unique-reference-target-count")).toContainText("1");
  await expect(page.getByTestId("cross-source-target-count")).toContainText("1");
  await expect(page.getByTestId("cross-source-target-guardrail")).toContainText(
    "not a directed source-to-source citation edge",
  );

  const group = page.getByTestId("reference-lineage-target");
  await expect(group).toContainText(sharedTarget);
  await expect(group).toContainText("2 occurrences · 2 citing sources");
  await expect(group).toContainText("Cross-source");
  await expect(group).toContainText("left-source.txt");
  await expect(group).toContainText("right-source.txt");

  await page.getByTestId("reference-source-scope-filter").selectOption("cross_source");
  await expect(page.getByTestId("reference-lineage-target")).toHaveCount(1);
  await page.getByTestId("reference-source-scope-filter").selectOption("single_source");
  await expect(page.getByText("No unique reference target matches the current search and filters.")).toBeVisible();

  await expect(page.getByTestId("citation-graph-status")).toContainText(
    "2 sources · 0 directed edges · 2 unresolved · 0 ambiguous",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("citation-edge-count")).toContainText("0");
  await expect(page.getByTestId("citation-graph-empty-state")).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("cross-source-target-count")).toContainText("1", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("citation-edge-count")).toContainText("0");
});
