/* ==========================================================================
   ULTRON SCI-FI WEB AUDIO SYNTHESIZER (PURE CODE SOUND FX)
   ========================================================================== */

window.UltronAudio = (function() {
    let ctx = null;
    let unlocked = false;

    // Chromium, kullanıcı sayfaya dokunmadan ses açılmasına izin vermez; her
    // denemede terminale "AudioContext was not allowed to start" basar.
    // İlk gerçek etkileşime kadar ses motoruna hiç dokunmuyoruz.
    function unlockAudio() {
        unlocked = true;
        window.removeEventListener('pointerdown', unlockAudio);
        window.removeEventListener('keydown', unlockAudio);
        if (ctx && ctx.state === 'suspended') ctx.resume();
    }
    window.addEventListener('pointerdown', unlockAudio);
    window.addEventListener('keydown', unlockAudio);

    function getAudioContext() {
        if (!unlocked) return null;
        if (!ctx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
                ctx = new AudioCtx();
            }
        }
        if (ctx && ctx.state === 'suspended') {
            ctx.resume();
        }
        return ctx;
    }

    // 1. Shockwave Energy Pulse Sound
    function playPulseSound() {
        const c = getAudioContext();
        if (!c) return;

        const osc = c.createOscillator();
        const gain = c.createGain();
        const filter = c.createBiquadFilter();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(320, c.currentTime);
        osc.frequency.exponentialRampToValueAtTime(45, c.currentTime + 0.35);

        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(1200, c.currentTime);
        filter.frequency.exponentialRampToValueAtTime(150, c.currentTime + 0.35);

        gain.gain.setValueAtTime(0.3, c.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 0.35);

        osc.connect(filter);
        filter.connect(gain);
        gain.connect(c.destination);

        osc.start();
        osc.stop(c.currentTime + 0.36);
    }

    // 2. High-Tech UI Beep / Confirmation Chime
    function playBeepSound(freq = 880, duration = 0.08) {
        const c = getAudioContext();
        if (!c) return;

        const osc = c.createOscillator();
        const gain = c.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, c.currentTime);
        osc.frequency.exponentialRampToValueAtTime(freq * 1.5, c.currentTime + duration);

        gain.gain.setValueAtTime(0.18, c.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + duration);

        osc.connect(gain);
        gain.connect(c.destination);

        osc.start();
        osc.stop(c.currentTime + duration);
    }

    // 3. Short Futuristic UI Click Tick
    function playClickSound() {
        playBeepSound(1200, 0.04);
    }

    // 4. Energy Charge Sound
    function playEnergyCharge() {
        const c = getAudioContext();
        if (!c) return;

        const osc = c.createOscillator();
        const gain = c.createGain();

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(180, c.currentTime);
        osc.frequency.exponentialRampToValueAtTime(750, c.currentTime + 0.25);

        gain.gain.setValueAtTime(0.15, c.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 0.25);

        osc.connect(gain);
        gain.connect(c.destination);

        osc.start();
        osc.stop(c.currentTime + 0.26);
    }

    return {
        pulse: playPulseSound,
        beep: playBeepSound,
        click: playClickSound,
        charge: playEnergyCharge
    };
})();
