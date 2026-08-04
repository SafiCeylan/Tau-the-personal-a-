/* ==========================================================================
   ULTRON HIGH-TECH HOLOGRAPHIC 3D ENGINE (WITH SOFT AURORA PRESET & TYPING MOTION)
   ========================================================================== */

(function() {
    let scene, camera, renderer;
    let gyroGroup, pedestalGroup;
    let outerMasterSphere, outerRingGroup, middleRingGroup, innerRingGroup;
    let outerMesh, middleMesh, innerMesh, outerWire, middleWire;
    let coreNucleus, coreGoldSun, coreRedShell, coreGeodesicCage, coreRingGears = [];
    let particleSwarm;
    let radialEqualizerRing, horizontalLaserWave;
    let centerGoldLight, redRimLight, goldRimLight;

    let plasmaArcs = [];
    const arcCount = 6;
    let shockwavePulses = [];

    let isHovered = false;
    let targetGroupScale = 0.90;
    let currentGroupScale = 0.90;

    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };
    let targetRotationX = 0;
    let targetRotationY = 0;
    let currentRotationX = 0;
    let currentRotationY = 0;

    let clock = new THREE.Clock();

    // 4 Theme Presets
    const themes = {
        gold: {
            primary: 0xffb700,
            secondary: 0xff2a4b,
            sun: 0xffb700,
            metal: 0xffb700,
            darkMetal: 0x241410
        },
        cyan: {
            primary: 0x00f0ff,
            secondary: 0x70e0ff,
            sun: 0x00f0ff,
            metal: 0x00f0ff,
            darkMetal: 0x061828
        },
        matrix: {
            primary: 0x00ff66,
            secondary: 0x70ffb0,
            sun: 0x00ff66,
            metal: 0x00ff66,
            darkMetal: 0x062410
        },
        aurora: {
            primary: 0xb870ff,
            secondary: 0xff85a0,
            sun: 0xd6a3ff,
            metal: 0xb870ff,
            darkMetal: 0x181024
        }
    };
    let currentThemeName = 'gold';

    function init3D() {
        const container = document.getElementById('canvas-3d-wrapper');
        const canvas = document.getElementById('canvas-3d');

        if (!container || !canvas || typeof THREE === 'undefined') return;

        const width = container.clientWidth;
        const height = container.clientHeight;

        scene = new THREE.Scene();

        camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);
        camera.position.set(0, 0, 17.8);

        renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            alpha: true,
            antialias: true,
            powerPreference: "high-performance"
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(width, height, false);

        const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
        scene.add(ambientLight);

        centerGoldLight = new THREE.PointLight(0xffb700, 6, 30);
        centerGoldLight.position.set(0, 0, 0);
        scene.add(centerGoldLight);

        redRimLight = new THREE.PointLight(0xff2a4b, 6, 40);
        redRimLight.position.set(-12, 10, 10);
        scene.add(redRimLight);

        goldRimLight = new THREE.PointLight(0xffb700, 5, 40);
        goldRimLight.position.set(12, -10, 10);
        scene.add(goldRimLight);

        gyroGroup = new THREE.Group();
        gyroGroup.scale.set(0.90, 0.90, 0.90);
        scene.add(gyroGroup);

        buildLargeOuterHologramSphere();
        buildMechanicalGimbalRings();
        buildUltraDetailedCore();
        buildPlasmaArcs();
        buildRadialEqualizerRing();
        buildBackgroundLaserWave();
        buildPedestalBase();

        window.triggerUltronPulseWave = triggerPulseWave;
        window.set3DHologramTheme = apply3DTheme;

        setupDragControls(canvas);
        setupHoverListeners(canvas);
        window.addEventListener('resize', onWindowResize);
        if (typeof ResizeObserver !== 'undefined' && container) {
            new ResizeObserver(onWindowResize).observe(container);
        }
        setTimeout(onWindowResize, 50);
        setTimeout(onWindowResize, 200);
        setTimeout(onWindowResize, 600);

        animate();
    }

    function apply3DTheme(themeName) {
        if (!themes[themeName]) return;
        currentThemeName = themeName;
        const t = themes[themeName];

        if (centerGoldLight) centerGoldLight.color.setHex(t.primary);
        if (goldRimLight) goldRimLight.color.setHex(t.primary);
        if (redRimLight) redRimLight.color.setHex(t.secondary);

        if (outerMasterSphere) outerMasterSphere.material.color.setHex(t.primary);
        if (outerMesh) outerMesh.material.color.setHex(t.metal);
        if (middleMesh) middleMesh.material.color.setHex(t.metal);
        if (innerMesh) innerMesh.material.color.setHex(t.metal);

        if (middleWire) middleWire.material.color.setHex(t.secondary);
        if (coreGoldSun) coreGoldSun.material.color.setHex(t.sun);
        if (coreRedShell) coreRedShell.material.color.setHex(t.secondary);
        if (coreGeodesicCage) coreGeodesicCage.material.color.setHex(t.primary);

        coreRingGears.forEach((ring) => ring.material.color.setHex(t.primary));
        if (radialEqualizerRing) radialEqualizerRing.material.color.setHex(t.primary);
        if (horizontalLaserWave) horizontalLaserWave.material.color.setHex(t.secondary);

        if (particleSwarm && particleSwarm.geometry) {
            const colors = particleSwarm.geometry.attributes.color.array;
            const cSec = new THREE.Color(t.secondary);
            const cPri = new THREE.Color(t.primary);
            const cWhite = new THREE.Color(0xffffff);

            const count = colors.length / 3;
            for (let i = 0; i < count; i++) {
                const rand = Math.random();
                const c = rand > 0.5 ? cPri : (rand > 0.2 ? cSec : cWhite);
                colors[i * 3] = c.r;
                colors[i * 3 + 1] = c.g;
                colors[i * 3 + 2] = c.b;
            }
            particleSwarm.geometry.attributes.color.needsUpdate = true;
        }
    }

    function buildLargeOuterHologramSphere() {
        const outerSphereGeo = new THREE.SphereGeometry(6.0, 36, 36);
        const outerSphereMat = new THREE.MeshBasicMaterial({
            color: 0xffb700,
            wireframe: true,
            transparent: true,
            opacity: 0.28,
            blending: THREE.AdditiveBlending
        });
        outerMasterSphere = new THREE.Mesh(outerSphereGeo, outerSphereMat);
        gyroGroup.add(outerMasterSphere);

        const eqRingGeo = new THREE.TorusGeometry(6.02, 0.03, 12, 100);
        const eqRingMat = new THREE.MeshBasicMaterial({
            color: 0xff2a4b,
            transparent: true,
            opacity: 0.75,
            blending: THREE.AdditiveBlending
        });
        const eqRing = new THREE.Mesh(eqRingGeo, eqRingMat);
        eqRing.rotation.x = Math.PI / 2;
        gyroGroup.add(eqRing);
    }

    function buildPlasmaArcs() {
        for (let i = 0; i < arcCount; i++) {
            const arcPoints = [];
            for (let s = 0; s <= 12; s++) arcPoints.push(new THREE.Vector3(0, 0, 0));

            const arcGeo = new THREE.BufferGeometry().setFromPoints(arcPoints);
            const arcMat = new THREE.LineBasicMaterial({
                color: i % 2 === 0 ? 0xffb700 : 0xff2a4b,
                transparent: true,
                opacity: 0.9,
                linewidth: 2,
                blending: THREE.AdditiveBlending
            });

            const arcLine = new THREE.Line(arcGeo, arcMat);
            gyroGroup.add(arcLine);
            plasmaArcs.push(arcLine);
        }
    }

    function updatePlasmaArcs() {
        const t = themes[currentThemeName];
        plasmaArcs.forEach((arcLine, idx) => {
            arcLine.material.color.setHex(idx % 2 === 0 ? t.primary : t.secondary);
            const angle = (idx / arcCount) * Math.PI * 2 + Math.random() * 0.4;
            const targetRadius = 2.8 + Math.random() * 0.4;
            const targetPos = new THREE.Vector3(
                Math.cos(angle) * targetRadius,
                Math.sin(angle) * targetRadius,
                (Math.random() - 0.5) * 1.5
            );

            const points = [];
            const startPos = new THREE.Vector3(0, 0, 0);

            for (let s = 0; s <= 12; s++) {
                const lerpPos = new THREE.Vector3().lerpVectors(startPos, targetPos, s / 12);
                if (s > 0 && s < 12) {
                    lerpPos.x += (Math.random() - 0.5) * 0.35;
                    lerpPos.y += (Math.random() - 0.5) * 0.35;
                    lerpPos.z += (Math.random() - 0.5) * 0.35;
                }
                points.push(lerpPos);
            }
            arcLine.geometry.setFromPoints(points);
        });
    }

    function triggerPulseWave() {
        const t = themes[currentThemeName];
        const pulseGeo = new THREE.RingGeometry(0.5, 0.7, 36);
        const pulseMat = new THREE.MeshBasicMaterial({
            color: t.primary,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 1.0,
            blending: THREE.AdditiveBlending
        });

        const pulseMesh = new THREE.Mesh(pulseGeo, pulseMat);
        pulseMesh.rotation.x = Math.PI / 2;
        gyroGroup.add(pulseMesh);

        shockwavePulses.push({
            mesh: pulseMesh,
            scale: 0.5,
            opacity: 1.0
        });
    }

    function updateShockwavePulses() {
        for (let i = shockwavePulses.length - 1; i >= 0; i--) {
            const p = shockwavePulses[i];
            p.scale += 0.15;
            p.opacity -= 0.035;

            p.mesh.scale.set(p.scale, p.scale, p.scale);
            p.mesh.material.opacity = Math.max(0, p.opacity);

            if (p.opacity <= 0) {
                gyroGroup.remove(p.mesh);
                p.mesh.geometry.dispose();
                p.mesh.material.dispose();
                shockwavePulses.splice(i, 1);
            }
        }
    }

    function setupHoverListeners(element) {
        element.addEventListener('pointerenter', () => { isHovered = true; });
        element.addEventListener('pointerleave', () => { isHovered = false; });
        element.addEventListener('click', () => { triggerPulseWave(); });
    }

    function buildRadialEqualizerRing() {
        const tickCount = 64;
        const positions = new Float32Array(tickCount * 6);
        const radius = 5.8;

        for (let i = 0; i < tickCount; i++) {
            const angle = (i / tickCount) * Math.PI * 2;
            const x1 = Math.cos(angle) * radius;
            const y1 = Math.sin(angle) * radius;
            const len = 0.25 + Math.random() * 0.35;
            const x2 = Math.cos(angle) * (radius + len);
            const y2 = Math.sin(angle) * (radius + len);

            positions[i * 6] = x1;
            positions[i * 6 + 1] = y1;
            positions[i * 6 + 2] = 0;
            positions[i * 6 + 3] = x2;
            positions[i * 6 + 4] = y2;
            positions[i * 6 + 5] = 0;
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const mat = new THREE.LineBasicMaterial({
            color: 0xffb700,
            transparent: true,
            opacity: 0.85,
            linewidth: 2,
            blending: THREE.AdditiveBlending
        });

        radialEqualizerRing = new THREE.LineSegments(geo, mat);
        radialEqualizerRing.rotation.x = Math.PI / 2.5;
        gyroGroup.add(radialEqualizerRing);
    }

    function buildBackgroundLaserWave() {
        const points = [];
        for (let i = 0; i <= 180; i++) {
            const x = (i / 180 - 0.5) * 32;
            const y = Math.sin(i * 0.08) * 0.9 - 0.2;
            points.push(new THREE.Vector3(x, y, -2.5));
        }

        const geo = new THREE.BufferGeometry().setFromPoints(points);
        const mat = new THREE.LineBasicMaterial({
            color: 0xff2a4b,
            transparent: true,
            opacity: 0.45,
            linewidth: 2,
            blending: THREE.AdditiveBlending
        });

        horizontalLaserWave = new THREE.Line(geo, mat);
        scene.add(horizontalLaserWave);
    }

    function buildMechanicalGimbalRings() {
        const goldMat = new THREE.MeshStandardMaterial({
            color: 0xffb700,
            metalness: 0.95,
            roughness: 0.15,
        });

        const darkMetalMat = new THREE.MeshStandardMaterial({
            color: 0x241410,
            metalness: 0.90,
            roughness: 0.3,
        });

        const holoRedWire = new THREE.MeshBasicMaterial({
            color: 0xff2a4b,
            wireframe: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });

        outerRingGroup = new THREE.Group();
        const outerGeo = new THREE.TorusGeometry(4.9, 0.23, 24, 120);
        outerMesh = new THREE.Mesh(outerGeo, goldMat);
        outerRingGroup.add(outerMesh);

        for (let i = 0; i < 36; i++) {
            const angle = (i / 36) * Math.PI * 2;
            const toothGeo = new THREE.BoxGeometry(0.14, 0.22, 0.40);
            const tooth = new THREE.Mesh(toothGeo, darkMetalMat);
            tooth.position.set(Math.cos(angle) * 4.65, Math.sin(angle) * 4.65, 0);
            tooth.rotation.z = angle + Math.PI / 2;
            outerRingGroup.add(tooth);
        }
        gyroGroup.add(outerRingGroup);

        middleRingGroup = new THREE.Group();
        const middleGeo = new THREE.TorusGeometry(3.9, 0.21, 24, 120);
        middleMesh = new THREE.Mesh(middleGeo, goldMat);
        middleRingGroup.add(middleMesh);

        const middleWireGeo = new THREE.TorusGeometry(3.92, 0.22, 10, 70);
        middleWire = new THREE.Mesh(middleWireGeo, holoRedWire);
        middleRingGroup.add(middleWire);

        middleRingGroup.rotation.x = Math.PI / 3;
        middleRingGroup.rotation.y = Math.PI / 6;
        gyroGroup.add(middleRingGroup);

        innerRingGroup = new THREE.Group();
        const innerGeo = new THREE.TorusGeometry(2.95, 0.19, 24, 120);
        innerMesh = new THREE.Mesh(innerGeo, goldMat);
        innerRingGroup.add(innerMesh);

        innerRingGroup.rotation.x = -Math.PI / 4;
        gyroGroup.add(innerRingGroup);
    }

    function buildUltraDetailedCore() {
        const nucGeo = new THREE.SphereGeometry(0.85, 32, 32);
        const nucMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        coreNucleus = new THREE.Mesh(nucGeo, nucMat);
        gyroGroup.add(coreNucleus);

        const sunGeo = new THREE.SphereGeometry(1.25, 32, 32);
        const sunMat = new THREE.MeshBasicMaterial({
            color: 0xffb700,
            transparent: true,
            opacity: 0.85
        });
        coreGoldSun = new THREE.Mesh(sunGeo, sunMat);
        gyroGroup.add(coreGoldSun);

        const redShellGeo = new THREE.SphereGeometry(1.7, 32, 32);
        const redShellMat = new THREE.MeshPhongMaterial({
            color: 0xff2a4b,
            emissive: 0xff1e3c,
            emissiveIntensity: 0.7,
            transparent: true,
            opacity: 0.55,
            blending: THREE.AdditiveBlending
        });
        coreRedShell = new THREE.Mesh(redShellGeo, redShellMat);
        gyroGroup.add(coreRedShell);

        const cageGeo = new THREE.IcosahedronGeometry(1.98, 2);
        const cageMat = new THREE.MeshStandardMaterial({
            color: 0xffb700,
            metalness: 0.95,
            roughness: 0.15,
            wireframe: true
        });
        coreGeodesicCage = new THREE.Mesh(cageGeo, cageMat);
        gyroGroup.add(coreGeodesicCage);

        const goldWireMat = new THREE.MeshBasicMaterial({
            color: 0xffb700,
            wireframe: true,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending
        });

        for (let r = 0; r < 3; r++) {
            const ringGeo = new THREE.TorusGeometry(1.3 + r * 0.32, 0.04, 12, 80);
            const ringMesh = new THREE.Mesh(ringGeo, goldWireMat);
            ringMesh.rotation.x = Math.PI / 2 + r * 0.5;
            ringMesh.rotation.y = r * 0.8;
            gyroGroup.add(ringMesh);
            coreRingGears.push(ringMesh);
        }

        const particleCount = 650;
        const particleGeo = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);

        const cRed = new THREE.Color(0xff2a4b);
        const cGold = new THREE.Color(0xffb700);
        const cWhite = new THREE.Color(0xffffff);

        for (let i = 0; i < particleCount; i++) {
            const radius = 1.35 + Math.random() * 2.6;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;

            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi);

            const rand = Math.random();
            const c = rand > 0.5 ? cGold : (rand > 0.2 ? cRed : cWhite);
            colors[i * 3] = c.r;
            colors[i * 3 + 1] = c.g;
            colors[i * 3 + 2] = c.b;
        }

        particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const particleMat = new THREE.PointsMaterial({
            size: 0.14,
            vertexColors: true,
            transparent: true,
            opacity: 0.95,
            blending: THREE.AdditiveBlending
        });

        particleSwarm = new THREE.Points(particleGeo, particleMat);
        gyroGroup.add(particleSwarm);
    }

    function buildPedestalBase() {
        pedestalGroup = new THREE.Group();
        pedestalGroup.position.set(0, -5.8, 0);

        const baseGeo = new THREE.CylinderGeometry(3.4, 4.2, 0.75, 36);
        const baseMat = new THREE.MeshStandardMaterial({
            color: 0x1f120c,
            metalness: 0.95,
            roughness: 0.2
        });
        const baseMesh = new THREE.Mesh(baseGeo, baseMat);
        pedestalGroup.add(baseMesh);

        const ringGeo = new THREE.TorusGeometry(3.2, 0.08, 12, 80);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0xffb700 });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        ringMesh.rotation.x = Math.PI / 2;
        ringMesh.position.y = 0.38;
        pedestalGroup.add(ringMesh);

        const beamGeo = new THREE.CylinderGeometry(1.6, 3.2, 4.8, 32, 1, true);
        const beamMat = new THREE.MeshBasicMaterial({
            color: 0xffb700,
            transparent: true,
            opacity: 0.15,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending
        });
        const beamMesh = new THREE.Mesh(beamGeo, beamMat);
        beamMesh.position.y = 2.4;
        pedestalGroup.add(beamMesh);

        scene.add(pedestalGroup);
    }

    function setupDragControls(element) {
        element.addEventListener('pointerdown', (e) => {
            isDragging = true;
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('pointermove', (e) => {
            if (!isDragging) return;

            const deltaX = e.clientX - previousMousePosition.x;
            const deltaY = e.clientY - previousMousePosition.y;

            targetRotationY += deltaX * 0.008;
            targetRotationX += deltaY * 0.008;

            previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('pointerup', () => { isDragging = false; });
    }

    function onWindowResize() {
        const container = document.getElementById('canvas-3d-wrapper');
        if (!container || !renderer || !camera) return;

        const width = container.clientWidth || window.innerWidth;
        const height = container.clientHeight || (window.innerHeight - 140);

        if (width > 0 && height > 0) {
            camera.aspect = width / height;
            camera.updateProjectionMatrix();
            // 3. parametre false: three.js canvas'a satır içi px genişlik YAZMASIN.
            // Yazarsa CSS'teki %100 ezilir ve kutu son boyutta kilitlenir.
            renderer.setSize(width, height, false);
        }
    }

    function animate() {
        requestAnimationFrame(animate);

        // Odak sayfası görünmüyorken çizim yapma (boşuna GPU/CPU yakmasın).
        if (window.__ultronPaused) return;

        const time = clock.getElapsedTime();

        // 3D Motion Acceleration during TYPING or PROCESSING
        const isTyping = window.ultronCoreState === 'TYPING';
        const isProcessing = window.ultronCoreState === 'PROCESSING';
        const isActive = isTyping || isProcessing;

        targetGroupScale = isActive ? 0.98 : (isHovered ? 0.95 : 0.90);
        currentGroupScale += (targetGroupScale - currentGroupScale) * 0.08;
        gyroGroup.scale.set(currentGroupScale, currentGroupScale, currentGroupScale);

        currentRotationX += (targetRotationX - currentRotationX) * 0.08;
        currentRotationY += (targetRotationY - currentRotationY) * 0.08;

        gyroGroup.rotation.x = currentRotationX;
        gyroGroup.rotation.y = currentRotationY;

        if (outerMasterSphere) outerMasterSphere.rotation.y += 0.002;

        const mult = isProcessing ? 2.8 : (isTyping ? 1.8 : 1.0);

        if (outerRingGroup) outerRingGroup.rotation.z += 0.006 * mult;
        if (middleRingGroup) middleRingGroup.rotation.x += 0.009 * mult;
        if (innerRingGroup) innerRingGroup.rotation.y += 0.014 * mult;

        if (coreNucleus) {
            const pulseSpeed = isTyping ? 12 : 5;
            const s = 0.95 + Math.sin(time * pulseSpeed) * (isTyping ? 0.12 : 0.07);
            coreNucleus.scale.set(s, s, s);
        }
        if (coreGoldSun) {
            const s2 = 1.0 + Math.cos(time * 3) * 0.06;
            coreGoldSun.scale.set(s2, s2, s2);
        }
        if (coreGeodesicCage) {
            coreGeodesicCage.rotation.y -= 0.01 * mult;
            coreGeodesicCage.rotation.z += 0.005 * mult;
        }

        coreRingGears.forEach((ring, idx) => {
            ring.rotation.z += (idx % 2 === 0 ? 0.02 : -0.025) * mult;
        });

        // Trigger plasma arcs more frequently when typing!
        const arcProbability = isTyping ? 0.75 : 0.3;
        if (Math.random() < arcProbability) {
            updatePlasmaArcs();
        }

        updateShockwavePulses();

        if (radialEqualizerRing) {
            radialEqualizerRing.rotation.z += 0.008 * mult;
        }

        if (particleSwarm) {
            particleSwarm.rotation.y += 0.008 * mult;
        }

        renderer.render(scene, camera);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init3D);
    } else {
        init3D();
    }
})();
