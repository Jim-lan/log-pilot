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

        // 4. Append References (SQL/RAG)
        if (data.sql || data.context) {
            responseHtml += `<div class="references" style="margin-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 0.5rem;">`;

            // SQL Reference
            if (data.sql) {
                responseHtml += `
                    <details style="margin-bottom: 0.5rem;">
                        <summary style="cursor: pointer; font-size: 0.85em; color: #60a5fa; font-weight: 500;">🔍 View SQL Query & Results</summary>
                        <div style="background: rgba(0,0,0,0.3); padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem;">
                            <div style="font-size: 0.75em; color: #9ca3af; margin-bottom: 0.25rem;">Generated SQL:</div>
                            <pre style="margin: 0; background: transparent;"><code class="language-sql" style="font-size: 0.8em;">${data.sql}</code></pre>
                            ${data.sql_result ? `
                                <div style="font-size: 0.75em; color: #9ca3af; margin: 0.5rem 0 0.25rem;">Execution Result:</div>
                                <pre style="margin: 0; background: transparent;"><code class="language-json" style="font-size: 0.8em;">${data.sql_result}</code></pre>
                            ` : ''}
                        </div>
                    </details>
                `;
            }

            // RAG Reference
            if (data.context) {
                responseHtml += `
                    <details>
                        <summary style="cursor: pointer; font-size: 0.85em; color: #34d399; font-weight: 500;">📄 View Retrieved Context</summary>
                        <div style="background: rgba(0,0,0,0.3); padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem;">
                            <pre style="margin: 0; background: transparent;"><code class="language-text" style="font-size: 0.8em;">${data.context}</code></pre>
                        </div>
                    </details>
                `;
            }

            responseHtml += `</div>`;
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

// Load History
async function loadHistory() {
    try {
        const response = await fetch('http://localhost:8000/history');
        const history = await response.json();

        // 1. Populate Chat Window
        messagesContainer.innerHTML = ''; // Clear default welcome
        if (history.length === 0) {
            addMessage('ai', `<p>Hello! I'm LogPilot. I can help you query your logs using natural language. 🚀</p>`);
        } else {
            history.forEach(msg => {
                // Simple markdown parsing for history
                const html = marked.parse(msg.content);
                addMessage(msg.role, html);
            });
        }

        // 2. Populate Sidebar
        const historyList = document.getElementById('history-list');
        historyList.innerHTML = '';

        // Group by User queries for the sidebar list
        const userQueries = history.filter(h => h.role === 'user');
        userQueries.forEach(q => {
            const li = document.createElement('li');
            li.textContent = q.content.length > 30 ? q.content.substring(0, 30) + '...' : q.content;
            li.title = q.content;
            li.style.cssText = "padding: 0.5rem; cursor: pointer; border-bottom: 1px solid #333; font-size: 0.9em;";
            li.onclick = () => {
                userInput.value = q.content;
                userInput.focus();
            };
            historyList.appendChild(li);
        });

    } catch (e) {
        console.error("Failed to load history", e);
    }
}

// Start polling
checkHealth();
loadHistory();

chatForm.addEventListener('submit', handleSubmit);
