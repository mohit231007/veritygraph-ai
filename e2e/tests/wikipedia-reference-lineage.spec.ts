import { expect, test } from "@playwright/test";

test("selected Wikipedia citation preserves citing context and bibliography entry", async ({ page }) => {
  const workspaceName = "E2E Wikipedia Citation Lineage";
  const targetUrl = "https://example.com/research/nvidia-founding";

  const workspaceResponse = await page.request.post("/api/v1/workspaces", {
    data: { name: workspaceName },
  });
  expect(workspaceResponse.ok()).toBeTruthy();
  const workspace = await workspaceResponse.json();

  const importResponse = await page.request.post("/api/v1/wikipedia/import", {
    data: {
      page_id: 609498,
      section_indices: ["1"],
    },
  });
  expect(importResponse.ok()).toBeTruthy();
  const bundle = await importResponse.json();
  expect(bundle.references).toHaveLength(1);
  expect(bundle.references[0].citation_label).toBe("[1]");
  expect(bundle.references[0].citation_marker).toBe("cite_note-fixture-history-1");
  expect(bundle.references[0].reference_text).toContain("Nvidia founding timeline");
  expect(bundle.references[0].span_id).toBe(bundle.spans[0].span_id);

  const addResponse = await page.request.put(
    `/api/v1/workspaces/${workspace.workspace_id}/sources/${bundle.document.source_id}`,
  );
  expect(addResponse.ok()).toBeTruthy();

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("reference-lineage-status")).toContainText(
    "1 explicit reference · 0 uniquely resolved · 0 ambiguous · 1 external",
    { timeout: 10_000 },
  );

  const edge = page.getByTestId("reference-lineage-edge");
  await expect(edge).toContainText("Nvidia");
  await expect(edge).toContainText(targetUrl);
  await expect(edge).toContainText("External / not ingested");
  await expect(edge).toContainText("Citation [1]");
  await expect(edge).toContainText("cite_note-fixture-history-1");
  await expect(edge).toContainText("Nvidia was founded in 1993.");
  await expect(edge).toContainText(
    "Reference entry · Example Research. Nvidia founding timeline. Retrieved 2026.",
  );
  await expect(edge).toContainText("mediawiki_inline_citation_v1");
  await expect(page.getByTestId("reference-lineage-guardrail")).toContainText(
    "Explicit URL ≠ endorsement, quotation, dependence, or truth",
  );

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("reference-lineage-status")).toContainText(
    "1 explicit reference · 0 uniquely resolved · 0 ambiguous · 1 external",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("reference-lineage-edge")).toContainText(
    "Reference entry · Example Research. Nvidia founding timeline. Retrieved 2026.",
  );
});
