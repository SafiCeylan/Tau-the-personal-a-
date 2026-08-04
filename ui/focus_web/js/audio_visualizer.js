/* ==========================================================================
   ULTRON HIGH-TECH RED & GOLD HOLOGRAPHIC AUDIO VISUALIZER
   ========================================================================== */

(function() {
    let topSpikesCanvas, topSpikesCtx;
    let phase = 0;

    function initVisualizers() {
        topSpikesCanvas = document.getElementById('canvas-top-spikes');
        if (topSpikesCanvas) topSpikesCtx = topSpikesCanvas.getContext('2d');

        renderVisualizers();
    }

    /* TOP CENTER CRIMSON & GOLD HOLOGRAPHIC SOUNDWAVE SPIKES */
    function drawTopSpikes() {
        if (!topSpikesCtx || !topSpikesCanvas) return;
        const w = topSpikesCanvas.width;
        const h = topSpikesCanvas.height;

        topSpikesCtx.clearRect(0, 0, w, h);

        const midY = h / 2;

        // Gold Spikes (Left side)
        topSpikesCtx.lineWidth = 1.5;
        topSpikesCtx.strokeStyle = '#ffb700';
        topSpikesCtx.shadowColor = '#ffb700';
        topSpikesCtx.shadowBlur = 8;

        topSpikesCtx.beginPath();
        for (let x = 10; x < w / 2 - 10; x += 4) {
            const hVal = Math.sin(x * 0.085 + phase) * Math.cos(x * 0.02) * (h * 0.42);
            topSpikesCtx.moveTo(x, midY - hVal);
            topSpikesCtx.lineTo(x, midY + hVal);
        }
        topSpikesCtx.stroke();

        // Crimson Red Spikes (Right side)
        topSpikesCtx.strokeStyle = '#ff2a4b';
        topSpikesCtx.shadowColor = '#ff2a4b';
        topSpikesCtx.shadowBlur = 8;

        topSpikesCtx.beginPath();
        for (let x = w / 2 + 10; x < w - 10; x += 4) {
            const hVal = Math.sin(x * 0.09 - phase * 1.2) * Math.cos(x * 0.03) * (h * 0.45);
            topSpikesCtx.moveTo(x, midY - hVal);
            topSpikesCtx.lineTo(x, midY + hVal);
        }
        topSpikesCtx.stroke();
        topSpikesCtx.shadowBlur = 0;

        // Hex Labels ("0x3", "0x5.2", "0x9", "0x33", "5228")
        topSpikesCtx.font = '10px "Share Tech Mono", monospace';
        topSpikesCtx.fillStyle = '#ffb700';
        topSpikesCtx.fillText('0x3', 20, 12);
        topSpikesCtx.fillText('0x5.2', w / 2 - 15, h - 4);
        
        topSpikesCtx.fillStyle = '#ff2a4b';
        topSpikesCtx.fillText('0x9', w - 45, 12);
        topSpikesCtx.fillText('0x33', w - 85, 12);
        topSpikesCtx.fillText('5228', 55, h - 4);
    }

    function renderVisualizers() {
        requestAnimationFrame(renderVisualizers);
        phase += 0.06;
        drawTopSpikes();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVisualizers);
    } else {
        initVisualizers();
    }
})();
