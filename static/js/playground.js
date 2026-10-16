(() => {
    const form=document.getElementById('playground-form');if(!form)return;
    const byId=id=>document.getElementById('playground-'+id);
    const definitions={
        search:{path:'search/',hint:'Search scope. Resolve a title into metadata and media links.',fields:[['q','Title','Inception'],['type','Media type','movie',['movie','tv']],['country','Country code','us'],['fields','Response fields (optional)','']]},
        results:{path:'search/results/',hint:'Search scope. Browse matching titles.',fields:[['q','Title','Inception'],['type','Media type','movie',['movie','tv']],['page','Page','1'],['year','Year (optional)',''],['genre','TMDB genre ID (optional)',''],['language','Language','en-US']]},
        details:{path:'media/',hint:'Search scope. Full details, cast, recommendations, and viewing options.',fields:[['type','Media type','movie',['movie','tv']],['id','TMDB ID','27205'],['country','Country code','US']]},
        trending:{path:'trending/',hint:'Search scope. Trending movies and shows this week.',fields:[['type','Media type','all',['all','movie','tv']]]},
        people:{path:'people/search/',hint:'Search scope. Find actors, directors, and other people.',fields:[['q','Name','Christopher Nolan']]},
        usage:{path:'usage/',hint:'Usage scope. Usage for this API key, including this request.',fields:[]},
        batch:{path:'batch/',method:'POST',hint:'Batch scope and Pro or Business plan required.',fields:[['body','JSON request body',JSON.stringify({items:[{q:'Inception',type:'movie',country:'us'},{q:'Breaking Bad',type:'tv',country:'us'}]},null,2)]]},
    };
    let controller=null,lastResponse='';
    const status=message=>{byId('status').textContent=message;};
    const selected=()=>definitions[byId('endpoint').value];
    const config=()=>{
        const definition=selected(),values=Object.fromEntries([...byId('parameters').querySelectorAll('[name]')].map(input=>[input.name,input.value.trim()]));
        let path=definition.path;
        if(byId('endpoint').value==='details'){
            if(!/^[1-9]\d*$/.test(values.id)||Number(values.id)>2147483647)throw new Error('Enter a valid positive TMDB ID.');
            path+=`${values.type}/${values.id}/`;delete values.type;delete values.id;
        }
        const url=new URL('/api/v1/'+path,window.location.origin);
        let body;
        if(definition.method==='POST'){
            try{body=JSON.parse(values.body);}catch(_){throw new Error('Enter valid JSON for the batch request.');}
            if(!body||!Array.isArray(body.items)||!body.items.length)throw new Error('Batch JSON needs a non-empty items array.');
        }else for(const [key,value] of Object.entries(values))if(value)url.searchParams.set(key,value);
        return {url:url.href,method:definition.method || 'GET',body};
    };
    const shell=value=>"'"+value.replace(/'/g,"'\"'\"'")+"'";
    const snippet=()=>{
        const {url,method,body}=config(),json=JSON.stringify(body),hasBody=body!==undefined;
        switch(byId('language').value){
            case 'python':return `import os\n${hasBody?'import json\n':''}import requests\n\nresponse = requests.${method.toLowerCase()}(\n    ${JSON.stringify(url)},\n    headers={"X-API-Key": os.environ["LINKIFY_API_KEY"]},\n${hasBody?`    json=json.loads(${JSON.stringify(json)}),\n`:''}    timeout=35,\n)\nprint(response.status_code)\nprint(response.json())`;
            case 'javascript':return `const response = await fetch(${JSON.stringify(url)}, {\n  method: ${JSON.stringify(method)},\n  headers: {\n    "X-API-Key": process.env.LINKIFY_API_KEY,${hasBody?'\n    "Content-Type": "application/json",':''}\n  },${hasBody?`\n  body: JSON.stringify(${JSON.stringify(body,null,2)}),`:''}\n});\nconsole.log(response.status);\nconsole.log(await response.json());`;
            default:return `curl --request ${method} ${shell(url)} \\\n  --header "X-API-Key: $LINKIFY_API_KEY"${hasBody?` \\\n  --header 'Content-Type: application/json' \\\n  --data ${shell(json)}`:''}`;
        }
    };
    const updateCode=()=>{try{byId('code').textContent=snippet();}catch(error){byId('code').textContent=error.message;}};
    const renderFields=()=>{
        const definition=selected();byId('hint').textContent=definition.hint;byId('parameters').replaceChildren();
        for(const [name,label,value,options] of definition.fields){
            const id='playground-param-'+name,labelNode=document.createElement('label');labelNode.htmlFor=id;labelNode.textContent=label;
            const input=document.createElement(options?'select':name==='body'?'textarea':'input');input.id=id;input.name=name;input.className='saas-input';
            if(options)for(const option of options){const item=document.createElement('option');item.value=option;item.textContent=option;input.append(item);}
            input.value=value;if(name!=='body'&&!options)input.maxLength=name==='fields'?500:200;
            input.addEventListener('input',updateCode);input.addEventListener('change',updateCode);byId('parameters').append(labelNode,input);
        }
        updateCode();
    };
    const copy=async text=>{try{await navigator.clipboard.writeText(text);status('Copied.');}catch(_){status('Clipboard unavailable. Select and copy the text below.');}};
    byId('copy-code').addEventListener('click',()=>{try{copy(snippet());}catch(error){status(error.message);}});
    byId('copy-response').addEventListener('click',()=>copy(lastResponse));
    byId('endpoint').addEventListener('change',renderFields);byId('language').addEventListener('change',updateCode);
    byId('clear-key').addEventListener('click',()=>{byId('key').value='';status('API key cleared.');});
    byId('cancel').addEventListener('click',()=>controller?.abort());
    window.addEventListener('pagehide',()=>{controller?.abort();byId('key').value='';});
    form.addEventListener('submit',async event=>{
        event.preventDefault();if(controller)return;
        let request;try{request=config();}catch(error){status(error.message);return;}
        const key=byId('key').value.trim();if(!key){status('Paste your API key first.');return;}
        controller=new AbortController();const signal=controller.signal;
        byId('run').disabled=true;byId('cancel').disabled=false;byId('copy-response').disabled=true;
        byId('response').textContent='Waiting for response...';byId('response-meta').textContent=`${request.method} ${request.url}`;byId('quota').textContent='Waiting for quota information...';status('Request running...');
        const start=performance.now(),timeout=setTimeout(()=>controller?.abort(),45000);
        try{
            const response=await fetch(request.url,{method:request.method,credentials:'same-origin',cache:'no-store',signal,headers:{Accept:'application/json','X-API-Key':key,'X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value,...(request.body?{'Content-Type':'application/json'}:{})},body:request.body?JSON.stringify(request.body):undefined});
            const text=await response.text();let data;try{data=JSON.parse(text);}catch(_){data={error:'The server returned a non-JSON response.',status:response.status};}
            lastResponse=JSON.stringify(data,null,2);byId('response').textContent=lastResponse;byId('copy-response').disabled=false;
            byId('response-meta').textContent=`HTTP ${response.status} ${response.statusText} · ${Math.round(performance.now()-start)} ms`;
            const cost=response.headers.get('X-Quota-Cost'),remaining=response.headers.get('X-Quota-Remaining'),limit=response.headers.get('X-Quota-Limit');
            byId('quota').textContent=cost!==null?`Request cost: ${cost} · Remaining today: ${remaining} · Daily limit: ${limit}`:'Quota information is unavailable for this response. Authentication, scope, and rate-limit checks may reject a request before usage is reserved.';
            status(response.ok?'Request completed.':`Request returned HTTP ${response.status}. Inspect the response for details.`);
        }catch(error){byId('response').textContent='No response received.';byId('response-meta').textContent='Request interrupted';byId('quota').textContent='Quota may have been used if the server received this request.';status(error.name==='AbortError'?'Request cancelled or timed out. It may still finish on the server.':'Network request failed. Check your connection and retry.');}
        finally{clearTimeout(timeout);controller=null;byId('run').disabled=false;byId('cancel').disabled=true;}
    });
    renderFields();
})();
