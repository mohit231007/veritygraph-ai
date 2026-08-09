import { expect, test } from "@playwright/test";

test("workspace keeps a source after browser reload", async ({ page }) => {
  const workspaceName = "E2E Persistent Research";

  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill(workspaceName);
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await page.getByTestId("document-input").setInputFiles({
    name: "persistent-evidence.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("NVIDIA acquired Mellanox Technologies."),
  });
  await page.getByRole("button", { name: "Analyse document" }).click();
  await expect(page.getByTestId("upload-status")).toContainText("Ready · 1 evidence spans");

  await page.getByTestId("workspace-add-source").click();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await expect(
    page.getByTestId("workspace-source-list").getByText("persistent-evidence.txt"),
  ).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");
  await expect(page.getByTestId("workspace-detail").getByText(workspaceName, { exact: true })).toBeVisible();
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await expect(
    page.getByTestId("workspace-source-list").getByText("persistent-evidence.txt"),
  ).toBeVisible();
});
