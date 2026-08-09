import { expect, test } from "@playwright/test";

test("retrieval, evidence packing and evaluation preserve the provenance boundary", async ({ page }) => {
  const workspaceName = "E2E Retrieval Preview";
  const targetUrl = "https://example.com/research/nvidia-networking";
  const evidenceText = `Primary evidence: ${targetUrl}#methods`;

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "retrieval-note.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(evidenceText),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");
  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");

  await page.getByTestId("public-url-mode").click();
  await page.getByTestId("public-url-input").fill(targetUrl);
  await page.getByTestId("public-url-import-button").click();
  await expect(page.getByTestId("public-url-status")).toContainText("Ready ·");
  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await page.getByTestId("retrieval-query-input").fill("Primary evidence");
  await page.getByTestId("retrieval-search-button").click();
  await expect(page.getByTestId("retrieval-preview-status")).toContainText(
    "1 ranked span from 1 source · 1 citation context item",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("retrieval-hit-count")).toContainText("1");
  await expect(page.getByTestId("retrieval-context-count")).toContainText("1");
  await expect(page.getByTestId("retrieval-preview-guardrail")).toContainText(
    "Citation neighbor ≠ retrieved evidence or query support",
  );

  const hit = page.getByTestId("retrieval-hit-card");
  await expect(hit).toHaveCount(1);
  await expect(hit).toContainText("retrieval-note.txt");
  await expect(hit).toContainText(evidenceText);
  await expect(hit).toContainText("Matched · primary · evidence");
  await expect(hit).not.toContainText("NVIDIA Networking Research");
  const hitText = (await hit.textContent()) ?? "";
  const spanId = hitText.match(/span_[A-Za-z0-9_-]+/)?.[0];
  expect(spanId).toBeTruthy();

  const context = page.getByTestId("retrieval-context-card");
  await expect(context).toHaveCount(1);
  await expect(context).toContainText("retrieval-note.txt");
  await expect(context).toContainText("cites / references NVIDIA Networking Research");
  await expect(context).toContainText("URL reference");

  await page.getByTestId("evidence-pack-query-input").fill("Primary evidence");
  await page.getByTestId("evidence-pack-build-button").click();
  await expect(page.getByTestId("evidence-pack-status")).toContainText(
    "Pack ready · 1 excerpt · 1 source",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("evidence-pack-excerpt-count")).toContainText("1");
  await expect(page.getByTestId("evidence-pack-context-count")).toContainText("1");
  await expect(page.getByTestId("evidence-pack-guardrail")).toContainText(
    "Citation neighbor text is not generator evidence unless independently retrieved",
  );
  const excerpt = page.getByTestId("evidence-pack-excerpt");
  await expect(excerpt).toHaveCount(1);
  await expect(excerpt).toContainText("retrieval-note.txt");
  await expect(excerpt).toContainText(evidenceText);
  await expect(excerpt).not.toContainText("NVIDIA Networking Research");
  await expect(page.getByTestId("evidence-pack-context-item")).toContainText(
    "NVIDIA Networking Research",
  );

  await page.getByTestId("retrieval-evaluation-cases-input").fill(
    JSON.stringify([
      {
        case_id: "browser-gold",
        query: "Primary evidence",
        relevant_span_ids: [spanId],
      },
    ]),
  );
  await page.getByTestId("retrieval-evaluation-k-input").fill("1");
  await page.getByTestId("retrieval-evaluation-button").click();
  await expect(page.getByTestId("retrieval-evaluation-status")).toContainText(
    "Evaluation ready · 1 case · MRR 1.000",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("retrieval-mrr")).toContainText("1.000");
  await expect(page.getByTestId("retrieval-evaluation-metric-card")).toContainText("Recall · 1.000");

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await page.getByTestId("retrieval-query-input").fill("Primary evidence");
  await page.getByTestId("retrieval-search-button").click();
  await expect(page.getByTestId("retrieval-preview-status")).toContainText(
    "1 ranked span from 1 source · 1 citation context item",
    { timeout: 10_000 },
  );

  await page.getByTestId("evidence-pack-query-input").fill("Primary evidence");
  await page.getByTestId("evidence-pack-build-button").click();
  await expect(page.getByTestId("evidence-pack-status")).toContainText(
    "Pack ready · 1 excerpt · 1 source",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("evidence-pack-context-item")).toContainText(
    "NVIDIA Networking Research",
  );

  await page.getByTestId("retrieval-evaluation-cases-input").fill(
    JSON.stringify([
      {
        case_id: "browser-gold-reload",
        query: "Primary evidence",
        relevant_span_ids: [spanId],
      },
    ]),
  );
  await page.getByTestId("retrieval-evaluation-k-input").fill("1");
  await page.getByTestId("retrieval-evaluation-button").click();
  await expect(page.getByTestId("retrieval-mrr")).toContainText("1.000", { timeout: 10_000 });
});
