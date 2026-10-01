(() => {
  const csrfToken = () => {
    const cookie = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) :
      document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  };

  document.querySelectorAll('[data-public-menu-toggle]').forEach((button) => {
    const menu = document.getElementById(button.getAttribute('aria-controls'));
    if (!menu) return;
    button.addEventListener('click', () => {
      const open = menu.hidden;
      menu.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
      button.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });
  });

  document.querySelectorAll('[data-sidebar-toggle]').forEach((button) => {
    const backdrop = document.querySelector('[data-sidebar-backdrop]');
    if (!backdrop) return;
    const close = () => { backdrop.hidden = true; button.setAttribute('aria-expanded', 'false'); };
    button.addEventListener('click', () => { backdrop.hidden = false; button.setAttribute('aria-expanded', 'true'); });
    backdrop.querySelector('[data-sidebar-close]')?.addEventListener('click', close);
    backdrop.addEventListener('click', (event) => { if (event.target === backdrop) close(); });
  });

  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.passwordToggle);
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      button.setAttribute('aria-label', input.type === 'password' ? 'Show password' : 'Hide password');
    });
  });

  const supportRoot = document.querySelector('[data-support-root]');
  if (supportRoot) {
    const panel = supportRoot.querySelector('[data-support-panel]');
    const toggle = supportRoot.querySelector('[data-support-toggle]');
    const close = supportRoot.querySelector('[data-support-close]');
    const form = supportRoot.querySelector('[data-support-form]');
    const messages = supportRoot.querySelector('[data-support-messages]');
    const error = supportRoot.querySelector('[data-support-error]');
    const sessionKey = 'linkify-support-conversation';
    const openPanel = (open) => {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (open) panel.querySelector('input[name=message]')?.focus();
    };
    toggle?.addEventListener('click', () => openPanel(panel.hidden));
    close?.addEventListener('click', () => openPanel(false));
    const addMessage = (text, who) => {
      const item = document.createElement('div');
      item.className = `support-message ${who}`;
      item.textContent = text;
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
      return item;
    };
    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = form.elements.message;
      const message = input.value.trim();
      if (!message) return;
      error.textContent = '';
      addMessage(message, 'user');
      input.value = '';
      const pending = addMessage('Thinking…', 'assistant pending');
      const headers = { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' };
      const token = csrfToken();
      if (token) headers['X-CSRFToken'] = token;
      let body = { message };
      try { body.conversation_id = sessionStorage.getItem(sessionKey); } catch (_) { /* storage may be disabled */ }
      try {
        const response = await fetch('/api/support/chat/', { method: 'POST', headers, body: JSON.stringify(body), cache: 'no-store' });
        const data = await response.json();
        pending.remove();
        if (!response.ok) throw new Error(data.error || 'The support request could not be completed.');
        try { sessionStorage.setItem(sessionKey, data.conversation_id); } catch (_) { /* keep this response only */ }
        addMessage(data.message || 'The support service returned an empty response.', 'assistant');
      } catch (exception) {
        pending.remove();
        error.textContent = exception.message || 'Could not reach the support service.';
      }
    });
  }

  const supportPage = document.querySelector('.support-chat-panel');
  if (supportPage) {
    const form = document.getElementById('support-chat-form');
    const input = document.getElementById('support-chat-input');
    const messages = document.getElementById('support-messages');
    const send = document.getElementById('support-chat-send');
    const ticketForm = document.getElementById('support-ticket-form');
    const ticketResult = document.getElementById('support-ticket-result');
    const sessionKey = 'linkify-support-conversation';
    const addMessage = (text, who) => {
      const item = document.createElement('div');
      item.className = `chat-bubble ${who}`;
      item.textContent = text;
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
      return item;
    };
    const headers = () => {
      const value = { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' };
      const token = csrfToken(); if (token) value['X-CSRFToken'] = token;
      return value;
    };
    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const message = input.value.trim(); if (!message) return;
      addMessage(message, 'user'); input.value = ''; send.disabled = true;
      const pending = addMessage('Thinking…', 'assistant pending');
      const payload = { message };
      try { payload.conversation_id = sessionStorage.getItem(sessionKey); } catch (_) { /* session storage optional */ }
      try {
        const response = await fetch(supportPage.dataset.chatUrl, { method: 'POST', headers: headers(), body: JSON.stringify(payload), cache: 'no-store' });
        const data = await response.json(); pending.remove();
        if (!response.ok) throw new Error(data.error || 'Support is temporarily unavailable.');
        try { sessionStorage.setItem(sessionKey, data.conversation_id); } catch (_) { /* this session only */ }
        addMessage(data.message || 'The support service returned an empty response.', 'assistant');
      } catch (exception) { pending.remove(); addMessage(exception.message || 'Could not reach the support service.', 'assistant error'); }
      finally { send.disabled = false; input.focus(); }
    });
    ticketForm?.addEventListener('submit', async (event) => {
      event.preventDefault(); ticketResult.textContent = '';
      let conversationId = null; try { conversationId = sessionStorage.getItem(sessionKey); } catch (_) { /* no storage */ }
      if (!conversationId) { ticketResult.textContent = 'Send at least one chat message before creating a ticket from the conversation.'; return; }
      const fields = Object.fromEntries(new FormData(ticketForm));
      fields.conversation_id = conversationId;
      try {
        const response = await fetch(supportPage.dataset.ticketUrl, { method: 'POST', headers: headers(), body: JSON.stringify(fields), cache: 'no-store' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not create ticket.');
        ticketResult.textContent = `Ticket ${data.ticket_id} was recorded.`;
      } catch (exception) { ticketResult.textContent = exception.message || 'Could not create ticket.'; }
    });
  }
})();
