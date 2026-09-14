/**
 * TRINETRA-AERO Simulator Operator Console Client Script
 * Connects to ws://127.0.0.1:8765/control
 * Handles bidirectional telemetry display, parameter injection,
 * and real-time interactive 3D tactical drone spatial attitude visualization.
 */

(function () {
  let ws = null;
  let activeFaults = {};
  let controlsState = {};
  let isSimRunning = true;
  let startTime = Date.now();

  // DOM Elements - Header
  const elHdrBroadcast = document.getElementById('hdr-broadcast-status');
  const elHdrClients = document.getElementById('hdr-clients-count');
  const elHdrPackets = document.getElementById('hdr-packets-sent');
  const elHdrSimTime = document.getElementById('hdr-sim-time');
  const elBtnToggleSim = document.getElementById('btn-toggle-sim');

  // DOM Elements - Sliders & Labels
  const sliderThrottle = document.getElementById('slider-throttle');
  const valThrottle = document.getElementById('val-throttle');
  const sliderAltitude = document.getElementById('slider-altitude');
  const valAltitude = document.getElementById('val-altitude');
  const sliderAmbientTemp = document.getElementById('slider-ambient-temp');
  const valAmbientTemp = document.getElementById('val-ambient-temp');
  const sliderWindSpeed = document.getElementById('slider-wind-speed');
  const valWindSpeed = document.getElementById('val-wind-speed');
  const sliderEngineLoad = document.getElementById('slider-engine-load');
  const valEngineLoad = document.getElementById('val-engine-load');

  // DOM Elements - Telemetry Display
  const telRpm = document.getElementById('tel-rpm');
  const barRpm = document.getElementById('bar-rpm');
  const telPower = document.getElementById('tel-power-kw');
  const telMap = document.getElementById('tel-map');
  const barMap = document.getElementById('bar-map');
  const telFuelFlow = document.getElementById('tel-fuel-flow');
  const telOilPress = document.getElementById('tel-oil-press');
  const barOilPress = document.getElementById('bar-oil-press');
  const telOilTemp = document.getElementById('tel-oil-temp');
  const telCoolant = document.getElementById('tel-coolant');
  const barCoolant = document.getElementById('bar-coolant');
  const telVibration = document.getElementById('tel-vibration');

  // Multi-cylinder DOM elements
  const cylCards = [1, 2, 3, 4].map(i => document.getElementById(`card-cyl-${i}`));
  const telChts = [1, 2, 3, 4].map(i => document.getElementById(`tel-cht-${i}`));
  const barChts = [1, 2, 3, 4].map(i => document.getElementById(`bar-cht-${i}`));
  const telEgts = [1, 2, 3, 4].map(i => document.getElementById(`tel-egt-${i}`));
  const barEgts = [1, 2, 3, 4].map(i => document.getElementById(`bar-egt-${i}`));

  // Reset All Faults Button
  const btnClearAll = document.getElementById('btn-clear-all-faults');

  // 3D Drone Viewport HUD Elements
  const hudPitch = document.getElementById('hud-pitch');
  const hudRoll = document.getElementById('hud-roll');
  const hudThrottle = document.getElementById('hud-throttle');
  const hudFaultAlert = document.getElementById('hud-fault-alert');
  const hudAlertText = document.getElementById('hud-alert-text');
  const btnDroneReset = document.getElementById('btn-drone-reset');
  const btnDroneSpin = document.getElementById('btn-drone-spin');

  // Current live telemetry cache for 3D physics
  let currentThrottle = 72;
  let currentRpm = 4800;
  let currentWind = 12;

  // =========================================================================
  // 3D DRONE MODEL & SPATIAL ENGINE (THREE.JS)
  // =========================================================================
  const DroneViewer = {
    renderer: null,
    scene: null,
    camera: null,
    droneGroup: null,
    rotors: [],
    engineCoreLight: null,
    beaconLight: null,
    autoRotate: true,
    targetDistance: 5.2,
    distance: 5.2,
    rotX: 0.35,
    rotY: -0.65,
    targetRotX: 0.35,
    targetRotY: -0.65,
    isDragging: false,
    prevMouseX: 0,
    prevMouseY: 0,
    animTime: 0,

    init: function () {
      const canvas = document.getElementById('drone-3d-canvas');
      const wrap = document.getElementById('drone-canvas-wrap');
      if (!canvas || !wrap || typeof THREE === 'undefined') return;

      const w = wrap.clientWidth || 600;
      const h = wrap.clientHeight || 270;

      // Renderer
      this.renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance'
      });
      this.renderer.setSize(w, h, false);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

      // Scene
      this.scene = new THREE.Scene();

      // Camera
      this.camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 100);
      this.updateCameraPos();

      // Lighting (High-Intensity Multi-Angle Aerospace Studio)
      const ambientLight = new THREE.AmbientLight(0xffffff, 1.4);
      this.scene.add(ambientLight);

      const dirLight = new THREE.DirectionalLight(0xffffff, 2.4);
      dirLight.position.set(8, 12, 10);
      this.scene.add(dirLight);

      const fillLight = new THREE.DirectionalLight(0x38bdf8, 1.0);
      fillLight.position.set(-8, -4, -8);
      this.scene.add(fillLight);

      const topLight = new THREE.DirectionalLight(0xFACC15, 0.7);
      topLight.position.set(0, 10, 0);
      this.scene.add(topLight);

      // Core engine glow light (amber/yellow nominal, pulses red on fault)
      this.engineCoreLight = new THREE.PointLight(0xFACC15, 2.0, 8);
      this.engineCoreLight.position.set(0, 0.3, -0.3);
      this.scene.add(this.engineCoreLight);

      // Strobe beacon light
      this.beaconLight = new THREE.PointLight(0xffffff, 1.2, 5);
      this.beaconLight.position.set(0, 0.7, -1.1);
      this.scene.add(this.beaconLight);

      // Ground plane grid for flight perspective
      this.grid = new THREE.GridHelper(20, 24, 0x38BDF8, 0x1E293B);
      this.grid.position.y = -1.6;
      this.scene.add(this.grid);

      // Construct 3D Drone Model
      this.buildDroneModel();

      // Setup Mouse Orbit Controls
      this.setupControls(wrap);

      // Handle Resize
      window.addEventListener('resize', () => this.onResize());

      // Start Render Loop
      this.animate();
    },

    updateTheme: function (isLight) {
      if (!this.scene) return;
      if (this.grid) {
        this.scene.remove(this.grid);
      }
      this.grid = new THREE.GridHelper(20, 24, isLight ? 0x475569 : 0x38BDF8, isLight ? 0x94A3B8 : 0x1E293B);
      this.grid.position.y = -1.6;
      this.scene.add(this.grid);
    },

    buildDroneModel: function () {
      this.droneGroup = new THREE.Group();

      // 1. High-Contrast Aerospace Composite Materials
      const fuselageMat = new THREE.MeshStandardMaterial({
        color: 0xF1F5F9,
        roughness: 0.25,
        metalness: 0.25
      });

      const wingMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        roughness: 0.35,
        metalness: 0.5
      });

      const accentMat = new THREE.MeshStandardMaterial({
        color: 0xFACC15,
        roughness: 0.2,
        metalness: 0.7,
        emissive: 0x92400E,
        emissiveIntensity: 0.3
      });

      const glassMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        roughness: 0.1,
        metalness: 0.9,
        emissive: 0x0369a1,
        emissiveIntensity: 0.4
      });

      const metalMat = new THREE.MeshStandardMaterial({
        color: 0x94A3B8,
        roughness: 0.2,
        metalness: 0.9
      });

      const bladeMat = new THREE.MeshStandardMaterial({
        color: 0x1E293B,
        roughness: 0.25,
        metalness: 0.4
      });

      // 2. Central Fuselage Body (Tapered Tactical Drone)
      const bodyGeo = new THREE.CylinderGeometry(0.35, 0.48, 2.6, 16);
      bodyGeo.rotateX(Math.PI / 2);
      const body = new THREE.Mesh(bodyGeo, fuselageMat);
      body.scale.set(1.1, 0.65, 1);
      this.droneGroup.add(body);

      // Top Avionics Spine
      const spineGeo = new THREE.BoxGeometry(0.32, 0.22, 1.8);
      const spine = new THREE.Mesh(spineGeo, accentMat);
      spine.position.set(0, 0.22, -0.1);
      this.droneGroup.add(spine);

      // 3. Nose Optical/FLIR Sensor Turret
      const noseGeo = new THREE.SphereGeometry(0.34, 16, 16);
      const nose = new THREE.Mesh(noseGeo, glassMat);
      nose.position.set(0, -0.05, 1.35);
      this.droneGroup.add(nose);

      // 4. Tactical Tail Fin
      const finGeo = new THREE.BoxGeometry(0.06, 0.75, 0.6);
      const fin = new THREE.Mesh(finGeo, accentMat);
      fin.position.set(0, 0.45, -1.1);
      this.droneGroup.add(fin);

      // 5. 4 Rotor Arms (X-Configuration)
      const armLength = 1.9;
      const armAngles = [
        Math.PI * 0.25,   // Front Right
        Math.PI * 0.75,   // Back Right
        Math.PI * 1.25,   // Back Left
        Math.PI * 1.75    // Front Left
      ];

      this.rotors = [];

      armAngles.forEach((angle, idx) => {
        const armGroup = new THREE.Group();
        const armGeo = new THREE.CylinderGeometry(0.07, 0.09, armLength, 8);
        armGeo.rotateZ(Math.PI / 2);
        const arm = new THREE.Mesh(armGeo, wingMat);
        arm.position.x = armLength / 2;
        armGroup.add(arm);

        armGroup.rotation.y = angle;
        this.droneGroup.add(armGroup);

        // Motor Hub at end of arm
        const motorGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.28, 12);
        const motor = new THREE.Mesh(motorGeo, metalMat);
        const motorX = Math.cos(angle) * armLength;
        const motorZ = -Math.sin(angle) * armLength;
        motor.position.set(motorX, 0.08, motorZ);
        this.droneGroup.add(motor);

        // Propeller Disc / Rotor Blades
        const rotorGroup = new THREE.Group();
        rotorGroup.position.set(motorX, 0.25, motorZ);

        // Center hub spinner
        const spinnerGeo = new THREE.ConeGeometry(0.09, 0.16, 8);
        const spinner = new THREE.Mesh(spinnerGeo, accentMat);
        rotorGroup.add(spinner);

        // 3 Propeller blades with high-vis yellow tips
        for (let b = 0; b < 3; b++) {
          const bladeGeo = new THREE.BoxGeometry(0.09, 0.015, 0.85);
          const blade = new THREE.Mesh(bladeGeo, bladeMat);
          blade.position.z = 0.42;

          const tipGeo = new THREE.BoxGeometry(0.092, 0.018, 0.18);
          const tip = new THREE.Mesh(tipGeo, accentMat);
          tip.position.z = 0.33;
          blade.add(tip);

          const bladeHolder = new THREE.Group();
          bladeHolder.rotation.y = (b * Math.PI * 2) / 3;
          bladeHolder.add(blade);
          rotorGroup.add(bladeHolder);
        }

        this.droneGroup.add(rotorGroup);
        this.rotors.push({
          group: rotorGroup,
          direction: idx % 2 === 0 ? 1 : -1
        });

        // Navigation LEDs at wingtip
        let ledColor = 0xFACC15;
        if (angle < Math.PI) {
          ledColor = 0x10B981; // Right/Starboard = Green
        } else {
          ledColor = 0xEF4444; // Left/Port = Red
        }

        const ledGeo = new THREE.SphereGeometry(0.06, 8, 8);
        const ledMat = new THREE.MeshBasicMaterial({ color: ledColor });
        const led = new THREE.Mesh(ledGeo, ledMat);
        led.position.set(motorX, -0.08, motorZ);
        this.droneGroup.add(led);
      });

      // 6. Carbon Landing Skids
      const skidMat = new THREE.MeshStandardMaterial({ color: 0x1E293B, metalness: 0.7 });
      [-0.65, 0.65].forEach(x => {
        const skidGeo = new THREE.CylinderGeometry(0.04, 0.04, 2.2, 8);
        skidGeo.rotateX(Math.PI / 2);
        const skid = new THREE.Mesh(skidGeo, skidMat);
        skid.position.set(x, -0.48, 0);
        this.droneGroup.add(skid);

        // Skid struts
        [-0.6, 0.6].forEach(z => {
          const strutGeo = new THREE.CylinderGeometry(0.035, 0.035, 0.45, 8);
          const strut = new THREE.Mesh(strutGeo, skidMat);
          strut.position.set(x, -0.25, z);
          this.droneGroup.add(strut);
        });
      });

      this.scene.add(this.droneGroup);
    },

    setupControls: function (wrap) {
      wrap.addEventListener('mousedown', (e) => {
        this.isDragging = true;
        this.prevMouseX = e.clientX;
        this.prevMouseY = e.clientY;
      });

      window.addEventListener('mouseup', () => {
        this.isDragging = false;
      });

      window.addEventListener('mousemove', (e) => {
        if (!this.isDragging) return;
        const deltaX = e.clientX - this.prevMouseX;
        const deltaY = e.clientY - this.prevMouseY;
        this.prevMouseX = e.clientX;
        this.prevMouseY = e.clientY;

        this.targetRotY += deltaX * 0.008;
        this.targetRotX += deltaY * 0.008;
        this.targetRotX = Math.max(-0.6, Math.min(1.2, this.targetRotX));
      });

      // Wheel Zoom
      wrap.addEventListener('wheel', (e) => {
        e.preventDefault();
        this.targetDistance += e.deltaY * 0.006;
        this.targetDistance = Math.max(5.0, Math.min(16.0, this.targetDistance));
      }, { passive: false });

      // Touch Controls for mobile/tablets
      wrap.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
          this.isDragging = true;
          this.prevMouseX = e.touches[0].clientX;
          this.prevMouseY = e.touches[0].clientY;
        }
      });

      window.addEventListener('touchend', () => {
        this.isDragging = false;
      });

      window.addEventListener('touchmove', (e) => {
        if (!this.isDragging || e.touches.length !== 1) return;
        const deltaX = e.touches[0].clientX - this.prevMouseX;
        const deltaY = e.touches[0].clientY - this.prevMouseY;
        this.prevMouseX = e.touches[0].clientX;
        this.prevMouseY = e.touches[0].clientY;

        this.targetRotY += deltaX * 0.01;
        this.targetRotX += deltaY * 0.01;
        this.targetRotX = Math.max(-0.6, Math.min(1.2, this.targetRotX));
      });

      // Reset Button
      if (btnDroneReset) {
        btnDroneReset.addEventListener('click', () => {
          this.targetRotX = 0.35;
          this.targetRotY = -0.65;
          this.targetDistance = 5.2;
        });
      }

      // Auto-Orbit Toggle Button
      if (btnDroneSpin) {
        btnDroneSpin.addEventListener('click', () => {
          this.autoRotate = !this.autoRotate;
          if (this.autoRotate) {
            btnDroneSpin.classList.add('active');
          } else {
            btnDroneSpin.classList.remove('active');
          }
        });
      }
    },

    updateCameraPos: function () {
      if (!this.camera) return;
      const x = this.distance * Math.sin(this.rotY) * Math.cos(this.rotX);
      const y = this.distance * Math.sin(this.rotX) + 0.5;
      const z = this.distance * Math.cos(this.rotY) * Math.cos(this.rotX);
      this.camera.position.set(x, y, z);
      this.camera.lookAt(0, 0.2, 0);
    },

    onResize: function () {
      const wrap = document.getElementById('drone-canvas-wrap');
      if (!wrap || !this.renderer || !this.camera) return;
      const w = wrap.clientWidth;
      const h = wrap.clientHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h, false);
    },

    animate: function () {
      requestAnimationFrame(() => this.animate());
      this.animTime += 0.016;

      // Smooth camera interpolation
      if (this.autoRotate && !this.isDragging) {
        this.targetRotY += 0.0035;
      }
      this.rotX += (this.targetRotX - this.rotX) * 0.08;
      this.rotY += (this.targetRotY - this.rotY) * 0.08;
      this.distance += (this.targetDistance - this.distance) * 0.08;
      this.updateCameraPos();

      // Drone flight kinematics (subtle hovering & pitch)
      if (this.droneGroup) {
        const hoverY = Math.sin(this.animTime * 2.5) * 0.08;
        const windRoll = Math.sin(this.animTime * 1.8) * 0.02 * (currentWind / 15);
        const throttlePitch = -0.04 * (currentThrottle / 100);

        this.droneGroup.position.y = hoverY;
        this.droneGroup.rotation.x = throttlePitch + Math.sin(this.animTime * 1.4) * 0.015;
        this.droneGroup.rotation.z = windRoll;

        // Update HUD readout
        if (hudPitch) hudPitch.textContent = `${(this.droneGroup.rotation.x * (180 / Math.PI)).toFixed(1)}°`;
        if (hudRoll) hudRoll.textContent = `${(this.droneGroup.rotation.z * (180 / Math.PI)).toFixed(1)}°`;
      }

      // Propeller rotation linked to throttle & RPM
      const rotorSpeed = 0.15 + (currentThrottle / 100) * 0.85;
      this.rotors.forEach(r => {
        r.group.rotation.y += rotorSpeed * r.direction;
      });

      // Beacon strobe pulse
      if (this.beaconLight) {
        this.beaconLight.intensity = 0.5 + 0.5 * Math.sin(this.animTime * 8);
      }

      // Fault visual alerting
      const faultCount = Object.keys(activeFaults).length;
      if (faultCount > 0) {
        const pulse = 0.5 + 0.5 * Math.sin(this.animTime * 10);
        if (this.engineCoreLight) {
          this.engineCoreLight.color.setHex(0xEF4444);
          this.engineCoreLight.intensity = 2.0 * pulse;
        }
        if (hudFaultAlert) {
          hudFaultAlert.style.display = 'flex';
          const firstFault = Object.keys(activeFaults)[0].toUpperCase().replace('_', ' ');
          if (hudAlertText) hudAlertText.textContent = `CRITICAL FAULT: ${firstFault}`;
        }
      } else {
        if (this.engineCoreLight) {
          this.engineCoreLight.color.setHex(0xFACC15);
          this.engineCoreLight.intensity = 1.2;
        }
        if (hudFaultAlert) hudFaultAlert.style.display = 'none';
      }

      this.renderer.render(this.scene, this.camera);
    }
  };

  // =========================================================================
  // WEBSOCKET TELEMETRY & COMMAND CLIENT
  // =========================================================================
  function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/control`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function () {
      if (elHdrBroadcast) {
        elHdrBroadcast.textContent = '10 Hz LIVE';
        elHdrBroadcast.style.color = '#39D353';
      }
    };

    ws.onmessage = function (event) {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'state_sync') {
          controlsState = msg.controls || {};
          activeFaults = msg.active_faults || {};
          updateControlSlidersUI();
          updateFaultButtonsUI();
        } else if (msg.type === 'telemetry_frame') {
          renderTelemetryFrame(msg.packet, msg.stats);
        }
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    ws.onclose = function () {
      if (elHdrBroadcast) {
        elHdrBroadcast.textContent = 'DISCONNECTED';
        elHdrBroadcast.style.color = '#EF4444';
      }
      setTimeout(initWebSocket, 1000);
    };

    ws.onerror = function () {
      ws.close();
    };
  }

  function sendCommand(cmd) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(cmd));
    }
  }

  // Update control sliders from state
  function updateControlSlidersUI() {
    if (controlsState.throttle_pct !== undefined) {
      sliderThrottle.value = controlsState.throttle_pct;
      valThrottle.textContent = `${Math.round(controlsState.throttle_pct)}%`;
      currentThrottle = controlsState.throttle_pct;
      if (hudThrottle) hudThrottle.textContent = `${Math.round(currentThrottle)}%`;
    }
    if (controlsState.altitude_ft !== undefined) {
      sliderAltitude.value = controlsState.altitude_ft;
      valAltitude.textContent = `${Number(controlsState.altitude_ft).toLocaleString()} ft`;
    }
    if (controlsState.ambient_temp_c !== undefined) {
      sliderAmbientTemp.value = controlsState.ambient_temp_c;
      valAmbientTemp.textContent = `${Number(controlsState.ambient_temp_c).toFixed(1)} °C`;
    }
    if (controlsState.wind_speed_mps !== undefined) {
      sliderWindSpeed.value = controlsState.wind_speed_mps;
      valWindSpeed.textContent = `${Math.round(controlsState.wind_speed_mps)} m/s`;
      currentWind = controlsState.wind_speed_mps;
    }
    if (controlsState.engine_load !== undefined) {
      sliderEngineLoad.value = controlsState.engine_load;
      valEngineLoad.textContent = `${Number(controlsState.engine_load).toFixed(2)}x`;
    }
  }

  // Update fault cards and buttons state
  function updateFaultButtonsUI() {
    document.querySelectorAll('.fault-item').forEach(item => {
      const faultKey = item.id.replace('fault-item-', '');
      const btn = item.querySelector('.btn-fault-toggle');
      const isActive = Boolean(activeFaults[faultKey]);

      if (isActive) {
        item.classList.add('active-fault');
        if (btn) {
          btn.classList.add('active');
          btn.textContent = 'ACTIVE';
        }
      } else {
        item.classList.remove('active-fault');
        if (btn) {
          btn.classList.remove('active');
          btn.textContent = 'INJECT';
        }
      }
    });
  }

  // Render incoming high-frequency telemetry frame
  function renderTelemetryFrame(packet, stats) {
    if (!packet || !packet.telemetry) return;
    const t = packet.telemetry;

    // Header stats
    if (stats) {
      if (elHdrClients) elHdrClients.textContent = stats.clients_connected || 0;
      if (elHdrPackets) elHdrPackets.textContent = (stats.packets_sent || 0).toLocaleString();
    }

    // RPM & Power
    currentRpm = t.rpm;
    if (telRpm) telRpm.textContent = Math.round(t.rpm);
    const rpmPct = Math.min(100, Math.max(0, (t.rpm / 5800) * 100));
    if (barRpm) barRpm.style.width = `${rpmPct}%`;

    const powerKw = packet.telemetry.power_kw || ((t.rpm * 0.015) * (t.map_kpa / 100));
    const powerHp = (powerKw * 1.341).toFixed(1);
    if (telPower) telPower.textContent = `${Number(powerKw).toFixed(1)} kW (${powerHp} HP)`;

    // MAP & Fuel Flow
    if (telMap) telMap.textContent = t.map_kpa.toFixed(1);
    const mapPct = Math.min(100, Math.max(0, ((t.map_kpa - 30) / 80) * 100));
    if (barMap) barMap.style.width = `${mapPct}%`;
    if (telFuelFlow) telFuelFlow.textContent = `${t.fuel_flow_lph.toFixed(1)} L/h`;

    // Lubrication
    if (telOilPress) telOilPress.textContent = t.oil_pressure_bar.toFixed(2);
    if (telOilTemp) telOilTemp.textContent = t.oil_temp_c.toFixed(1);
    const oilPressPct = Math.min(100, Math.max(0, (t.oil_pressure_bar / 6.5) * 100));
    if (barOilPress) barOilPress.style.width = `${oilPressPct}%`;

    // Color code oil pressure warning
    if (t.oil_pressure_bar < 2.0) {
      if (barOilPress) barOilPress.style.background = '#EF4444';
      if (telOilPress) telOilPress.style.color = '#EF4444';
    } else {
      if (barOilPress) barOilPress.style.background = '#39D353';
      if (telOilPress) telOilPress.style.color = '#FFFFFF';
    }

    // Coolant & Vibration
    if (telCoolant) telCoolant.textContent = t.coolant_temp_c.toFixed(1);
    const coolPct = Math.min(100, Math.max(0, ((t.coolant_temp_c - 40) / 90) * 100));
    if (barCoolant) barCoolant.style.width = `${coolPct}%`;
    if (t.coolant_temp_c > 110) {
      if (barCoolant) barCoolant.style.background = '#EF4444';
    } else {
      if (barCoolant) barCoolant.style.background = '#FACC15';
    }

    const vibVal = t.vibration ? t.vibration.rms : 0.5;
    if (telVibration) {
      telVibration.textContent = vibVal.toFixed(2);
      if (vibVal > 3.0) {
        telVibration.style.color = '#EF4444';
      } else {
        telVibration.style.color = '#FFFFFF';
      }
    }

    // 4 Cylinders
    if (t.cht && t.cht.length >= 4) {
      for (let i = 0; i < 4; i++) {
        if (telChts[i]) telChts[i].textContent = `${t.cht[i].toFixed(1)} °C`;
        const chtPct = Math.min(100, Math.max(0, ((t.cht[i] - 50) / 100) * 100));
        if (barChts[i]) {
          barChts[i].style.width = `${chtPct}%`;
          barChts[i].style.background = t.cht[i] > 135 ? '#EF4444' : '#FACC15';
        }
      }
    }

    if (t.egt && t.egt.length >= 4) {
      for (let i = 0; i < 4; i++) {
        if (telEgts[i]) telEgts[i].textContent = `${Math.round(t.egt[i])} °C`;
        const egtPct = Math.min(100, Math.max(0, ((t.egt[i] - 400) / 550) * 100));
        if (barEgts[i]) {
          barEgts[i].style.width = `${egtPct}%`;
          barEgts[i].style.background = (t.egt[i] > 840 || t.egt[i] < 550) ? '#EF4444' : '#FACC15';
        }
      }
    }

    // Highlight cylinder cards if target cylinder fault active
    for (let i = 0; i < 4; i++) {
      const cylNum = i + 1;
      let cylHasFault = false;
      for (const [fName, fData] of Object.entries(activeFaults)) {
        if (fData && fData.target_cylinder === cylNum) {
          cylHasFault = true;
          break;
        }
      }
      if (cylCards[i]) {
        if (cylHasFault) {
          cylCards[i].classList.add('card-fault');
        } else {
          cylCards[i].classList.remove('card-fault');
        }
      }
    }
  }

  // Mission Simulation Clock
  setInterval(function () {
    const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
    const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, '0');
    const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, '0');
    const secs = String(elapsedSec % 60).padStart(2, '0');
    if (elHdrSimTime) elHdrSimTime.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);

  // Setup Event Listeners for Controls
  function setupControlListeners() {
    // Throttle
    if (sliderThrottle) {
      sliderThrottle.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (valThrottle) valThrottle.textContent = `${Math.round(val)}%`;
        currentThrottle = val;
        if (hudThrottle) hudThrottle.textContent = `${Math.round(val)}%`;
        sendCommand({ action: 'set_controls', controls: { throttle_pct: val } });
      });
    }

    // Altitude
    if (sliderAltitude) {
      sliderAltitude.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (valAltitude) valAltitude.textContent = `${Number(val).toLocaleString()} ft`;
        sendCommand({ action: 'set_controls', controls: { altitude_ft: val } });
      });
    }

    // Ambient Temp
    if (sliderAmbientTemp) {
      sliderAmbientTemp.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (valAmbientTemp) valAmbientTemp.textContent = `${val.toFixed(1)} °C`;
        sendCommand({ action: 'set_controls', controls: { ambient_temp_c: val } });
      });
    }

    // Wind Speed
    if (sliderWindSpeed) {
      sliderWindSpeed.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (valWindSpeed) valWindSpeed.textContent = `${Math.round(val)} m/s`;
        currentWind = val;
        sendCommand({ action: 'set_controls', controls: { wind_speed_mps: val } });
      });
    }

    // Engine Load
    if (sliderEngineLoad) {
      sliderEngineLoad.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (valEngineLoad) valEngineLoad.textContent = `${val.toFixed(2)}x`;
        sendCommand({ action: 'set_controls', controls: { engine_load: val } });
      });
    }

    // Flight Phase Preset Buttons
    document.querySelectorAll('.btn-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const throttle = parseFloat(btn.dataset.throttle);
        const alt = parseFloat(btn.dataset.alt);
        const phase = btn.dataset.phase;

        if (sliderThrottle) sliderThrottle.value = throttle;
        if (valThrottle) valThrottle.textContent = `${Math.round(throttle)}%`;
        currentThrottle = throttle;
        if (hudThrottle) hudThrottle.textContent = `${Math.round(throttle)}%`;

        if (sliderAltitude) sliderAltitude.value = alt;
        if (valAltitude) valAltitude.textContent = `${Number(alt).toLocaleString()} ft`;

        sendCommand({
          action: 'set_controls',
          controls: {
            throttle_pct: throttle,
            altitude_ft: alt,
            flight_phase: phase
          }
        });
      });
    });

    // Fault Injection Toggle Buttons
    document.querySelectorAll('.btn-fault-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const faultKey = btn.dataset.fault;
        const isActive = Boolean(activeFaults[faultKey]);
        const slider = document.querySelector(`.fault-slider[data-fault="${faultKey}"]`);
        const severity = slider ? parseFloat(slider.value) : 0.75;

        if (isActive) {
          sendCommand({ action: 'clear_fault', fault_type: faultKey });
        } else {
          sendCommand({
            action: 'set_fault',
            fault_type: faultKey,
            severity: severity,
            target_cylinder: 3
          });
        }
      });
    });

    // Fault Severity Sliders
    document.querySelectorAll('.fault-slider').forEach(slider => {
      slider.addEventListener('input', (e) => {
        const faultKey = slider.dataset.fault;
        const val = parseFloat(e.target.value);
        const valLabel = document.getElementById(`sev-val-${faultKey}`);
        if (valLabel) valLabel.textContent = `${Math.round(val * 100)}%`;

        if (activeFaults[faultKey]) {
          sendCommand({
            action: 'set_fault',
            fault_type: faultKey,
            severity: val,
            target_cylinder: 3
          });
        }
      });
    });

    // Reset All Faults
    if (btnClearAll) {
      btnClearAll.addEventListener('click', () => {
        sendCommand({ action: 'clear_all_faults' });
      });
    }

    // Toggle Simulation
    if (elBtnToggleSim) {
      elBtnToggleSim.addEventListener('click', () => {
        isSimRunning = !isSimRunning;
        elBtnToggleSim.textContent = isSimRunning ? 'PAUSE SIM' : 'RESUME SIM';
        elBtnToggleSim.style.background = isSimRunning ? '' : 'rgba(57, 211, 83, 0.2)';
        elBtnToggleSim.style.color = isSimRunning ? '' : '#39D353';
        sendCommand({ action: 'toggle_simulation' });
      });
    }

    // Setup Light/Dark Mode Theme Toggle
    setupThemeToggle();
  }

  function setupThemeToggle() {
    const themeBtn = document.getElementById('theme-toggle');
    if (!themeBtn) return;
    const iconSun = themeBtn.querySelector('.theme-icon-sun');
    const iconMoon = themeBtn.querySelector('.theme-icon-moon');

    function applyTheme(theme) {
      const isLight = theme === 'light';
      if (isLight) {
        document.body.setAttribute('data-theme', 'light');
        if (iconSun) iconSun.style.display = 'block';
        if (iconMoon) iconMoon.style.display = 'none';
      } else {
        document.body.removeAttribute('data-theme');
        if (iconSun) iconSun.style.display = 'none';
        if (iconMoon) iconMoon.style.display = 'block';
      }
      DroneViewer.updateTheme(isLight);
    }

    const savedTheme = localStorage.getItem('sih_theme') || 'dark';
    applyTheme(savedTheme);

    themeBtn.addEventListener('click', () => {
      const isLight = document.body.getAttribute('data-theme') === 'light';
      const nextTheme = isLight ? 'dark' : 'light';
      applyTheme(nextTheme);
      localStorage.setItem('sih_theme', nextTheme);
    });
  }

  // Initialize on DOM load
  window.addEventListener('DOMContentLoaded', () => {
    DroneViewer.init();
    initWebSocket();
    setupControlListeners();
  });
})();
