import { expect, test } from "@playwright/test";

test("imported source can be saved to the active workspace beside its preview", async ({ page }) => {
  const workspaceName = "E2E Source Handoff";

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("0 sources");

  await page.getByTestId("document-input").setInputFiles({
    name: "handoff-note.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Microsoft acquired GitHub in 2018."),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");

  const handoff = page.getByTestId("source-workspace-handoff");
  await expect(handoff).toContainText("Keep the imported source with your research");
  await expect(handoff).toContainText("imported but not yet part of");
  await expect(handoff).toContainText(workspaceName);

  await page.getByTestId("source-workspace-save-button").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await expect(handoff).toContainText("Source is ready for workspace intelligence");
  await expect(handoff).toContainText(`Saved “handoff-note.txt” in ${workspaceName}.`);
  await expect(page.getByTestId("source-workspace-save-button")).toContainText(
    `Saved in ${workspaceName}`,
  );

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail")).toContainText(workspaceName);
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await expect(page.getByTestId("workspace-source-list")).toContainText("handoff-note.txt");
});
