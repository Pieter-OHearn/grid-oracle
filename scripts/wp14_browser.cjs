/* Built frontend + persisted PostgreSQL replay; no response interception. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.WP14_PREVIEW_URL || 'http://127.0.0.1:4174';
const output = path.resolve(process.env.WP14_BROWSER_OUTPUT || '/tmp/wp14-evidence/browser');
const faults = path.resolve(process.env.WP14_PREVIEW_OUTPUT || '/tmp/wp14-preview');
const axe = process.env.AXE_PATH;
assert(axe, 'AXE_PATH must identify pinned axe-core 4.10.3');
assert(new URL(base).hostname === '127.0.0.1', 'only loopback fixture allowed');
fs.mkdirSync(output, { recursive: true });
const report = { passed: false, checks: [], accessibility: [], errors: [], requests: [], limits: 'Synthetic replay with real PG/API/built React. Automated Chromium/axe only; no assistive-technology/device or public-ingress claim.' };
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_EXECUTABLE ? { executablePath: process.env.CHROME_EXECUTABLE } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
  const page = await context.newPage();
  page.on('pageerror', e => report.errors.push(e.message));
  page.on('request', r => report.requests.push(r.url()));
  const record = name => report.checks.push({ name, passed: true });
  const open = async (url, title) => {
    await page.goto(base + url);
    await page.getByRole('heading', { name: title, exact: true }).waitFor();
  };
  const audit = async name => {
    await page.addScriptTag({ path: axe });
    const result = await page.evaluate(async () => await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }));
    report.accessibility.push({ name, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) })), incomplete: result.incomplete.map(v => v.id) });
    assert.equal(result.violations.length, 0, JSON.stringify(report.accessibility.at(-1)));
  };
  const full = '/seasons/2026/events/2026/field';
  try {
    await open(full, 'Horizon and revision comparison');
    const field = page.getByRole('region', { name: 'Full-field win probability comparison' });
    await field.waitFor();
    assert.equal(await field.locator('tbody tr').count(), 22);
    assert.match(await field.innerText(), /4\.5%/);
    await page.reload(); await field.waitFor();
    assert.equal(await field.locator('tbody tr').count(), 22);
    assert.doesNotMatch(await page.locator('body').innerText(), /NaN|\/private\/|internal_secret/);
    record('Deep-link refresh serves persisted 22-entry field across both horizons');
    const saved = await (await context.request.get(base + '/api/v1/seasons/2026/events/2026/forecast?horizon=pre_weekend')).json();
    assert.equal(saved.state, 'published');
    assert.equal(saved.run.entries.length, 22);
    assert(saved.run.entries.every(e => Math.abs(e.win_probability - 1 / 22) < 1e-14));
    record('Displayed field has actual stored equal season-opening baseline probabilities');
    await page.screenshot({ path: path.join(output, 'published.png'), fullPage: true });
    await audit('published comparison light');
    await page.emulateMedia({ colorScheme: 'dark' }); await audit('published comparison dark');
    await page.emulateMedia({ colorScheme: 'light' });
    await page.getByRole('link', { name: 'Skip to main content' }).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'main');
    await page.getByRole('button', { name: /After qualifying/ }).focus(); await page.keyboard.press('Space');
    await field.waitFor();
    record('Keyboard skip and horizon controls work on persisted forecast');
    await open('/seasons/2026/events/2026/results', 'Results and correction history');
    await page.getByText('Result revision 2', { exact: false }).waitFor();
    assert.match(await page.locator('body').innerText(), /3.091042/);
    assert.match(await page.locator('body').innerText(), /Earlier scores do not represent this result revision/);
    record('Computed log(22) score remains tied to original result; unscored correction is explicit');
    await audit('results and correction');
    await page.screenshot({ path: path.join(output, 'correction.png'), fullPage: true });
    await page.getByRole('combobox', { name: 'Season', exact: true }).selectOption('2027');
    await page.waitForURL(/\/seasons\/2027\//);
    await page.goto(base + '/seasons/2027/events/2027?horizon=post_qualifying');
    await page.getByRole('heading', { name: 'No published forecast', exact: true }).waitFor();
    assert.equal(await page.getByLabel('Comparison', { exact: true }).inputValue(), '');
    assert((await field.locator('tbody tr td:nth-child(3)').allTextContents()).every(value => value === 'Entry unavailable'));
    assert.equal(await page.getByRole('region', { name: 'Published probabilities; scroll horizontally on small screens' }).count(), 0);
    assert.doesNotMatch(await field.innerText(), /· 2026/);
    record('Season rollover binds new-season reference; unpublished comparison remains unavailable with no delta');
    await audit('unpublished horizon');
    fs.writeFileSync(path.join(faults, 'delay.flag'), 'test');
    await page.goto(base + full);
    await page.getByRole('heading', { name: 'Loading selected data', exact: true }).first().waitFor();
    assert.equal(await field.count(), 0);
    await field.waitFor(); fs.rmSync(path.join(faults, 'delay.flag'));
    record('Actual delayed HTTP response displays loading without retained rows');
    fs.writeFileSync(path.join(faults, 'outage.flag'), 'test');
    await page.reload();
    await page.getByRole('heading', { name: 'Could not load data', exact: true }).first().waitFor();
    assert.equal(await field.count(), 0);
    await audit('API outage');
    await page.screenshot({ path: path.join(output, 'outage.png'), fullPage: true });
    fs.rmSync(path.join(faults, 'outage.flag'));
    for (let attempt = 0; attempt < 6; attempt++) {
      const retry = page.getByRole('button', { name: 'Retry', exact: true }).first();
      if (await retry.count()) {
        await retry.focus(); await page.keyboard.press('Enter');
      }
      await page.waitForTimeout(200);
      if (await field.count()) break;
    }
    await field.waitFor();
    const recovered = await (await context.request.get(base + '/api/v1/seasons/2026/events/2026/forecast?horizon=pre_weekend')).json();
    assert.deepEqual(recovered, saved);
    record('Real HTTP 503 is distinct from unpublished; keyboard Retry restores identical last-good forecast');
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await open(full, 'Horizon and revision comparison'); await field.waitFor();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await audit('mobile forecast ' + width);
      await page.screenshot({ path: path.join(output, 'mobile-' + width + '.png'), fullPage: true });
      record('Full-field semantic table and reflow at ' + width);
    }
    assert.deepEqual(report.errors, []);
    assert(report.requests.every(url => new URL(url).hostname === '127.0.0.1'));
    record('All browser requests stay on loopback; no provider network or page exceptions');
    report.passed = true;
  } catch (error) {
    report.failure = String(error.stack || error);
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
    throw error;
  } finally {
    for (const name of ['delay.flag', 'outage.flag']) fs.rmSync(path.join(faults, name), { force: true });
    fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify(report, null, 2) + '\n');
    await context.tracing.stop({ path: path.join(output, 'trace.zip') });
    await browser.close();
  }
  console.log(JSON.stringify({ passed: report.passed, checks: report.checks.length, accessibility: report.accessibility.length }));
})().catch(error => { console.error(error); process.exit(1); });
