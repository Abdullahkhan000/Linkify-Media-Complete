// Run against the isolated local verification database, never production.
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path=require('node:path');
const os=require('node:os');
const {execFileSync}=require('node:child_process');
const {chromium}=require(process.env.SUPPORT_PLAYWRIGHT_PATH || 'playwright');

(async()=>{
    const browser=await chromium.launch({channel:'chrome',headless:true});
    try{
        const context=await browser.newContext({viewport:{width:1280,height:900},permissions:['clipboard-read','clipboard-write']});
        const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
        const base=process.env.SUPPORT_TEST_BASE_URL || 'http://127.0.0.1:8767';
        await page.goto(base+'/accounts/signup/');
        const username='playground_'+crypto.randomBytes(5).toString('hex'),password='Playground-'+crypto.randomBytes(16).toString('hex')+'!';
        await page.locator('#id_username').fill(username);await page.locator('#id_email').fill(username+'@example.com');
        await page.locator('#id_password1').fill(password);await page.locator('#id_password2').fill(password);await page.locator('[name=terms]').check();
        await Promise.all([page.waitForURL('**/dashboard/'),page.locator('form[action="/accounts/signup/"] button[type=submit]').click()]);
        await page.getByRole('link',{name:'Open API Playground',exact:true}).click();
        const keyResponse=await page.evaluate(async()=>{
            const response=await fetch('/api/keys/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({name:'Browser playground test',scopes:['search','usage']})});
            return {status:response.status,data:await response.json()};
        });
        assert.equal(keyResponse.status,201);const secret=keyResponse.data.key;
        await page.locator('#playground-key').fill(secret);
        const run=async()=>{const waiting=page.waitForResponse(response=>response.url().startsWith(base+'/api/v1/'));await page.locator('#playground-run').click();const response=await waiting;await page.waitForFunction(()=>!document.getElementById('playground-run').disabled);return response;};
        assert.equal((await run()).status(),200);
        assert(JSON.parse(await page.locator('#playground-response').textContent())['Official Title']);
        assert((await page.locator('#playground-quota').textContent()).includes('Remaining today: 99'));
        console.log('PASS live TMDB search, HTTP status, JSON, timing, and quota headers');
        for(const endpoint of ['search','results','details','trending','people','usage','batch']){
            await page.locator('#playground-endpoint').selectOption(endpoint);
            for(const language of ['curl','python','javascript']){
                await page.locator('#playground-language').selectOption(language);
                const code=await page.locator('#playground-code').textContent();assert(code.includes('LINKIFY_API_KEY'));assert(!code.includes(secret));
                if(language==='python')execFileSync(path.join(process.cwd(),'.venv','Scripts','python.exe'),['-c','import sys; compile(sys.stdin.read(), "snippet", "exec")'],{input:code});
                if(language==='javascript')new (Object.getPrototypeOf(async function(){}).constructor)(code);
            }
        }
        await page.locator('#playground-endpoint').selectOption('usage');
        await page.locator('#playground-language').selectOption('javascript');
        const javascript=await page.locator('#playground-code').textContent(),messages=[];
        await new (Object.getPrototypeOf(async function(){}).constructor)('process','console',javascript)({env:{LINKIFY_API_KEY:secret}},{log:value=>messages.push(value)});
        assert.equal(messages[0],200);assert(messages[1].today_usage>=2);
        await page.locator('#playground-language').selectOption('python');
        const python=await page.locator('#playground-code').textContent();
        const pythonResult=execFileSync(path.join(process.cwd(),'.venv','Scripts','python.exe'),['-c',python],{env:{...process.env,LINKIFY_API_KEY:secret},encoding:'utf8'});
        assert(pythonResult.startsWith('200'));
        await page.locator('#playground-copy-code').click();
        assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replace(/\r\n/g,'\n'),python);
        console.log('PASS all endpoint snippets compile; copied Python and JavaScript snippets execute against the API');
        await page.locator('#playground-key').fill('invalid-test-key');assert.equal((await run()).status(),401);
        assert((await page.locator('#playground-response-meta').textContent()).includes('401'));
        await page.locator('#playground-key').fill(secret);
        await page.locator('#playground-endpoint').selectOption('batch');
        await page.locator('#playground-param-body').fill('{bad json');
        await page.locator('#playground-run').click();assert((await page.locator('#playground-status').textContent()).includes('valid JSON'));
        await page.locator('#playground-endpoint').selectOption('usage');assert.equal((await run()).status(),200);
        await page.locator('#playground-copy-response').click();
        assert.equal(JSON.parse(await page.evaluate(()=>navigator.clipboard.readText())).tier,'free');
        const storage=await page.evaluate(()=>({local:JSON.stringify(localStorage),session:JSON.stringify(sessionStorage)}));
        assert(!storage.local.includes(secret));assert(!storage.session.includes(secret));
        await page.setViewportSize({width:390,height:844});
        await page.waitForTimeout(250);
        const overflow=await page.evaluate(()=>[...document.querySelectorAll('main *')].filter(item=>item.getBoundingClientRect().right>innerWidth+1).map(item=>({tag:item.tagName,id:item.id,class:item.className,right:item.getBoundingClientRect().right})).slice(0,12));
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),JSON.stringify(overflow));
        await page.screenshot({path:path.join(os.tmpdir(),'linkify-support-browser','playground-mobile.png')});
        await page.locator('#playground-clear-key').click();assert.equal(await page.locator('#playground-key').inputValue(),'');
        await page.locator('#playground-key').fill(secret);await page.reload();assert.equal(await page.locator('#playground-key').inputValue(),'');
        assert.deepEqual(errors,[]);
        console.log('PASS invalid credentials and JSON errors; clipboard; mobile layout; key stays out of storage and clears on reload');
    }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
