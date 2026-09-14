import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';

let browser;
const root = new URL('../../services/frontend/src/', import.meta.url);
before(async () => {
  browser = await chromium.launch({ executablePath: process.env.LOGPILOT_CHROME_PATH ||
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
});
after(async () => { await browser?.close(); });

async function pageFor(t, { history = [], alerts = [], answer = {}, status = 200 } = {}) {
  const context = await browser.newContext({ serviceWorkers: 'block' });
  t.after(() => context.close());
  const requests = [];
  // Every browser request is fulfilled locally; there is no running API, data
  // mount, remote CDN, font request or live network dependency in these tests.
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    requests.push(url.href);
    if (url.host === 'localhost:8000') {
      let body = {};
      if (url.pathname === '/health') body = { status: 'ok', llm: { status: 'ready' } };
      if (url.pathname === '/history') body = history;
      if (url.pathname === '/alerts') body = alerts;
      if (url.pathname === '/metrics') body = { history: [], total_runs: 0 };
      if (url.pathname === '/query') body = answer;
      return route.fulfill({ status: url.pathname === '/query' ? status : 200,
        contentType: 'application/json', body: JSON.stringify(body) });
    }
    if (url.host === 'logpilot.test') {
      const name = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      if (!name.includes('..')) {
        try {
          const body = await readFile(new URL(name, root));
          const contentType = name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html';
          return route.fulfill({ body, contentType });
        } catch {}
      }
    }
    return route.fulfill({ status: 404, body: '' });
  });
  const page = await context.newPage();
  await page.goto('http://logpilot.test/');
  await page.waitForFunction(() => document.querySelector('#messages').textContent.trim().length > 0);
  return { page, requests };
}

test('user input and stored history stay literal', async t => {
  const attack = '<img src=x onerror="window.__xss=1">';
  const { page } = await pageFor(t, { history: [{ role: 'user', content: attack }], answer: { answer: 'Done' } });
  assert.match(await page.locator('#messages').innerText(), /<img/);
  await page.locator('#user-input').fill(attack);
  await page.locator('#chat-form').evaluate(form => form.requestSubmit());
  await page.waitForFunction(() => document.querySelector('#messages').textContent.includes('Done'));
  assert.equal(await page.locator('#messages img').count(), 0);
  assert.equal(await page.evaluate(() => window.__xss), undefined);
});

test('Markdown remains useful while hostile HTML and links are removed', async t => {
  const markdown = '**Useful**\n\n```sql\nSELECT * FROM logs WHERE body = \'<tag>\';\n```\n\n' +
    '<img src=x onerror="window.__xss=1"> [bad](javascript:alert(1))';
  const { page } = await pageFor(t, { answer: { answer: markdown, sql: '<script>unsafe()</script>', context: '<log>evidence</log>' } });
  await page.locator('#user-input').fill('question');
  await page.locator('#chat-form').evaluate(form => form.requestSubmit());
  await page.waitForFunction(() => document.querySelector('#messages strong') !== null);
  assert.equal(await page.locator('#messages strong').innerText(), 'Useful');
  assert.match(await page.locator('#messages').textContent(), /<log>evidence<\/log>/);
  assert.match(await page.locator('#messages code').first().innerText(), /<tag>/);
  assert.equal(await page.locator('#messages img, #messages script, #messages [onerror], #messages a[href^="javascript:"]').count(), 0);
  assert.equal(await page.evaluate(() => window.__xss), undefined);
});

test('alerts cannot inject markup or executable dismissal IDs', async t => {
  const id = "');window.__xss=1;//";
  const { page, requests } = await pageFor(t, { alerts: [{ id, service: '<img src=x onerror="window.__xss=1">',
    message: '<b>literal</b>', analysis: '<svg onload="window.__xss=1">', timestamp: '2026-09-13' }] });
  await page.evaluate(() => switchView('alerts'));
  await page.waitForFunction(() => document.querySelector('#alerts-list button') !== null);
  assert.equal(await page.locator('#alerts-list img, #alerts-list svg, #alerts-list [onclick]').count(), 0);
  await page.locator('#alerts-list button').click();
  assert.equal(await page.evaluate(() => window.__xss), undefined);
  assert.ok(requests.some(url => url.endsWith('/alerts/' + encodeURIComponent(id) + '/read')));
});

test('deadline errors display the actual safe message', async t => {
  const { page } = await pageFor(t, { status: 504, answer: { detail: { code: 'deadline_exceeded', message: 'The request deadline was exceeded.' } } });
  await page.locator('#user-input').fill('question');
  await page.locator('#chat-form').evaluate(form => form.requestSubmit());
  await page.waitForFunction(() => document.querySelector('#messages').textContent.includes('deadline'));
  assert.match(await page.locator('#messages').textContent(), /request deadline was exceeded/);
});


test('missing evaluation metrics display unavailable instead of zero', async t => {
  const { page } = await pageFor(t);
  await page.evaluate(() => switchView('performance'));
  await page.waitForFunction(() => document.querySelector('#metric-pass-rate').textContent === 'Unavailable');
  assert.equal(await page.locator('#metric-latency').innerText(), 'Unavailable');
});
