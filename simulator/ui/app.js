/**
 * SIH26054 Simulator Operator Console Client Script
 * Connects to ws://127.0.0.1:8765/control
 * Handles bidirectional telemetry display and parameter injection
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

  function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/control`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function () {
      elHdrBroadcast.textContent = '10 Hz LIVE';
      elHdrBroadcast.style.color = '#39D353';
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
      elHdrBroadcast.textContent = 'DISCONNECTED';
      elHdrBroadcast.style.color = '#EF4444';
      // Auto-reconnect after 1 second
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
        btn.classList.add('active');
        btn.textContent = 'ACTIVE';
      } else {
        item.classList.remove('active-fault');
        btn.classList.remove('active');
        btn.textContent = 'INJECT';
      }
    });
  }

  // Render incoming high-frequency telemetry frame
  function renderTelemetryFrame(packet, stats) {
    if (!packet || !packet.telemetry) return;
    const t = packet.telemetry;

    // Header stats
    if (stats) {
      elHdrClients.textContent = stats.clients_connected || 0;
      elHdrPackets.textContent = (stats.packets_sent || 0).toLocaleString();
    }

    // RPM & Power
    telRpm.textContent = Math.round(t.rpm);
    const rpmPct = Math.min(100, Math.max(0, (t.rpm / 5800) * 100));
    barRpm.style.width = `${rpmPct}%`;

    const powerKw = packet.telemetry.power_kw || ((t.rpm * 0.015) * (t.map_kpa / 100));
    const powerHp = (powerKw * 1.341).toFixed(1);
    telPower.textContent = `${Number(powerKw).toFixed(1)} kW (${powerHp} HP)`;

    // MAP & Fuel Flow
    telMap.textContent = t.map_kpa.toFixed(1);
    const mapPct = Math.min(100, Math.max(0, ((t.map_kpa - 30) / 80) * 100));
    barMap.style.width = `${mapPct}%`;
    telFuelFlow.textContent = `${t.fuel_flow_lph.toFixed(1)} L/h`;

    // Lubrication
    telOilPress.textContent = t.oil_pressure_bar.toFixed(2);
    telOilTemp.textContent = t.oil_temp_c.toFixed(1);
    const oilPressPct = Math.min(100, Math.max(0, (t.oil_pressure_bar / 6.5) * 100));
    barOilPress.style.width = `${oilPressPct}%`;

    // Color code oil pressure warning
    if (t.oil_pressure_bar < 2.0) {
      barOilPress.style.background = '#EF4444';
      telOilPress.style.color = '#EF4444';
    } else {
      barOilPress.style.background = '#39D353';
      telOilPress.style.color = '#FFFFFF';
    }

    // Coolant & Vibration
    telCoolant.textContent = t.coolant_temp_c.toFixed(1);
    const coolPct = Math.min(100, Math.max(0, ((t.coolant_temp_c - 40) / 90) * 100));
    barCoolant.style.width = `${coolPct}%`;
    if (t.coolant_temp_c > 110) {
      barCoolant.style.background = '#EF4444';
    } else {
      barCoolant.style.background = '#94A3B8';
    }

    const vibVal = t.vibration ? t.vibration.rms : 0.5;
    telVibration.textContent = vibVal.toFixed(2);
    if (vibVal > 3.0) {
      telVibration.style.color = '#EF4444';
    } else {
      telVibration.style.color = '#FFFFFF';
    }

    // 4 Cylinders
    if (t.cht && t.cht.length >= 4) {
      for (let i = 0; i < 4; i++) {
        telChts[i].textContent = `${t.cht[i].toFixed(1)} °C`;
        const chtPct = Math.min(100, Math.max(0, ((t.cht[i] - 50) / 100) * 100));
        barChts[i].style.width = `${chtPct}%`;
        if (t.cht[i] > 135) {
          barChts[i].style.background = '#EF4444';
        } else {
          barChts[i].style.background = '#FACC15';
        }
      }
    }

    if (t.egt && t.egt.length >= 4) {
      for (let i = 0; i < 4; i++) {
        telEgts[i].textContent = `${Math.round(t.egt[i])} °C`;
        const egtPct = Math.min(100, Math.max(0, ((t.egt[i] - 400) / 550) * 100));
        barEgts[i].style.width = `${egtPct}%`;
        if (t.egt[i] > 840 || t.egt[i] < 550) {
          barEgts[i].style.background = '#EF4444';
        } else {
          barEgts[i].style.background = '#FACC15';
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
      if (cylHasFault) {
        cylCards[i].classList.add('card-fault');
      } else {
        cylCards[i].classList.remove('card-fault');
      }
    }
  }

  // Update Elapsed Mission Simulation Clock
  setInterval(function () {
    const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
    const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, '0');
    const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, '0');
    const secs = String(elapsedSec % 60).padStart(2, '0');
    elHdrSimTime.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);

  // Setup Event Listeners for Controls
  function setupControlListeners() {
    // Throttle
    sliderThrottle.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      valThrottle.textContent = `${Math.round(val)}%`;
      sendCommand({ action: 'set_controls', controls: { throttle_pct: val } });
    });

    // Altitude
    sliderAltitude.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      valAltitude.textContent = `${Number(val).toLocaleString()} ft`;
      sendCommand({ action: 'set_controls', controls: { altitude_ft: val } });
    });

    // Ambient Temp
    sliderAmbientTemp.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      valAmbientTemp.textContent = `${val.toFixed(1)} °C`;
      sendCommand({ action: 'set_controls', controls: { ambient_temp_c: val } });
    });

    // Wind Speed
    sliderWindSpeed.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      valWindSpeed.textContent = `${Math.round(val)} m/s`;
      sendCommand({ action: 'set_controls', controls: { wind_speed_mps: val } });
    });

    // Engine Load
    sliderEngineLoad.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      valEngineLoad.textContent = `${val.toFixed(2)}x`;
      sendCommand({ action: 'set_controls', controls: { engine_load: val } });
    });

    // Flight Phase Preset Buttons
    document.querySelectorAll('.btn-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const throttle = parseFloat(btn.dataset.throttle);
        const alt = parseFloat(btn.dataset.alt);
        const phase = btn.dataset.phase;

        sliderThrottle.value = throttle;
        valThrottle.textContent = `${Math.round(throttle)}%`;
        sliderAltitude.value = alt;
        valAltitude.textContent = `${Number(alt).toLocaleString()} ft`;

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
    btnClearAll.addEventListener('click', () => {
      sendCommand({ action: 'clear_all_faults' });
    });

    // Toggle Simulation
    elBtnToggleSim.addEventListener('click', () => {
      isSimRunning = !isSimRunning;
      elBtnToggleSim.textContent = isSimRunning ? 'PAUSE SIM' : 'RESUME SIM';
      elBtnToggleSim.style.background = isSimRunning ? '' : 'rgba(0, 230, 118, 0.2)';
      elBtnToggleSim.style.borderColor = isSimRunning ? '' : '#00e676';
      elBtnToggleSim.style.color = isSimRunning ? '' : '#00e676';
      sendCommand({ action: 'toggle_simulation' });
    });
  }

  // Initialize on DOM load
  window.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    setupControlListeners();
  });
})();
