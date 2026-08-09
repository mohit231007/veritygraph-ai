import { expect, test } from "@playwright/test";

test("lexical evidence retrieval keeps citation neighbors out of ranked hits", async ({ page }) => {
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

  const context = page.getByTestId("retrieval-context-card");
  await expect(context).toHaveCount(1);
  await expect(context).toContainText("retrieval-note.txt");
  await expect(context).toContainText("cites / references NVIDIA Networking Research");
  await expect(context).toContainText("URL reference");

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
  await expect(page.getByTestId("retrieval-hit-card")).toHaveCount(1);
  await expect(page.getByTestId("retrieval-context-card")).toContainText(
    "NVIDIA Networking Research",
  );
});
