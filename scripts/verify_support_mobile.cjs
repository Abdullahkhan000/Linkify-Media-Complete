const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const { chromium } = require(process.env.SUPPORT_PLAYWRIGHT_PATH || 'playwright');

(async () => {
    const browser = await chromium.launch({channel: 'chrome', headless: true});
    try {
        for (const viewport of [{width:320,height:568},{width:390,height:844},{width:430,height:932},{width:844,height:390}]) {
            const context = await browser.newContext({viewport, isMobile:true, hasTouch:true, deviceScaleFactor:1});
            const page = await context.newPage();
            const failures = [];
            page.on('pageerror', error => failures.push(error.message));
            await page.goto((process.env.SUPPORT_TEST_BASE_URL || 'http://127.0.0.1:8767') + '/');
            const button = page.locator('#support-toggle');
            await button.waitFor({state:'visible', timeout:10000}).catch(async error => {
                console.log(await button.evaluate(node => {
                    const result=[];
                    for (let current=node; current; current=current.parentElement) {
                        const style=getComputedStyle(current);
                        result.push({tag:current.tagName,id:current.id,display:style.display,visibility:style.visibility,hidden:current.hidden,style:current.getAttribute('style')});
                    }
                    return result;
                }));
                throw error;
            });
            const initial = await button.boundingBox();
            assert(initial.x >= 0 && initial.y >= 0 && initial.x + initial.width <= viewport.width && initial.y + initial.height <= viewport.height);
            assert(initial.height >= 44);
            assert.match(await button.innerText(), /Support/);
            await button.tap();
            await page.locator('#support-panel').waitFor({state:'visible'});
            const panel = await page.locator('#support-panel').boundingBox();
            assert(panel.x >= 0 && panel.y >= 0, `panel outside viewport: ${JSON.stringify(panel)}`);
            assert(panel.x + panel.width <= viewport.width + 1 && panel.y + panel.height <= viewport.height + 1);
            const input = page.locator('#support-chat-input');
            assert.equal(await input.evaluate(node => getComputedStyle(node).fontSize), '16px');
            await input.fill('How do I authenticate?');
            const waiting = page.waitForResponse(response => response.url().endsWith('/api/support/chat/') && response.request().method() === 'POST');
            await page.locator('#support-chat-form button[type=submit]').tap();
            assert.equal((await waiting).status(), 200);
            await page.waitForFunction(() => document.getElementById('support-messages').textContent.includes('X-API-Key'));
            if (viewport.width === 390) {
                await page.setViewportSize({width:390,height:420});
                await input.focus();
                const compact = await page.locator('#support-panel').boundingBox();
                assert(compact.y >= 0 && compact.y + compact.height <= 421);
                const send = await page.locator('#support-chat-form button[type=submit]').boundingBox();
                assert(send.y >= 0 && send.y + send.height <= 421);
                await page.setViewportSize(viewport);
                await page.screenshot({path:path.join(os.tmpdir(), 'linkify-support-browser', 'mobile-support.png')});
                console.log('PASS compact viewport keeps mobile composer visible');
            }
            await page.locator('#support-close').tap();
            assert.equal(await page.locator('#support-panel').isVisible(), false);
            assert.equal(await button.isVisible(), true);
            assert.deepEqual(failures, []);
            console.log(`PASS mobile ${viewport.width}x${viewport.height}: visible launcher, fitting panel, real chat, close/reopen access`);
            await context.close();
        }
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
