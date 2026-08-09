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

test("two sources expose corroboration and transparent relationship signals", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("api-status")).toHaveText("API healthy");

  await page.getByTestId("workspace-name-input").fill("E2E Source Comparison");
  await page.getByTestId("workspace-create-button").click();
  await expect(page.getByTestId("workspace-message")).toContainText("created locally");

  await uploadAndAdd(page, "source-one.txt", "Microsoft acquired GitHub. GitHub acquired OpenAI.");
  await expect(page.getByTestId("workspace-source-count")).toHaveText("1 source");
  await uploadAndAdd(page, "source-two.txt", "Microsoft acquired GitHub. Amazon acquired Twitch.");
  await expect(page.getByTestId("workspace-source-count")).toHaveText("2 sources");

  await page.getByTestId("analyse-workspace-button").click();
  await expect(page.getByTestId("analysis-status")).toContainText("Analysis completed locally", {
    timeout: 20_000,
  });
  await expect(page.getByTestId("comparison-status")).toContainText(
    "Comparison ready · 1 cross-source · 2 single-source",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("comparison-status")).toContainText("1 relationship review signal");
  await expect(page.getByTestId("contradiction-count")).toContainText("0");
  await expect(page.getByTestId("relationship-signal-count")).toContainText("1");
  await expect(page.getByTestId("comparison-guardrail")).toContainText(
    "Source IDs ≠ independent reports",
  );
  await expect(page.getByTestId("comparison-guardrail")).toContainText(
    "does not prove independence",
  );
  await expect(page.getByTestId("source-profile-list")).toContainText("source-one.txt");
  await expect(page.getByTestId("source-profile-list")).toContainText("source-two.txt");

  await page.getByTestId("comparison-filter-cross_source").click();
  const claimList = page.getByTestId("comparison-claim-list");
  await expect(claimList.getByRole("button")).toHaveCount(1);
  await expect(claimList).toContainText("Microsoft");
  await expect(claimList).toContainText("acquire");
  await expect(claimList).toContainText("GitHub");
  await expect(claimList).toContainText("AFFIRMED");
  await expect(claimList).toContainText("ASSERTED");
  await expect(claimList).toContainText("No explicit year");
  await expect(claimList).toContainText("2 sources");

  await claimList.getByRole("button").click();
  const detail = page.getByTestId("comparison-claim-detail");
  await expect(detail).toContainText("AFFIRMED");
  await expect(detail).toContainText("ASSERTED");
  await expect(detail).toContainText("CROSS-SOURCE SUPPORT");
  await expect(detail).toContainText("source-one.txt");
  await expect(detail).toContainText("source-two.txt");
  await expect(detail).toContainText("Microsoft acquired GitHub.");

  const diversity = page.getByTestId("claim-diversity");
  await expect(diversity).toContainText("2 distinct content fingerprints");
  await expect(diversity).toContainText("1 distinct evidence text");
  await expect(diversity).toContainText("Repeated supporting text signal");
  await expect(diversity).not.toContainText("Exact content duplicate signal");

  const pair = page.getByTestId("source-pair-overlap");
  await expect(pair).toContainText("1 shared / 3 union");
  await expect(pair).toContainText("33.3% overlap");
  await expect(pair).toContainText("1 exact shared supporting text");
  await expect(pair).toContainText("Relationship review signal · not proof of copying");
  await expect(pair).toContainText("Microsoft acquired GitHub.");

  await page.reload();
  await expect(page.getByTestId("workspace-detail")).toContainText("E2E Source Comparison");
  await expect(page.getByTestId("analysis-status")).toContainText("restored from SQLite", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("comparison-status")).toContainText("Comparison ready", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("relationship-signal-count")).toContainText("1");
  await expect(page.getByTestId("source-pair-overlap")).toContainText(
    "Relationship review signal · not proof of copying",
  );
  await expect(page.getByTestId("contradiction-count")).toContainText("0");
});
