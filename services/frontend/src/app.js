const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const messagesContainer = document.getElementById('messages');
const typingIndicator = document.getElementById('typing');

// Auto-focus input
userInput.focus();

function clearChat() {
    messagesContainer.innerHTML = '';
    addMessage('ai', `
        <p>Chat cleared. How can I help you now?</p>
    `);
}

function addMessage(role, htmlContent) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const avatar = role === 'ai' ? '🤖' : '👤';

    div.innerHTML = `
        <div class="avatar">${avatar}</div>
        <div class="content">${htmlContent}</div>
    `;

    messagesContainer.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTyping(show) {
    if (show) {
        typingIndicator.classList.remove('hidden');
    } else {
        typingIndicator.classList.add('hidden');
    }
}

async function handleSubmit(e) {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    // 1. Add User Message
    addMessage('user', `<p>${query}</p>`);
    userInput.value = '';
    showTyping(true);

    try {
        // 2. Call API
        // Note: In Docker, we use relative path or proxy. 
        // For local dev, we assume localhost:8000 is accessible via CORS or Proxy.
        // Since we are running in browser, we need to hit the API exposed port.
        const response = await fetch('http://localhost:8000/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query })
        });

        const data = await response.json();
        showTyping(false);

        // 3. Format Response
        let responseHtml = marked.parse(data.answer);

        // Append SQL if present
        if (data.sql) {
            responseHtml += `
                <div style="margin-top: 1rem;">
                    <p style="font-size: 0.8em; color: var(--text-secondary); margin-bottom: 0.25rem;">Generated SQL:</p>
                    <pre><code class="language-sql">${data.sql}</code></pre>
                </div>
            `;
        }

        // Append Context if present (and intent was RAG)
        if (data.intent === 'rag' && data.context) {
            responseHtml += `
                <div style="margin-top: 1rem;">
                    <p style="font-size: 0.8em; color: var(--text-secondary); margin-bottom: 0.25rem;">Source:</p>
                    <pre><code class="language-text">${data.context.substring(0, 150)}...</code></pre>
                </div>
            `;
        }

        addMessage('ai', responseHtml);

    } catch (error) {
        showTyping(false);
        addMessage('ai', `<p style="color: #ef4444;">Error: Could not connect to Pilot. Is the API running?</p>`);
        console.error(error);
    }
}

// Health Check & Polling
async function checkHealth() {
    try {
        const response = await fetch('http://localhost:8000/health');
        const data = await response.json();

        const statusBanner = document.getElementById('status-banner');
        const submitBtn = document.querySelector('button[type="submit"]');

        if (data.llm && data.llm.status === 'downloading') {
            // Show Loading State
            if (!statusBanner) {
                const banner = document.createElement('div');
                banner.id = 'status-banner';
                banner.style.cssText = 'background: #eab308; color: #000; padding: 0.5rem; text-align: center; font-weight: bold; position: sticky; top: 0; z-index: 100;';
                banner.innerHTML = `⚠️ Model is downloading... (${data.llm.model}). Please wait.`;
                document.body.prepend(banner);
            }
            userInput.disabled = true;
            userInput.placeholder = "Waiting for model download...";
            submitBtn.disabled = true;

            // Poll again in 5s
            setTimeout(checkHealth, 5000);
        } else {
            // Ready State
            if (statusBanner) statusBanner.remove();
            userInput.disabled = false;
            userInput.placeholder = "Ask about your logs...";
            submitBtn.disabled = false;
        }
    } catch (e) {
        console.error("Health check failed", e);
        // Retry in 5s if API is down
        setTimeout(checkHealth, 5000);
    }
}

// Start polling
checkHealth();

chatForm.addEventListener('submit', handleSubmit);
