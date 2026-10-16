// Run against an isolated local server, never a production support inbox.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.SUPPORT_PLAYWRIGHT_PATH || 'playwright');

(async () => {
    const browser = await chromium.launch({ channel: 'chrome', headless: true });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const base = process.env.SUPPORT_TEST_BASE_URL || 'http://127.0.0.1:8767';
        await page.goto(base + '/support/');
        await page.waitForFunction(() => document.getElementById('bot-messages').textContent.includes('How can I help'));
        await page.locator('#support-toggle').click();
        const send = async (input, button, message) => {
            await page.locator(input).fill(message);
            const waiting = page.waitForResponse(response => response.url().endsWith('/api/support/chat/') && response.request().method() === 'POST');
            await page.locator(button).click();
            const response = await waiting;
            assert.equal(response.status(), 200);
            const data = await response.json();
            await page.waitForFunction(() => !document.querySelector('#support-chat-form button[type=submit]').disabled);
            return data;
        };
        const first = await send('#support-chat-input', '#support-chat-form button[type=submit]', 'How do I create an API key?');
        assert.match(await page.locator('#support-messages').innerText(), /Create key/);
        assert.match(await page.locator('#bot-messages').innerText(), /Create key/);
        console.log('PASS widget sends real chat; full-page chat stays synchronized');
        await page.reload();
        await page.waitForFunction(() => document.getElementById('bot-messages').textContent.includes('Create key'));
        console.log('PASS conversation restored after reload');
        await page.locator('#show-escalation').click();
        await page.locator('#escalation-form [name=name]').fill('Browser Test');
        await page.locator('#escalation-form [name=email]').fill('browser-test@example.com');
        const ticketWaiting = page.waitForResponse(response => response.url().endsWith('/api/support/ticket/') && response.request().method() === 'POST');
        await page.locator('#escalation-form button[type=submit]').click();
        const ticket = await ticketWaiting;
        assert.equal(ticket.status(), 201);
        await page.waitForFunction(() => document.getElementById('escalation-result').textContent.includes('recorded'));
        console.log('PASS human-support ticket created from the real conversation');
        await page.locator('#bot-new').click();
        const second = await send('#bot-input', '#bot-submit', 'How do I change my profile photo?');
        assert.notEqual(first.conversation_id, second.conversation_id);
        assert.match(await page.locator('#bot-messages').innerText(), /\/profile\//);
        console.log('PASS new chat creates a separate conversation and answers profile questions');
        await page.route('**/api/support/chat/', async route => {
            if (route.request().method() === 'POST') return route.fulfill({status: 429, contentType: 'application/json', body: JSON.stringify({error:'Test limit reached'})});
            return route.continue();
        });
        await page.locator('#bot-input').fill('A retryable message');
        await page.locator('#bot-submit').click();
        await page.waitForFunction(() => document.getElementById('bot-messages').textContent.includes('Test limit reached'));
        assert.equal(await page.locator('#bot-input').inputValue(), 'A retryable message');
        await page.unroute('**/api/support/chat/');
        await send('#bot-input', '#bot-submit', '<img src=x onerror=alert(1)>');
        assert.equal(await page.locator('#bot-messages img').count(), 0);
        assert.deepEqual(errors, []);
        console.log('PASS request failures retain the draft; messages cannot inject HTML; no browser JS errors');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
