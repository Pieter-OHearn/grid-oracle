/* Require the named browser defect to fail the actual horizon transition. */
const { spawnSync } = require('node:child_process');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const output = path.resolve(process.env.WP14_BROWSER_MUTATION_OUTPUT || '/tmp/wp14-evidence/browser-mutations');
fs.mkdirSync(output, { recursive: true });
const report = { passed: false, mutation: 'horizon-keyboard', killed: false };
try {
  const result = spawnSync(process.execPath, [path.join(__dirname, 'wp14_browser.cjs')], {
    env: { ...process.env, WP14_BROWSER_MUTANT: 'horizon-keyboard', WP14_BROWSER_OUTPUT: output },
    encoding: 'utf8', timeout: 120000,
  });
  fs.writeFileSync(path.join(output, 'mutation.log'), (result.stdout || '') + (result.stderr || ''));
  assert.ifError(result.error);
  const browser = JSON.parse(fs.readFileSync(path.join(output, 'browser.json'), 'utf8'));
  report.killed = result.status === 1 && !browser.passed && browser.checks.length === 2 && browser.failure.includes('Keyboard horizon activation failed');
  assert(report.killed, 'keyboard mutation survived or unrelated browser failure');
  report.passed = true;
} finally {
  fs.writeFileSync(path.join(output, 'mutations.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify(report));
