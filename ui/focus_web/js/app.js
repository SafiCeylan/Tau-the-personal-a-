/* ==========================================================================
   ULTRON HOLOGRAPHIC APP & TACTICAL HUD RADIAL WHEEL SYSTEM
   ========================================================================== */

window.ultronCoreState = 'IDLE';

(function() {
    let cmdInput, chatBody, lblState, lblCore, telFreq, telTemp;
    let svgCpuBar, svgRamBar, valCpu, valRam;
    let coreRadialMenu, btnToggleRadial;
    let telemetryTimer = null;
    let paused = false;

    // 4 Theme Presets
    const themePresets = [
        { id: 'gold', icon: '🎨', label: 'Ultron Gold', class: 'theme-gold' },
        { id: 'cyan', icon: '💎', label: 'Ultron Cyan', class: 'theme-cyan' },
        { id: 'matrix', icon: '❇️', label: 'Ultron Matrix', class: 'theme-matrix' },
        { id: 'aurora', icon: '🌌', label: 'Soft Aurora', class: 'theme-aurora' }
    ];
    let currentThemeIdx = 0;

    /* Köprüye kısayol: bağlı değilse null döner. */
    function api() {
        return (window.UltronBridge && window.UltronBridge.api) || null;
    }

    function initApp() {
        cmdInput = document.getElementById('cmd-input');
        chatBody = document.getElementById('ai-chat-body');
        lblState = document.getElementById('lbl-state');
        lblCore = document.getElementById('lbl-core');
        telFreq = document.getElementById('tel-freq');
        telTemp = document.getElementById('tel-temp');

        svgCpuBar = document.getElementById('svg-cpu-bar');
        svgRamBar = document.getElementById('svg-ram-bar');
        valCpu = document.getElementById('val-cpu');
        valRam = document.getElementById('val-ram');

        coreRadialMenu = document.getElementById('core-radial-menu');
        btnToggleRadial = document.getElementById('btn-toggle-radial');

        setupThemePresetToggle();
        setupWindowControlButtons();
        setupFormListener();
        setupInputTypingListener();
        setupQuickChipListeners();
        setupTacticalHudRadialListeners();
        setupViewModeToggle();

        // Köprü hazır olunca haber ver (event kaçırma riski yok — Promise).
        if (window.UltronBridge) {
            window.UltronBridge.ready.then(onBridgeReady);
        } else {
            console.warn('[ULTRON] UltronBridge yüklenmemiş.');
        }

        telemetryTimer = setInterval(pollTelemetry, 2500);
    }

    function onBridgeReady(bridgeApi) {
        if (!bridgeApi) {
            console.warn('[ULTRON] Python köprüsü yok — komutlar çalıştırılamaz.');
            return;
        }
        console.log('[ULTRON] Nöral çekirdek köprüsü bağlandı.');
        pollTelemetry();

        if (bridgeApi.get_initial_state) {
            bridgeApi.get_initial_state().then((data) => {
                if (data) console.log('Ultron Core Initialized:', data);
            }).catch(err => console.log('State init note:', err));
        }
    }

    /* ----------------------------------------------------------------------
       KOMUT GÖNDERİMİ — tek kapı
       Köprü varsa: kullanıcı satırını Python geri yansıtır (çift basılmasın).
       Köprü yoksa: sahte "başarılı" mesajı YAZMAYIZ, açıkça hata veririz.
       ---------------------------------------------------------------------- */
    function dispatchBridgeCall(methodName, arg, fallbackLabel) {
        const bridge = api();

        if (!bridge || typeof bridge[methodName] !== 'function') {
            appendUserMsg(fallbackLabel);
            appendSystemMsg('⚠️ Python köprüsü bağlı değil — komut çalıştırılamadı. (Konsolu kontrol et)');
            setCoreState('IDLE');
            return;
        }

        setCoreState('PROCESSING');
        bridge[methodName](arg).then((res) => {
            // Gerçek cevap motordan asenkron gelir (add_message ile).
            // Burada sadece köprünün reddettiği durumları gösteririz.
            if (res && res.status === 'error') {
                appendSystemMsg('⚠️ ' + (res.message || 'Komut reddedildi.'));
                setCoreState('IDLE');
            }
        }).catch((err) => {
            console.error('Köprü hatası:', err);
            appendSystemMsg('⚠️ Köprü hatası: ' + err);
            setCoreState('IDLE');
        });
    }

    /* ----------------------------------------------------------------------
       FEATURE 1: SCI-FI TACTICAL HUD RADIAL WHEEL SYSTEM
       ---------------------------------------------------------------------- */
    function setupTacticalHudRadialListeners() {
        const canvas3d = document.getElementById('canvas-3d');
        if (!coreRadialMenu) return;

        if (btnToggleRadial) {
            btnToggleRadial.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleRadialMenu();
            });
        }

        if (canvas3d) {
            canvas3d.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                toggleRadialMenu();
            });
        }

        function toggleRadialMenu() {
            if (coreRadialMenu.classList.contains('hidden')) {
                coreRadialMenu.classList.remove('hidden');
                if (window.UltronAudio) window.UltronAudio.charge();
            } else {
                coreRadialMenu.classList.add('hidden');
            }
        }

        // Handle 6 Hexagonal Radial Node Clicks
        const radialNodes = coreRadialMenu.querySelectorAll('.radial-hex-node');
        radialNodes.forEach((node) => {
            node.addEventListener('click', (e) => {
                e.stopPropagation();
                coreRadialMenu.classList.add('hidden');

                const action = node.getAttribute('data-action');
                if (!action) return;

                if (window.UltronAudio) window.UltronAudio.pulse();
                if (typeof window.triggerUltronPulseWave === 'function') {
                    window.triggerUltronPulseWave();
                }

                const title = node.querySelector('.node-title').textContent;
                dispatchBridgeCall('execute_quick_action', action, `[Tactical HUD] ${title}`);
            });
        });

        // Close when clicking outside
        document.addEventListener('click', (e) => {
            if (!coreRadialMenu.contains(e.target) && e.target !== btnToggleRadial) {
                coreRadialMenu.classList.add('hidden');
            }
        });
    }

    /* ----------------------------------------------------------------------
       FEATURE 2: INPUT TYPING MOTION
       ---------------------------------------------------------------------- */
    function setupInputTypingListener() {
        if (!cmdInput) return;

        cmdInput.addEventListener('input', () => {
            if (cmdInput.value.length > 0) {
                setCoreState('TYPING');
            } else {
                if (window.ultronCoreState === 'TYPING') {
                    setCoreState('IDLE');
                }
            }
        });
    }

    /* ----------------------------------------------------------------------
       FEATURE 3: DYNAMIC THEME PRESET SWITCHER
       ---------------------------------------------------------------------- */
    function setupThemePresetToggle() {
        const btn = document.getElementById('btn-toggle-theme');
        const iconElem = document.getElementById('theme-icon');
        const labelElem = document.getElementById('theme-label');
        if (!btn) return;

        btn.addEventListener('click', () => {
            currentThemeIdx = (currentThemeIdx + 1) % themePresets.length;
            const theme = themePresets[currentThemeIdx];

            document.body.className = theme.class;

            if (iconElem) iconElem.textContent = theme.icon;
            if (labelElem) labelElem.textContent = theme.label;

            if (typeof window.set3DHologramTheme === 'function') {
                window.set3DHologramTheme(theme.id);
            }

            if (window.UltronAudio) window.UltronAudio.charge();
            if (typeof window.triggerUltronPulseWave === 'function') {
                window.triggerUltronPulseWave();
            }

            appendSystemMsg(`Ultron Hologram Teması Değiştirildi: [${theme.label}]`);
        });
    }

    /* ----------------------------------------------------------------------
       FRAMELESS WINDOW CONTROLS
       ---------------------------------------------------------------------- */
    function setupWindowControlButtons() {
        const btnMin = document.getElementById('win-btn-min');
        const btnMax = document.getElementById('win-btn-max');
        const btnClose = document.getElementById('win-btn-close');

        if (btnMin) {
            btnMin.addEventListener('click', () => {
                if (window.UltronAudio) window.UltronAudio.click();
                const b = api();
                if (b) b.minimize_window();
            });
        }

        if (btnMax) {
            btnMax.addEventListener('click', () => {
                if (window.UltronAudio) window.UltronAudio.click();
                const b = api();
                if (b) b.maximize_window();
            });
        }

        if (btnClose) {
            btnClose.addEventListener('click', () => {
                if (window.UltronAudio) window.UltronAudio.beep(440, 0.15);
                const b = api();
                if (b) b.close_window();
            });
        }
    }

    /* ----------------------------------------------------------------------
       TYPEWRITER LOG & MESSAGES
       ---------------------------------------------------------------------- */
    function dropWelcomePlaceholder() {
        // İlk gerçek mesaj gelince HTML'deki statik karşılama satırı düşer
        // (Python açılışta aynı karşılamayı zaten gönderiyor → çift yazmasın).
        const ph = document.getElementById('initial-welcome-msg');
        if (ph) ph.remove();
    }

    /* Motorun markdown'ını (**kalın**, `kod`, satır sonu) görünür HTML'e çevirir. */
    function formatUltronText(text) {
        return escapeHtml(text)
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    /* Typewriter için düz metin: işaretler görünmesin. */
    function stripMarkdown(text) {
        return text.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/`([^`]+)`/g, '$1');
    }

    function appendUserMsg(msgText) {
        if (!chatBody) return;
        dropWelcomePlaceholder();
        const p = document.createElement('p');
        p.className = 'chat-msg user-msg mt-10';
        p.innerHTML = `<span class="dim-text">❯ Emredilen:</span> <strong>${escapeHtml(msgText)}</strong>`;
        chatBody.appendChild(p);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function appendSystemMsg(fullText) {
        if (!chatBody) return;
        dropWelcomePlaceholder();

        const p = document.createElement('p');
        p.className = 'chat-msg system-msg mt-10 animate-fade-in';

        const prefix = `<span class="neon-text-red">🤖 ULTRON:</span> `;
        const hex = '[0x' + Math.floor(Math.random() * 255).toString(16).toUpperCase() + ']';
        const suffix = ` <span class="hex-inline">${hex}</span>`;

        p.innerHTML = prefix + `<span class="typewriter-content"></span>` + suffix;
        chatBody.appendChild(p);
        chatBody.scrollTop = chatBody.scrollHeight;

        const textSpan = p.querySelector('.typewriter-content');
        if (!textSpan) return;

        // Uzun cevaplar harf harf yazılırsa dakikalar sürer → tek seferde bas.
        if (fullText.length > 240) {
            textSpan.innerHTML = formatUltronText(fullText);
            chatBody.scrollTop = chatBody.scrollHeight;
            if (window.ultronCoreState === 'TYPING') setCoreState('IDLE');
            return;
        }

        // Performans: harf harf yerine 2'şer harf, sesi de en fazla 110ms'de bir
        // çalıyoruz. Eskiden saniyede ~18 kez Web Audio düğümü kuruluyordu —
        // komut verildiğinde hissedilen kasmanın ana kaynağı buydu.
        const plain = stripMarkdown(fullText);
        const CHARS_PER_TICK = 2;
        const TICK_MS = 34;
        const SOUND_MIN_GAP = 110;
        let charIdx = 0;
        let lastSound = 0;

        setCoreState('TYPING');

        function typeNextChunk() {
            if (charIdx < plain.length) {
                textSpan.textContent += plain.substr(charIdx, CHARS_PER_TICK);
                charIdx += CHARS_PER_TICK;

                const now = Date.now();
                if (window.UltronAudio && now - lastSound >= SOUND_MIN_GAP) {
                    lastSound = now;
                    window.UltronAudio.click();
                }

                chatBody.scrollTop = chatBody.scrollHeight;
                setTimeout(typeNextChunk, TICK_MS);
            } else {
                // Yazım bitti → markdown biçimini yerine koy
                textSpan.innerHTML = formatUltronText(fullText);
                chatBody.scrollTop = chatBody.scrollHeight;
                setCoreState('IDLE');
            }
        }

        typeNextChunk();
    }

    function setupFormListener() {
        const form = document.getElementById('command-form');
        const btnSubmit = document.getElementById('btn-submit');
        if (!form) return;

        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const text = cmdInput.value.trim();
            if (!text) return;

            cmdInput.value = '';

            if (window.UltronAudio) window.UltronAudio.pulse();
            if (typeof window.triggerUltronPulseWave === 'function') {
                window.triggerUltronPulseWave();
            }

            dispatchBridgeCall('send_command', text, text);
        });

        // Kutu boşken mikrofon butonu sesli komutu başlatır (ikon zaten mikrofon).
        if (btnSubmit) {
            btnSubmit.addEventListener('click', () => {
                if (cmdInput && cmdInput.value.trim()) return;   // dolu → form gönderir
                const b = api();
                if (!b || typeof b.start_voice_input !== 'function') {
                    appendSystemMsg('⚠️ Sesli komut köprüsü bağlı değil.');
                    return;
                }
                if (window.UltronAudio) window.UltronAudio.charge();
                b.start_voice_input().then((res) => {
                    if (res && res.status === 'error') appendSystemMsg('⚠️ ' + res.message);
                }).catch((err) => appendSystemMsg('⚠️ Mikrofon hatası: ' + err));
            });
        }
    }

    /* Python'dan gelen durumları HUD etiketine çevirir. */
    function setCoreState(newState) {
        const raw = String(newState || 'IDLE').toUpperCase();
        const map = {
            THINKING: 'PROCESSING',
            SPEAKING: 'SPEAKING',
            LISTENING: 'LISTENING',
            IDLE: 'IDLE'
        };
        const state = map[raw] || raw;

        window.ultronCoreState = state;
        if (lblState) {
            lblState.textContent = state;
            if (state === 'IDLE') {
                lblState.className = 'badge-value neon-text-blue';
            } else {
                lblState.className = 'badge-value neon-text-red';
            }
        }
    }

    function setupQuickChipListeners() {
        const chips = document.querySelectorAll('.chip-btn');
        chips.forEach((chip) => {
            chip.addEventListener('click', () => {
                const action = chip.getAttribute('data-action');
                if (!action) return;

                if (window.UltronAudio) window.UltronAudio.click();
                if (typeof window.triggerUltronPulseWave === 'function') {
                    window.triggerUltronPulseWave();
                }

                const label = chip.querySelector('span:last-child').textContent;
                dispatchBridgeCall('execute_quick_action', action, `[Hızlı İşlem] ${label}`);
            });
        });
    }

    function setupViewModeToggle() {
        const btn = document.getElementById('btn-toggle-view');
        if (!btn) return;

        btn.addEventListener('click', () => {
            if (window.UltronAudio) window.UltronAudio.click();
            if (typeof window.triggerUltronPulseWave === 'function') {
                window.triggerUltronPulseWave();
            }
            const b = api();
            if (b) {
                b.toggle_view_mode('standard');
            } else {
                appendSystemMsg('⚠️ Python köprüsü bağlı değil — görünüm değiştirilemedi.');
            }
        });
    }

    /* ----------------------------------------------------------------------
       TELEMETRY POLLING & RADIAL GAUGES ANIMATION
       ---------------------------------------------------------------------- */
    function pollTelemetry() {
        if (paused) return;
        const b = api();

        if (b && typeof b.get_telemetry === 'function') {
            b.get_telemetry().then((data) => {
                if (!data) return;
                if (lblCore) lblCore.textContent = `${data.core_load}%`;
                if (telFreq) telFreq.textContent = data.freq;
                if (telTemp) telTemp.textContent = data.temp;

                updateRadialGauges(data.cpu, data.ram);
            }).catch(() => {});
        }
        // Köprü yoksa sayaçlar son gerçek değerde donar — uydurma veri basmayız.
    }

    function updateRadialGauges(cpuVal, ramVal) {
        if (valCpu) valCpu.textContent = Math.round(cpuVal);
        if (valRam) valRam.textContent = Math.round(ramVal);

        if (svgCpuBar) {
            svgCpuBar.setAttribute('stroke-dasharray', `${Math.round(cpuVal)}, 100`);
        }
        if (svgRamBar) {
            svgRamBar.setAttribute('stroke-dasharray', `${Math.round(ramVal)}, 100`);
        }
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    /* ----------------------------------------------------------------------
       CANLI AKIŞ (Ollama streaming) — cevap kelime kelime aksın
       ---------------------------------------------------------------------- */
    let streamSpan = null;

    function beginStreamMsg() {
        if (!chatBody) return;
        dropWelcomePlaceholder();

        const p = document.createElement('p');
        p.className = 'chat-msg system-msg mt-10 animate-fade-in';
        const prefix = `<span class="neon-text-red">🤖 ULTRON:</span> `;
        const hex = '[0x' + Math.floor(Math.random() * 255).toString(16).toUpperCase() + ']';
        p.innerHTML = prefix + `<span class="typewriter-content">▌</span>` +
                      ` <span class="hex-inline">${hex}</span>`;
        chatBody.appendChild(p);
        chatBody.scrollTop = chatBody.scrollHeight;
        streamSpan = p.querySelector('.typewriter-content');
    }

    function updateStreamMsg(partial) {
        if (!streamSpan) beginStreamMsg();
        if (!streamSpan) return;
        streamSpan.textContent = stripMarkdown(partial) + ' ▌';
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function endStreamMsg(fullText) {
        if (!streamSpan) {
            appendSystemMsg(fullText);
            return;
        }
        streamSpan.innerHTML = formatUltronText(fullText);
        chatBody.scrollTop = chatBody.scrollHeight;
        streamSpan = null;
    }

    /* ----------------------------------------------------------------------
       PYTHON'DAN ÇAĞRILAN GLOBAL API
       (IIFE içinde kaldıkları için runJavaScript bunlara ulaşamıyordu.)
       ---------------------------------------------------------------------- */
    window.appendUserMsg = appendUserMsg;
    window.appendSystemMsg = appendSystemMsg;
    window.setCoreState = setCoreState;
    window.beginStreamMsg = beginStreamMsg;
    window.updateStreamMsg = updateStreamMsg;
    window.endStreamMsg = endStreamMsg;

    /* Odak sayfası görünmüyorken 3D render + telemetriyi durdurur (CPU/GPU). */
    window.setUltronActive = function(active) {
        paused = !active;
        window.__ultronPaused = paused;
        if (active) pollTelemetry();
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initApp);
    } else {
        initApp();
    }
})();
