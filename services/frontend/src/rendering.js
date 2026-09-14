// All model-provided HTML passes through a restricted local sanitizer.
window.LogPilotRendering = (() => {
    function escapeText(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[char]);
    }
    function sanitizeHTML(value) {
        if (!window.DOMPurify) return escapeText(value);
        return DOMPurify.sanitize(String(value ?? ''), {
            ALLOWED_TAGS: ['p', 'br', 'hr', 'strong', 'em', 'del', 'blockquote',
                'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a',
                'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
                'details', 'summary', 'div', 'span'],
            ALLOWED_ATTR: ['class', 'href', 'title'],
            ALLOW_DATA_ATTR: false,
            ALLOW_ARIA_ATTR: false
        });
    }
    function renderMarkdown(value) {
        return window.marked ? sanitizeHTML(marked.parse(String(value ?? ''))) : escapeText(value);
    }
    return { escapeText, sanitizeHTML, renderMarkdown };
})();
