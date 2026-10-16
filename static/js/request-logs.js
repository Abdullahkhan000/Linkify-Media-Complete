document.addEventListener('click',async event=>{
    const button=event.target.closest('.request-id-copy');if(!button)return;
    const status=document.getElementById('request-logs-copy-status');
    try{await navigator.clipboard.writeText(button.dataset.requestId);status.textContent='Request ID copied.';}
    catch(_){status.textContent='Clipboard unavailable. Select and copy the request ID from the table.';}
});
