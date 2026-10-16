(() => {
    const key = 'linkify_support_conversation';
    let conversationId = null;
    let fresh = false;
    let busy = false;
    let generation = 0;
    try { conversationId = sessionStorage.getItem(key); fresh = conversationId === 'new'; if (fresh) conversationId = null; } catch (_) {}
    const widget = document.getElementById('support-messages');
    const page = document.getElementById('bot-messages');
    const views = [widget, page].filter(Boolean);
    const status = document.getElementById('bot-status');
    const error = document.getElementById('support-error');
    const escalation = document.getElementById('escalation-panel');
    const result = document.getElementById('escalation-result');
    const forms = [document.getElementById('support-chat-form'), document.getElementById('bot-form')].filter(Boolean);
    const ticketForm = document.getElementById('escalation-form');
    const saveId = id => {
        conversationId = id;
        if (id) fresh = false;
        try { if (id) sessionStorage.setItem(key, id); else sessionStorage.removeItem(key); } catch (_) {}
    };
    const bubble = (container, text, role, source) => {
        const item = document.createElement('div');
        item.className = `support-bot-message ${role === 'user' ? 'user' : 'bot'}`;
        item.style.whiteSpace = 'pre-wrap';
        item.textContent = text;
        if (source && role !== 'user') {
            const label = document.createElement('small');
            label.style.display = 'block';
            label.textContent = source === 'ai' ? 'AI assistant' : source === 'human' ? 'Support team' : 'Built-in support';
            item.append(label);
        }
        container.append(item);
        container.scrollTop = container.scrollHeight;
        return item;
    };
    const showError = message => {
        if (error) error.textContent = message;
        if (status) status.textContent = message ? 'Please retry' : 'Ready';
        if (page && message) bubble(page, message, 'assistant');
    };
    const setBusy = value => {
        busy = value;
        forms.forEach(form => form.querySelectorAll('button,textarea').forEach(item => { item.disabled = value; }));
        document.querySelectorAll('[data-support-question],#support-new,#bot-new,#bot-refresh').forEach(item => { item.disabled = value; });
        if (status) status.textContent = value ? 'Replying...' : 'Ready';
    };
    const request = async (url, body) => {
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 45000);
        try {
            const response = await fetch(url, {
                method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
                headers: {Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': token},
                body: body ? JSON.stringify(body) : undefined, signal: controller.signal,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                const failure = new Error(data.error || `Support returned HTTP ${response.status}. Please retry.`);
                failure.status = response.status;
                throw failure;
            }
            return data;
        } catch (failure) {
            if (failure.name === 'AbortError') throw new Error('Support took too long to reply. Refresh the chat before retrying.');
            throw failure;
        } finally { clearTimeout(timer); }
    };
    const render = data => {
        if (data.conversation_id) saveId(data.conversation_id);
        views.forEach(container => {
            container.replaceChildren();
            if (!data.messages?.length) bubble(container, 'How can I help with Linkify Media?', 'assistant');
            (data.messages || []).forEach(item => bubble(container, item.content, item.role, item.source));
        });
        if (data.status === 'escalated') escalation?.classList.remove('hidden');
        if (result) result.textContent = data.ticket ? `Ticket #${data.ticket.id}: ${data.ticket.status.replace('_', ' ')}` : '';
        const submit = ticketForm?.querySelector('button[type=submit]');
        if (submit) submit.disabled = !!data.ticket && data.ticket.status !== 'resolved';
    };
    const restore = async (recoverSession = true) => {
        if (fresh && !conversationId) { render({messages: []}); return; }
        const version = generation;
        try {
            const url = '/api/support/chat/' + (conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : '');
            const data = await request(url);
            if (version === generation) render(data);
        } catch (failure) {
            if ([403, 404].includes(failure.status)) {
                saveId(null);
                if (recoverSession) return restore(false);
            } else showError(failure.message);
        }
    };
    const send = async text => {
        const message = text.trim();
        if (!message || busy) return false;
        if (message.length > 4000) { showError('Use at most 4000 characters.'); return false; }
        generation++;
        showError('');
        setBusy(true);
        const userBubbles = views.map(container => bubble(container, message, 'user'));
        const pending = views.map(container => bubble(container, 'Replying...', 'assistant'));
        try {
            const data = await request('/api/support/chat/', {message, conversation_id: conversationId});
            saveId(data.conversation_id);
            userBubbles.forEach(item => { item.textContent = data.user_message || message; });
            pending.forEach(item => item.remove());
            views.forEach(container => bubble(container, data.message, 'assistant', data.source));
            if (data.should_escalate) escalation?.classList.remove('hidden');
            return true;
        } catch (failure) {
            pending.forEach(item => item.remove());
            userBubbles.forEach(item => item.remove());
            if ([403, 404].includes(failure.status)) saveId(null);
            showError(failure.message);
            return false;
        } finally { setBusy(false); }
    };
    forms.forEach(form => {
        const input = form.querySelector('textarea');
        form.addEventListener('submit', async event => {
            event.preventDefault();
            if (await send(input.value)) input.value = '';
            input.focus();
        });
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
        });
    });
    document.querySelectorAll('[data-support-question]').forEach(button => button.addEventListener('click', () => send(button.dataset.supportQuestion)));
    const panel = document.getElementById('support-panel');
    const toggle = document.getElementById('support-toggle');
    const open = visible => {
        panel?.classList.toggle('hidden', !visible);
        toggle?.setAttribute('aria-expanded', String(visible));
        if (visible && !busy) { restore(); document.getElementById('support-chat-input')?.focus(); }
    };
    toggle?.addEventListener('click', () => open(panel.classList.contains('hidden')));
    document.getElementById('support-close')?.addEventListener('click', () => open(false));
    document.addEventListener('keydown', event => { if (event.key === 'Escape') open(false); });
    const newChat = () => {
        if (busy) return;
        generation++;
        saveId(null);
        fresh = true;
        try { sessionStorage.setItem(key, 'new'); } catch (_) {}
        render({messages: []});
        escalation?.classList.add('hidden');
        showError('');
    };
    document.getElementById('support-new')?.addEventListener('click', newChat);
    document.getElementById('bot-new')?.addEventListener('click', newChat);
    document.getElementById('bot-refresh')?.addEventListener('click', () => { if (!busy) restore(); });
    document.getElementById('show-escalation')?.addEventListener('click', () => escalation?.classList.toggle('hidden'));
    ticketForm?.addEventListener('submit', async event => {
        event.preventDefault();
        if (!conversationId) { result.textContent = 'Send a chat message first so the ticket includes your conversation.'; return; }
        const submit = ticketForm.querySelector('button[type=submit]');
        if (submit.disabled) return;
        submit.disabled = true;
        result.textContent = 'Creating ticket...';
        try {
            const data = await request('/api/support/ticket/', {...Object.fromEntries(new FormData(ticketForm)), conversation_id: conversationId});
            result.textContent = `Ticket #${data.ticket_id} recorded for the support team.`;
        } catch (failure) { result.textContent = failure.message; submit.disabled = false; }
    });
    if (page) restore();
})();
