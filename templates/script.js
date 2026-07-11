
    const terminal   = document.getElementById('terminal');
    const statusDot  = document.getElementById('statusDot');
    const statusLabel= document.getElementById('statusLabel');
    const sbStatus   = document.getElementById('sbStatus');
    const sbCount    = document.getElementById('sbCount');
    const sbTime     = document.getElementById('sbTime');
    const logBadge   = document.getElementById('logCountBadge');
    const scrollPill = document.getElementById('scrollPill');

    let totalLines   = 0;
    let autoScroll   = true;
    let showTs       = false;
    let cursorEl     = null;

    // ── Clock ──
    setInterval(() => {
        sbTime.textContent = new Date().toLocaleTimeString('fr-FR');
    }, 1000);

    // ── Classify ──
    function classify(msg) {
        if (msg.includes('✅') || msg.includes('[SUCCESS]'))                                     return 'success';
        if (msg.includes('❌') || msg.includes('Erreur') || msg.includes('ERROR'))              return 'error';
        if (msg.includes('⚠️') || msg.includes('WARNING'))                                      return 'warning';
        if (msg.includes('[WEB]'))                                                               return 'web';
        if (msg.includes('INFO') || msg.includes('ℹ️'))                                         return 'info';
        if (msg.includes('------') || msg.startsWith('20'))                                     return 'dim';
        return '';
    }

    // ── Render line ──
    function renderLine(msg, isNew) {
        // Remove cursor temporarily
        if (cursorEl) cursorEl.remove();

        totalLines++;
        const cls = classify(msg);
        const now = new Date().toLocaleTimeString('fr-FR');

        const line = document.createElement('div');
        line.className = 'line' + (cls ? ' c-' + cls : '');

        const promptSpan = document.createElement('span');
        promptSpan.className = 'prompt';
        promptSpan.innerHTML =
            '<span class="prompt-user">bot</span>' +
            '<span class="prompt-at">@</span>' +
            '<span class="prompt-host">chouchous</span>' +
            '<span class="prompt-sep">:</span>' +
            '<span class="prompt-path">~</span>' +
            '<span class="prompt-arrow"> $ </span>';

        const msgSpan = document.createElement('span');
        msgSpan.className = 'msg';
        msgSpan.textContent = (showTs ? '[' + now + '] ' : '') + msg;

        line.appendChild(promptSpan);
        line.appendChild(msgSpan);
        terminal.appendChild(line);

        // Re-add cursor
        addCursor();

        updateCounts();

        const atBottom = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight < 60;
        if (!atBottom && isNew) {
            scrollPill.classList.add('visible');
        }
        if (autoScroll) scrollToBottom();
    }

    function addCursor() {
        const cl = document.createElement('div');
        cl.className = 'cursor-line';

        const p = document.createElement('span');
        p.className = 'prompt';
        p.innerHTML =
            '<span class="prompt-user">bot</span>' +
            '<span class="prompt-at">@</span>' +
            '<span class="prompt-host">chouchous</span>' +
            '<span class="prompt-sep">:</span>' +
            '<span class="prompt-path">~</span>' +
            '<span class="prompt-arrow"> $ </span>';

        const c = document.createElement('span');
        c.className = 'cursor';

        cl.appendChild(p);
        cl.appendChild(c);
        terminal.appendChild(cl);
        cursorEl = cl;
    }

    function updateCounts() {
        const txt = totalLines + ' ligne' + (totalLines !== 1 ? 's' : '');
        sbCount.textContent  = txt;
        logBadge.textContent = txt;
    }

    function scrollToBottom() {
        terminal.scrollTop = terminal.scrollHeight;
        scrollPill.classList.remove('visible');
    }

    terminal.addEventListener('scroll', () => {
        const atBottom = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight < 60;
        if (atBottom) scrollPill.classList.remove('visible');
    });

    function clearTerminal() {
        terminal.innerHTML = '';
        totalLines = 0;
        cursorEl = null;
        addCursor();
        updateCounts();
    }

    function toggleTimestamps() {
        showTs = !showTs;
        document.getElementById('tsToggle').textContent = '⏱ Timestamps ' + (showTs ? 'ON' : 'OFF');
    }

    // ── Socket.IO ──
    const socket = io();

    socket.on('connect', () => {
        statusDot.classList.add('online');
        statusLabel.textContent = 'Connecté';
        sbStatus.textContent = '● En ligne';
        sbStatus.style.color = '#4ec94e';
    });

    socket.on('disconnect', () => {
        statusDot.classList.remove('online');
        statusLabel.textContent = 'Déconnecté';
        sbStatus.textContent = '● Hors ligne';
        sbStatus.style.color = '#e05c5c';
    });

    socket.on('new_log', (data) => {
        if (data.message && data.message.trim()) {
            renderLine(data.message.trim(), true);
        }
    });

    // Initial cursor
    addCursor();
