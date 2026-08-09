import { expect, test } from "@playwright/test";

test("explicit URL reference resolves into citation topology and survives reload", async ({ page }) => {
  const workspaceName = "E2E Citation Lineage";
  const targetUrl = "https://example.com/research/nvidia-networking";
  const citationSentence = `Primary evidence: ${targetUrl}#methods`;

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "citation-note.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(citationSentence),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");
  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");

  await expect(page.getByTestId("reference-lineage-status")).toContainText(
    "1 explicit reference · 0 uniquely resolved · 0 ambiguous · 1 external",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("citation-graph-status")).toContainText(
    "1 sources · 0 directed edges · 1 unresolved · 0 ambiguous",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("citation-edge-count")).toContainText("0");
  await expect(page.getByTestId("reference-lineage-guardrail")).toContainText(
    "Explicit URL ≠ endorsement, quotation, dependence, or truth",
  );
  let referenceEdge = page.getByTestId("reference-lineage-edge");
  await expect(referenceEdge).toContainText("citation-note.txt");
  await expect(referenceEdge).toContainText("External / not ingested");
  await expect(referenceEdge).toContainText(targetUrl);
  await expect(referenceEdge).toContainText(citationSentence);
  await expect(referenceEdge).toContainText("visible_url_in_source_span_v1");

  await page.getByTestId("public-url-mode").click();
  await page.getByTestId("public-url-input").fill(targetUrl);
  await page.getByTestId("public-url-import-button").click();
  await expect(page.getByTestId("public-url-status")).toContainText("Ready ·");
  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await expect(page.getByTestId("reference-lineage-status")).toContainText(
    "1 explicit reference · 1 uniquely resolved · 0 ambiguous · 0 external",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("resolved-reference-count")).toContainText("1");
  referenceEdge = page.getByTestId("reference-lineage-edge");
  await expect(referenceEdge).toContainText("citation-note.txt");
  await expect(referenceEdge).toContainText("NVIDIA Networking Research");
  await expect(referenceEdge).toContainText("Workspace source");
  await expect(referenceEdge).toContainText(targetUrl);
  await expect(referenceEdge).toContainText(citationSentence);
  await expect(referenceEdge).toContainText(/span_/);

  await expect(page.getByTestId("citation-graph-status")).toContainText(
    "2 sources · 1 directed edge · 0 unresolved · 0 ambiguous",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("citation-edge-count")).toContainText("1");
  await expect(page.getByTestId("citation-graph-guardrail")).toContainText(
    "Edge = explicit uniquely resolved reference, not factual support or truth",
  );
  const citationEdge = page.getByTestId("citation-edge-card");
  await expect(citationEdge).toContainText("citation-note.txt");
  await expect(citationEdge).toContainText("NVIDIA Networking Research");
  await expect(citationEdge).toContainText("URL reference");

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");
  await expect(page.getByTestId("reference-lineage-status")).toContainText(
    "1 explicit reference · 1 uniquely resolved · 0 ambiguous · 0 external",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("reference-lineage-edge")).toContainText(
    "NVIDIA Networking Research",
  );
  await expect(page.getByTestId("citation-graph-status")).toContainText(
    "2 sources · 1 directed edge · 0 unresolved · 0 ambiguous",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("citation-edge-card")).toContainText(
    "NVIDIA Networking Research",
  );
});
