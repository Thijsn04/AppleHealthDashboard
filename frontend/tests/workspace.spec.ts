import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("import, inspect, compare and export from a local responsive workspace", async ({ page }) => {
  const external: string[] = [];
  const errors: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith("http://127.0.0.1:8765/") && !request.url().startsWith("blob:")) external.push(request.url());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Health overview" })).toBeVisible();
  await page.getByRole("button", { name: "Try synthetic demo" }).click();
  await expect(page.getByRole("heading", { name: "Review import" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("heading", { name: "Review import" })).toHaveCount(0);
  await page.getByRole("button", { name: "Try synthetic demo" }).click();
  await page.getByRole("button", { name: "Confirm import" }).click();
  await expect(page.getByRole("status").filter({ hasText: "observations" })).toContainText("added");
  await expect(page.getByRole("heading", { name: "Data coverage" })).toBeVisible();
  await expect(page.getByRole("img", { name: /Steps.*Observed range/ })).toBeVisible();
  const slider = page.getByRole("slider");
  const latest = await slider.getAttribute("aria-valuetext");
  await slider.press("ArrowLeft");
  await expect(slider).not.toHaveAttribute("aria-valuetext", latest!);
  await page.getByLabel("Theme").selectOption("light");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  if (process.env.HEALTH_SCREENSHOTS) {
    await page.reload();
    await expect(page.getByRole("img", { name: /Steps.*Observed range/ })).toBeVisible();
    await page.screenshot({ path: "../docs/screenshots/overview.png" });
  }

  await page.getByRole("link", { name: "Data Explorer", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Source observations" })).toBeVisible();
  await page.getByLabel("Compare with").selectOption("HKQuantityTypeIdentifierRestingHeartRate");
  await expect(page.getByText("Pearson r")).toBeVisible();
  await page.getByRole("combobox", { name: "Source", exact: true }).selectOption("source:Demo Watch");
  await page.getByLabel("Group by").selectOption("week");
  await expect(page.getByText(/Total per week/)).toBeVisible();
  await expect(page.getByText("Pearson r")).toHaveCount(0);
  await page.getByLabel("From").fill("2025-10-01");
  await expect(page.getByText("31 matching records")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV" }).first().click();
  expect((await download).suggestedFilename()).toBe("apple-health-series.csv");
  await page.getByText("Method and contributing records").first().click();
  await expect(page.getByText("Period start").first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations.map(({ id }) => id)).toEqual([]);
  if (process.env.HEALTH_SCREENSHOTS) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: "../docs/screenshots/explorer.png" });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel("Theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  expect((await new AxeBuilder({ page }).analyze()).violations.map(({ id }) => id)).toEqual([]);
  await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("link", { name: "Sleep", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recorded stages" })).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.getByRole("heading", { name: "Recorded stages" })).toBeVisible();
  if (process.env.HEALTH_SCREENSHOTS) await page.screenshot({ path: "../docs/screenshots/sleep-mobile.png" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const metric = "HKQuantityTypeIdentifierWalkingHeartRateAverage";
  const first = Date.UTC(2015, 10, 5, 12);
  const days = 3650;
  const entries = Array.from({ length: days }, (_, i) => {
    const date = new Date(first + i * 86_400_000).toISOString().slice(0, 10);
    const stamp = `${date} 12:00:00 +0000`;
    return `<Record type="${metric}" unit="count/min" value="${85 + i % 19}" sourceName="Chart fixture" startDate="${stamp}" endDate="${stamp}"/>`;
  });
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-chart.xml", mimeType: "application/xml", buffer: Buffer.from(`<HealthData>${entries.join("")}</HealthData>`),
  });
  await page.getByRole("button", { name: "Confirm import" }).click();
  await expect(page.getByRole("status").filter({ hasText: "3,650 observations" })).toBeVisible();
  await page.getByRole("link", { name: "Data Explorer", exact: true }).click();
  await page.getByRole("combobox", { name: "Metric", exact: true }).selectOption(metric);
  const started = performance.now();
  await page.getByLabel("From").fill("2015-11-05");
  await expect(page.getByText(/Sample mean per day.*3,650 observed days/)).toBeVisible();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  console.log(`3,650-point chart, filter change through painted frame: ${Math.round(performance.now() - started)} ms`);
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});
