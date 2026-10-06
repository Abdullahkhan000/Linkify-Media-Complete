(() => {
    if ('serviceWorker' in navigator && window.isSecureContext) {
        navigator.serviceWorker.register('/service-worker.js', {scope: '/'}).catch(() => {});
    }
    const notice = document.createElement('aside');
    notice.className = 'connection-notice';
    notice.hidden = true;
    notice.setAttribute('role', 'status');
    const text = document.createElement('span');
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.textContent = 'Dismiss';
    dismiss.addEventListener('click', () => { notice.hidden = true; });
    notice.append(text, dismiss);
    document.body.append(notice);
    let timer;
    const update = () => {
        clearTimeout(timer);
        notice.hidden = false;
        if (!navigator.onLine) {
            text.textContent = 'NETWORK · Connection lost. Reconnect before trying again.';
        } else {
            text.textContent = 'Connection restored. You can continue.';
            timer = setTimeout(() => { notice.hidden = true; }, 3000);
        }
    };
    window.addEventListener('offline', update);
    window.addEventListener('online', update);
    if (!navigator.onLine) update();
})();
