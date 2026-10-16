(() => {
    function initAgentCursor() {
        if (document.getElementById('agent-cursor-overlay')) return;

        const cursor = document.createElement('div');
        cursor.id = 'agent-cursor-overlay';
        cursor.style.position = 'fixed';
        cursor.style.top = '-100px';
        cursor.style.left = '-100px';
        cursor.style.width = '24px';
        cursor.style.height = '24px';
        cursor.style.borderRadius = '50%';
        cursor.style.backgroundColor = 'rgba(255, 45, 85, 0.85)';
        cursor.style.border = '2px solid #ffffff';
        cursor.style.boxShadow = '0 0 16px rgba(255, 45, 85, 1)';
        cursor.style.pointerEvents = 'none';
        cursor.style.zIndex = '2147483647';
        cursor.style.transform = 'translate(-50%, -50%)';
        cursor.style.transition = 'opacity 0.25s ease, transform 0.04s linear';
        cursor.style.opacity = '0';

        const dot = document.createElement('div');
        dot.style.width = '6px';
        dot.style.height = '6px';
        dot.style.borderRadius = '50%';
        dot.style.backgroundColor = '#ffffff';
        dot.style.position = 'absolute';
        dot.style.top = '50%';
        dot.style.left = '50%';
        dot.style.transform = 'translate(-50%, -50%)';
        cursor.appendChild(dot);

        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes agent-cursor-ripple {
                0% { width: 20px; height: 20px; opacity: 1; transform: translate(-50%, -50%) scale(1); }
                100% { width: 84px; height: 84px; opacity: 0; transform: translate(-50%, -50%) scale(1); }
            }
            .agent-click-ripple {
                position: fixed;
                border-radius: 50%;
                border: 2px solid #ff2d55;
                background: rgba(255, 45, 85, 0.25);
                pointer-events: none;
                z-index: 2147483646;
                animation: agent-cursor-ripple 0.45s ease-out forwards;
            }
        `;
        (document.head || document.documentElement).appendChild(style);
        (document.body || document.documentElement).appendChild(cursor);

        // Explicit Agent Cursor API (ignores human mouse events completely)
        window.__moveAgentCursor = (x, y) => {
            cursor.style.opacity = '1';
            cursor.style.left = x + 'px';
            cursor.style.top = y + 'px';
        };

        window.__hideAgentCursor = () => {
            cursor.style.opacity = '0';
        };

        window.__agentClick = (x, y) => {
            cursor.style.opacity = '1';
            cursor.style.left = x + 'px';
            cursor.style.top = y + 'px';
            const rip = document.createElement('div');
            rip.className = 'agent-click-ripple';
            rip.style.top = y + 'px';
            rip.style.left = x + 'px';
            (document.body || document.documentElement).appendChild(rip);
            setTimeout(() => rip.remove(), 500);
        };
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAgentCursor);
    } else {
        initAgentCursor();
    }
})();
