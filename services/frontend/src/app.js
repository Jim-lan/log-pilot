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

// View Switching
function switchView(viewName) {
    const chatView = document.getElementById('chat-view');
    const perfView = document.getElementById('performance-view');
    const alertsView = document.getElementById('alerts-view');
    const navItems = document.querySelectorAll('.nav-item');

    // Update Nav
    navItems.forEach(item => item.classList.remove('active'));
    if (viewName === 'chat') navItems[0].classList.add('active');
    if (viewName === 'performance') navItems[1].classList.add('active');
    if (viewName === 'alerts') navItems[2].classList.add('active');

    // Update View
    chatView.classList.add('hidden');
    perfView.classList.add('hidden');
    alertsView.classList.add('hidden');

    if (viewName === 'chat') {
        chatView.classList.remove('hidden');
    } else if (viewName === 'performance') {
        perfView.classList.remove('hidden');
        loadMetrics();
    } else if (viewName === 'alerts') {
        alertsView.classList.remove('hidden');
        checkAlerts();
    }
}

// Metrics Loading
async function loadMetrics() {
    try {
        const response = await fetch('http://localhost:8000/metrics');
        const data = await response.json();

        // Update Cards
        document.getElementById('metric-pass-rate').textContent = `${data.pass_rate_24h}%`;
        document.getElementById('metric-latency').textContent = `${data.avg_latency_24h}s`;
        document.getElementById('metric-runs').textContent = data.total_runs;

        // Update Table
        const tbody = document.getElementById('metrics-history-body');
        tbody.innerHTML = '';

        data.history.forEach(run => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';

            // Color code pass rate
            let color = '#ef4444'; // red
            if (run.pass_rate >= 90) color = '#34d399'; // green
            else if (run.pass_rate >= 70) color = '#eab308'; // yellow

            tr.innerHTML = `
                <td style="padding: 1rem; font-family: monospace; color: #d1d5db;">${run.run_id.substring(0, 8)}...</td>
                <td style="padding: 1rem; color: #9ca3af;">${new Date(run.timestamp).toLocaleString()}</td>
                <td style="padding: 1rem; font-weight: bold; color: ${color};">${run.pass_rate.toFixed(1)}%</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (e) {
        console.error("Failed to load metrics", e);
    }
}

async function checkAlerts() {
    try {
        const response = await fetch('http://localhost:8000/alerts');
        const alerts = await response.json();
        const alertCount = document.getElementById('alert-count');
        const alertsList = document.getElementById('alerts-list');

        // Update Badge
        if (alerts.length > 0) {
            alertCount.textContent = alerts.length;
            alertCount.style.display = 'inline-block';
        } else {
            alertCount.style.display = 'none';
        }

        // populate list
        if (alertsList && !document.getElementById('alerts-view').classList.contains('hidden')) {
            alertsList.innerHTML = '';
            if (alerts.length === 0) {
                alertsList.innerHTML = '<div style="color:#9ca3af; text-align:center;">No active alerts. System healthy. 🟢</div>';
                return;
            }

            alerts.forEach(alert => {
                const card = document.createElement('div');
                card.className = 'metric-card';
                card.style.cssText = "background: rgba(239, 68, 68, 0.1); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(239, 68, 68, 0.3); margin-bottom: 1rem;";

                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:start;">
                        <div>
                            <h3 style="color: #f87171; font-size: 1.1em; margin-bottom: 0.5rem;">🚨 ${alert.service} Error Spike</h3>
                            <div style="color: #d1d5db; margin-bottom: 0.5rem;">${alert.message}</div>
                            <div style="background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: 4px; font-size: 0.9em; color: #d1d5db;">
                                💡 <strong>Analysis:</strong> ${alert.analysis}
                            </div>
                            <div style="margin-top:0.5rem; font-size: 0.8em; color: #6b7280;">${new Date(alert.timestamp).toLocaleString()}</div>
                        </div>
                        <button onclick="markAlertRead('${alert.id}')" style="background:transparent; border:1px solid #f87171; color:#f87171; padding:0.25rem 0.5rem; border-radius:4px; cursor:pointer;">Dismiss</button>
                    </div>
                 `;
                alertsList.appendChild(card);
            });
        }

    } catch (e) {
        console.error("Alert check failed", e);
    }
}

async function markAlertRead(id) {
    try {
        await fetch(`http://localhost:8000/alerts/${id}/read`, { method: 'POST' });
        checkAlerts(); // Refresh
    } catch (e) {
        console.error("Failed to mark read", e);
    }
}

// Start polling
checkHealth();
loadHistory();
checkAlerts();
setInterval(checkAlerts, 5000); // 5s poll for demo

chatForm.addEventListener('submit', handleSubmit);
