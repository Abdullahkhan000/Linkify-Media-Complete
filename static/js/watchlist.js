(() => {
    const api = '/api/v1/watchlist/';
    let favorites = false, page = 1, pages = 1, searchResults = [], recommendationResults = [], selected = null, searchVersion = 0, providerVersion = 0, collectionVersion = 0;
    const list = document.getElementById('watchlist-items');
    if (!list) return;
    const status = document.getElementById('watchlist-status');
    const searchStatus = document.getElementById('watchlist-search-status');
    const dialog = document.getElementById('watchlist-providers-dialog');
    const node = (tag, text, className) => { const item = document.createElement(tag); if (text) item.textContent = text; if (className) item.className = className; return item; };
    const request = async (path, method = 'GET', body) => {
        const response = await fetch(api + path, {method, credentials:'same-origin', cache:'no-store',
            headers:{Accept:'application/json','Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},
            body:body ? JSON.stringify(body) : undefined});
        const data = response.status === 204 ? null : await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data?.error || (response.status === 403 ? 'Your session expired. Please sign in again.' : 'This request could not be completed. Please retry.'));
        return data;
    };
    const renderSearch = () => render(document.getElementById('watchlist-results'), searchResults, true);
    const syncSearch = (item, removed = false) => {
        [...searchResults,...recommendationResults].forEach(result => { if (result.tmdb_id === item.tmdb_id && result.media_type === item.media_type) { result.saved_id = removed ? null : item.id; result.favorite = removed ? false : item.favorite; } });
        renderSearch();
        render(document.getElementById('watchlist-recommendations'),recommendationResults,true);
    };
    const action = (label, fn) => {
        const button = node('button', label, 'ghost-button'); button.type='button';
        button.addEventListener('click', async () => { button.disabled=true; status.textContent=''; try { await fn(); } catch (error) { status.textContent=error.message; } finally { button.disabled=false; } });
        return button;
    };
    const render = (target, items, search = false) => {
        target.replaceChildren();
        items.forEach(item => {
            const card = node('article', null, 'watchlist-card');
            const poster = node('div', null, 'watchlist-poster');
            if (item.poster_url) { const image=node('img'); image.src=item.poster_url; image.alt=`${item.title} poster`; image.loading='lazy'; image.addEventListener('error', () => { image.remove(); poster.textContent='No poster available'; }, {once:true}); poster.append(image); } else poster.textContent='No poster available';
            const body=node('div',null,'watchlist-card-body'); body.append(node('h3',item.title),node('small',`${item.media_type === 'tv' ? 'TV show' : 'Movie'} · ${item.release_year || 'Year unknown'}`));
            if(item.because)body.append(node('p',`Because you liked ${item.because}`,'watchlist-reason'));
            const buttons=node('div',null,'watchlist-actions');
            const id=search ? item.saved_id : item.id;
            if (!id) buttons.append(action('Save to watchlist',async () => { const saved=await request('','POST',{tmdb_id:item.tmdb_id,media_type:item.media_type}); syncSearch(saved); await load(); status.textContent=`${saved.title} saved.`; }));
            else {
                const favorite=action(item.favorite ? '★ Favorited' : '☆ Favorite',async () => { const updated=await request(`${id}/`,'PATCH',{favorite:!item.favorite}); syncSearch(updated); await load(); });
                favorite.setAttribute('aria-pressed',String(item.favorite)); buttons.append(favorite);
                buttons.append(action('Remove',async () => { await request(`${id}/`,'DELETE'); syncSearch({...item,id},true); await load(); status.textContent=`${item.title} removed. ${status.textContent}`; }));
            }
            buttons.append(action('Where to watch',async () => { selected=item; document.getElementById('watchlist-dialog-title').textContent=`Where to watch ${item.title}`; dialog.showModal(); await providers(); }));
            if (!search) {
                const form=node('form',null,'watchlist-edit');
                const field=(label,control)=>{const wrapper=node('label',label);wrapper.append(control);form.append(wrapper);};
                const state=node('select'); state.className='saas-input';
                for(const [value,label] of [['plan_to_watch','Plan to watch'],['watching','Watching'],['watched','Watched']]){const option=node('option',label);option.value=value;state.append(option);}state.value=item.status;
                field('Watch status',state);
                const rating=node('select');rating.className='saas-input';const empty=node('option','Not rated');empty.value='';rating.append(empty);
                for(let value=1;value<=10;value++){const option=node('option',`${value}/10`);option.value=value;rating.append(option);}rating.value=item.rating ?? '';field('Your rating',rating);
                const notes=node('textarea');notes.className='saas-input';notes.maxLength=1000;notes.rows=3;notes.value=item.notes || '';field('Private notes',notes);
                const save=node('button','Save progress','ghost-button');save.type='submit';form.append(save);
                form.addEventListener('submit',async event=>{event.preventDefault();save.disabled=true;try{const updated=await request(`${id}/`,'PATCH',{status:state.value,rating:rating.value ? Number(rating.value) : null,notes:notes.value});syncSearch(updated);await load();status.textContent=`${item.title}: progress saved.`;}catch(error){status.textContent=error.message;}finally{save.disabled=false;}});
                body.append(form);
            }
            body.append(buttons); card.append(poster,body); target.append(card);
        });
    };
    const load = async () => {
        const version=++collectionVersion;
        const filter=document.getElementById('watchlist-status-filter').value;
        const query=document.getElementById('watchlist-collection-query').value.trim();
        const sort=document.getElementById('watchlist-sort').value;
        const params=new URLSearchParams({page:String(page),q:query,sort});
        if(favorites)params.set('favorite','true');if(filter)params.set('status',filter);
        const data=await request('?'+params);
        if(version!==collectionVersion)return;
        page=data.page; pages=data.pages; render(list,data.results);
        document.getElementById('watchlist-all').textContent=`All saved (${data.total})`;
        document.getElementById('watchlist-favorites').textContent=`Favorites (${data.favorites})`;
        status.textContent=data.results.length ? `${data.matched} matching title${data.matched===1 ? '' : 's'}.` : filter || query ? 'No titles match your collection filters.' : favorites ? 'No favorites yet. Mark a saved title as a favorite.' : 'Your watchlist is empty. Search above to save your first movie or show.';
        document.getElementById('watchlist-page-number').textContent=`Page ${page} of ${pages}`;
        document.getElementById('watchlist-previous').disabled=page<=1;
        document.getElementById('watchlist-next').disabled=page>=pages;
    };
    const safeLoad = () => load().catch(error => { status.textContent=error.message; });
    document.getElementById('watchlist-collection-form').addEventListener('submit',event=>{event.preventDefault();page=1;safeLoad();});
    document.getElementById('watchlist-sort').addEventListener('change',()=>{page=1;safeLoad();});
    document.getElementById('watchlist-status-filter').addEventListener('change',()=>{page=1;safeLoad();});
    document.getElementById('watchlist-search-form').addEventListener('submit',async event => {
        event.preventDefault(); const form=event.currentTarget, version=++searchVersion;
        const params=new URLSearchParams(new FormData(form)); params.delete('csrfmiddlewaretoken');
        searchStatus.textContent='Searching...';
        try { const data=await request('search/?'+params); if (version!==searchVersion) return; searchResults=data.results; renderSearch(); searchStatus.textContent=data.results.length ? (data._cache ? 'Showing cached results while the provider is unavailable.' : `${data.results.length} matching titles`) : 'No matching titles. Try another title or media type.'; }
        catch(error) { if (version===searchVersion) searchStatus.textContent=error.message; }
    });
    for (const [id,value] of [['watchlist-all',false],['watchlist-favorites',true]]) document.getElementById(id).addEventListener('click',()=>{
        favorites=value; page=1; document.getElementById('watchlist-all').setAttribute('aria-pressed',String(!value)); document.getElementById('watchlist-favorites').setAttribute('aria-pressed',String(value)); safeLoad();
    });
    document.getElementById('watchlist-previous').addEventListener('click',()=>{if(page>1){page--;safeLoad();}});
    document.getElementById('watchlist-next').addEventListener('click',()=>{if(page<pages){page++;safeLoad();}});
    const providers = async () => {
        const target=document.getElementById('watchlist-providers'), version=++providerVersion;
        target.textContent='Checking availability...';
        const country=document.getElementById('watchlist-country').value.trim().toUpperCase();
        if(!/^[A-Z]{2}$/.test(country)){target.textContent='Enter a two-letter country code.';return;}
        try {
            const data=await request(`providers/${selected.media_type}/${selected.tmdb_id}/?country=${country}`);
            if(version!==providerVersion)return;
            target.replaceChildren(); let found=false;
            for(const [key,label] of [['flatrate','Stream'],['free','Free'],['ads','With ads'],['rent','Rent'],['buy','Buy']]){
                const options=data.providers[key] || [];
                if(options.length){found=true;target.append(node('h3',label),node('p',options.map(provider=>provider.provider_name).join(', ')));}
            }
            if(!found)target.append(node('p',`No streaming information is available for ${country}. Try another country.`));
            if(data._cache)target.append(node('p','Showing cached availability while the provider is unavailable.'));
            if(data.providers.link){try{const url=new URL(data.providers.link);if(url.protocol==='https:'&&(url.hostname==='www.themoviedb.org'||url.hostname==='themoviedb.org')){const link=node('a','View viewing options on TMDB');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';target.append(link);}}catch(_){}}
        }catch(error){if(version===providerVersion)target.textContent=error.message;}
    };
    document.getElementById('watchlist-country-form').addEventListener('submit',event=>{event.preventDefault();providers();});
    document.getElementById('watchlist-dialog-close').addEventListener('click',()=>dialog.close());
    const recommendations=async()=>{
        const button=document.getElementById('watchlist-refresh-recommendations'),message=document.getElementById('watchlist-recommendations-status');
        button.disabled=true;message.textContent='Finding recommendations...';
        try{const data=await request('recommendations/');recommendationResults=data.results;render(document.getElementById('watchlist-recommendations'),recommendationResults,true);message.textContent=data.message || (data.partial ? 'Some suggestions are unavailable. Showing available recommendations.' : data.stale ? 'Showing cached recommendations while the provider is unavailable.' : 'Save a suggestion or check where to watch.');}
        catch(error){message.textContent=error.message;}
        finally{button.disabled=false;}
    };
    document.getElementById('watchlist-refresh-recommendations').addEventListener('click',recommendations);
    recommendations();
    safeLoad();
})();
