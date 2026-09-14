/**
 * SIH Digital Twin — Aircraft Engine Health Monitoring Client Application
 * Connects to ws://127.0.0.1:8766/ws/digital_twin
 * Renders real-time aircraft telemetry, Digital Twin physics residual comparison,
 * circular health gauge, anomaly diagnosis, and rolling canvas charts.
 */

(function () {
  let ws = null;
  let missionStartTime = Date.now();

  // Chart rolling buffers (last 80 frames)
  const MAX_POINTS = 80;
  const historyRpm = [];
  const historyMap = [];
  const historyCht3 = [];
  const historyEgt3 = [];
  const historyDres = [];
  const historyCht = [[], [], [], []];

  // DOM Elements - Header & Connection
  const connIndicator = document.getElementById('conn-indicator');
  const connStatusText = document.getElementById('conn-status-text');
  const connEndpointText = document.getElementById('conn-endpoint-text');
  const subLinkStatus = document.getElementById('sub-link-status');
  const hdrTwinSync = document.getElementById('hdr-twin-sync');
  const hdrLatency = document.getElementById('hdr-latency');
  const hdrPackets = document.getElementById('hdr-packets');
  const hdrMissionClock = document.getElementById('hdr-mission-clock');

  // DOM Elements - Telemetry Gauges
  const dispRpm = document.getElementById('disp-rpm');
  const meterRpm = document.getElementById('meter-rpm');
  const dispPower = document.getElementById('disp-power');
  const dispMap = document.getElementById('disp-map');
  const dispOilP = document.getElementById('disp-oil-p');
  const meterOilP = document.getElementById('meter-oil-p');
  const cardOilPress = document.getElementById('card-oil-press');
  const dispOilT = document.getElementById('disp-oil-t');
  const meterOilT = document.getElementById('meter-oil-t');
  const cardOilTemp = document.getElementById('card-oil-temp');
  const dispCoolant = document.getElementById('disp-coolant');
  const meterCoolant = document.getElementById('meter-coolant');
  const cardCoolant = document.getElementById('card-coolant');
  const dispVib = document.getElementById('disp-vib');
  const meterVib = document.getElementById('meter-vib');
  const cardVibration = document.getElementById('card-vibration');
  const valFlightPhase = document.getElementById('val-flight-phase');

  // Cylinders CHT & EGT + Balance Section
  const dispChts = [1, 2, 3, 4].map(i => document.getElementById(`disp-cht-${i}`));
  const dispEgts = [1, 2, 3, 4].map(i => document.getElementById(`disp-egt-${i}`));
  const dashCyls = [1, 2, 3, 4].map(i => document.getElementById(`dash-cyl-${i}`));
  const dispSpreadCht = document.getElementById('disp-spread-cht');
  const dispSpreadEgt = document.getElementById('disp-spread-egt');
  const badgeCylBalance = document.getElementById('badge-cyl-balance');
  const barsCht = [1, 2, 3, 4].map(i => document.getElementById(`bar-cht-${i}`));
  const barsEgt = [1, 2, 3, 4].map(i => document.getElementById(`bar-egt-${i}`));
  const numBars = [1, 2, 3, 4].map(i => document.getElementById(`num-bar-${i}`));
  const canvasCylTrend = document.getElementById('chart-cyl-trend');

  // Digital Twin EKF States
  const dtEtaVol = document.getElementById('dt-eta-vol');
  const barEtaVol = document.getElementById('bar-eta-vol');
  const dtEtaMech = document.getElementById('dt-eta-mech');
  const barEtaMech = document.getElementById('bar-eta-mech');
  const dtEtaComb = document.getElementById('dt-eta-comb');
  const barEtaComb = document.getElementById('bar-eta-comb');

  // Residual Table Elements
  const expRpm = document.getElementById('exp-rpm');
  const obsRpm = document.getElementById('obs-rpm');
  const diffRpm = document.getElementById('diff-rpm');

  const expMap = document.getElementById('exp-map');
  const obsMap = document.getElementById('obs-map');
  const diffMap = document.getElementById('diff-map');

  const expOilP = document.getElementById('exp-oil-p');
  const obsOilP = document.getElementById('obs-oil-p');
  const diffOilP = document.getElementById('diff-oil-p');
  const rowOilPress = document.getElementById('row-oil-press');

  const expOilT = document.getElementById('exp-oil-t');
  const obsOilT = document.getElementById('obs-oil-t');
  const diffOilT = document.getElementById('diff-oil-t');
  const rowOilTemp = document.getElementById('row-oil-temp');

  const expCoolant = document.getElementById('exp-coolant');
  const obsCoolant = document.getElementById('obs-coolant');
  const diffCoolant = document.getElementById('diff-coolant');
  const rowCoolant = document.getElementById('row-coolant');

  const expCht3 = document.getElementById('exp-cht-3');
  const obsCht3 = document.getElementById('obs-cht-3');
  const diffCht3 = document.getElementById('diff-cht-3');
  const rowCht3 = document.getElementById('row-cht-3');

  const expEgt3 = document.getElementById('exp-egt-3');
  const obsEgt3 = document.getElementById('obs-egt-3');
  const diffEgt3 = document.getElementById('diff-egt-3');
  const rowEgt3 = document.getElementById('row-egt-3');

  const expVib = document.getElementById('exp-vib');
  const obsVib = document.getElementById('obs-vib');
  const diffVib = document.getElementById('diff-vib');
  const rowVibration = document.getElementById('row-vibration');

  const dtDres = document.getElementById('dt-dres');
  const barDres = document.getElementById('bar-dres');

  // Health, Risk & Advisory Elements
  const svgHealthMeter = document.getElementById('svg-health-meter');
  const dispHealthNum = document.getElementById('disp-health-num');
  const dispHealthNumCockpit = document.getElementById('disp-health-num-cockpit');
  const topHealthStatus = document.getElementById('top-health-status');
  const badgeMissionRisk = document.getElementById('badge-mission-risk');
  const dispRiskStatus = document.getElementById('disp-risk-status');
  const dispRulVal = document.getElementById('disp-rul-val');
  const dispRulCi = document.getElementById('disp-rul-ci');
  const dispConfidence = document.getElementById('disp-confidence');

  // Feature Card Blue Elements
  const featureCardRiskTitle = document.getElementById('feature-card-risk-title');
  const featureCardHealth = document.getElementById('feature-card-health');
  const featureCardRul = document.getElementById('feature-card-rul');

  // Active Diagnostics Elements
  const diagStatusBadge = document.getElementById('diag-status-badge');
  const diagFaultName = document.getElementById('diag-fault-name');
  const diagSubsystem = document.getElementById('diag-subsystem');
  const incidentContainer = document.getElementById('incident-container');
  const statRiskVal = document.getElementById('stat-risk-val');
  const statDresVal = document.getElementById('stat-dres-val');

  // Advisory Elements
  const cardAdvisory = document.getElementById('card-advisory');
  const advBadgeUrgency = document.getElementById('adv-badge-urgency');
  const advTitle = document.getElementById('adv-title');
  const advDiagCode = document.getElementById('adv-diag-code');
  const advRootCause = document.getElementById('adv-root-cause');
  const advPilotList = document.getElementById('adv-pilot-list');
  const advMaintList = document.getElementById('adv-maint-list');

  // Canvases
  const canvasRpmMap = document.getElementById('chart-rpm-map');
  const canvasTemps = document.getElementById('chart-temps');
  const canvasResiduals = document.getElementById('chart-residuals');

  function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/digital_twin`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function () {
      if (connIndicator) connIndicator.classList.remove('disconnected');
      if (connStatusText) {
        connStatusText.textContent = 'AIRCRAFT TELEMETRY LINK ACTIVE';
        connStatusText.classList.remove('offline');
      }
      if (connEndpointText) connEndpointText.textContent = '10 Hz TELEMETRY SYNCHRONIZED';
      if (subLinkStatus) subLinkStatus.textContent = 'ACTIVE';
    };

    ws.onmessage = function (event) {
      try {
        const frame = JSON.parse(event.data);
        renderDashboardFrame(frame);
      } catch (err) {
        console.error('Error parsing telemetry frame', err);
      }
    };

    ws.onclose = function () {
      if (connIndicator) connIndicator.classList.add('disconnected');
      if (connStatusText) {
        connStatusText.textContent = 'AIRCRAFT TELEMETRY LINK OFFLINE';
        connStatusText.classList.add('offline');
      }
      if (connEndpointText) connEndpointText.textContent = 'SEARCHING FOR TELEMETRY STREAM...';
      if (subLinkStatus) subLinkStatus.textContent = 'OFFLINE';
      setTimeout(initWebSocket, 1000);
    };

    ws.onerror = function () {
      ws.close();
    };
  }

  function renderDashboardFrame(data) {
    if (!data || !data.observed) return;

    const obs = data.observed;
    const exp = data.expected;
    const res = data.residuals;
    const deg = data.degradation;
    const analytics = data.analytics;
    const hr = data.health_risk;
    const adv = data.advisory;
    const stats = data.stats;

    // Header diagnostics
    if (stats) {
      if (hdrPackets) hdrPackets.textContent = (stats.packets || 0).toLocaleString();
      if (hdrLatency) hdrLatency.textContent = `${stats.latency_ms || 1.2} ms`;
      if (!stats.connected) {
        if (connIndicator) connIndicator.classList.add('disconnected');
        if (connStatusText) {
          connStatusText.textContent = 'AIRCRAFT TELEMETRY LINK OFFLINE';
          connStatusText.classList.add('offline');
        }
        if (connEndpointText) connEndpointText.textContent = 'SEARCHING FOR TELEMETRY STREAM...';
        if (subLinkStatus) subLinkStatus.textContent = 'STANDBY';
      } else {
        if (connIndicator) connIndicator.classList.remove('disconnected');
        if (connStatusText) {
          connStatusText.textContent = 'AIRCRAFT TELEMETRY LINK ACTIVE';
          connStatusText.classList.remove('offline');
        }
        if (connEndpointText) connEndpointText.textContent = '10 Hz TELEMETRY SYNCHRONIZED';
        if (subLinkStatus) subLinkStatus.textContent = 'ACTIVE';
      }
    }

    // Flight phase
    if (data.flight_env && data.flight_env.flight_phase) {
      if (valFlightPhase) valFlightPhase.textContent = data.flight_env.flight_phase.toUpperCase();
    }

    // 1. Observed Telemetry Gauges
    if (dispRpm) dispRpm.textContent = Math.round(obs.rpm);
    const rpmPct = Math.min(100, Math.max(0, (obs.rpm / 5800) * 100));
    if (meterRpm) meterRpm.style.width = `${rpmPct}%`;

    const pKw = (obs.rpm * 0.015) * (obs.map_kpa / 100);
    if (dispPower) dispPower.textContent = `${pKw.toFixed(1)} kW (${(pKw * 1.341).toFixed(1)} HP)`;
    if (dispMap) dispMap.textContent = `${obs.map_kpa.toFixed(1)} kPa`;

    // Oil Pressure
    if (dispOilP) dispOilP.textContent = obs.oil_pressure_bar.toFixed(2);
    const oilPPct = Math.min(100, Math.max(0, (obs.oil_pressure_bar / 6.5) * 100));
    if (meterOilP) meterOilP.style.width = `${oilPPct}%`;
    if (obs.oil_pressure_bar < 2.0) {
      if (cardOilPress) cardOilPress.classList.add('alarm');
      if (meterOilP) meterOilP.style.background = '#EF4444';
      if (dispOilP) dispOilP.style.color = '#EF4444';
    } else {
      if (cardOilPress) cardOilPress.classList.remove('alarm');
      if (meterOilP) meterOilP.style.background = '#39D353';
      if (dispOilP) dispOilP.style.color = '#FFFFFF';
    }

    // Oil Temp
    if (dispOilT) dispOilT.textContent = obs.oil_temp_c.toFixed(1);
    const oilTPct = Math.min(100, Math.max(0, ((obs.oil_temp_c - 40) / 100) * 100));
    if (meterOilT) meterOilT.style.width = `${oilTPct}%`;
    if (obs.oil_temp_c > 115) {
      if (cardOilTemp) cardOilTemp.classList.add('alarm');
      if (meterOilT) meterOilT.style.background = '#EF4444';
      if (dispOilT) dispOilT.style.color = '#EF4444';
    } else {
      if (cardOilTemp) cardOilTemp.classList.remove('alarm');
      if (meterOilT) meterOilT.style.background = '#FDE68A';
      if (dispOilT) dispOilT.style.color = '#FFFFFF';
    }

    // Coolant Temp
    if (dispCoolant) dispCoolant.textContent = obs.coolant_temp_c.toFixed(1);
    const coolPct = Math.min(100, Math.max(0, ((obs.coolant_temp_c - 40) / 90) * 100));
    if (meterCoolant) meterCoolant.style.width = `${coolPct}%`;
    if (obs.coolant_temp_c > 110) {
      if (cardCoolant) cardCoolant.classList.add('alarm');
      if (meterCoolant) meterCoolant.style.background = '#EF4444';
      if (dispCoolant) dispCoolant.style.color = '#EF4444';
    } else {
      if (cardCoolant) cardCoolant.classList.remove('alarm');
      if (meterCoolant) meterCoolant.style.background = '#FDE68A';
      if (dispCoolant) dispCoolant.style.color = '#FFFFFF';
    }

    // Vibration
    if (dispVib) dispVib.textContent = obs.vibration_rms.toFixed(2);
    const vibPct = Math.min(100, Math.max(0, (obs.vibration_rms / 6.0) * 100));
    if (meterVib) meterVib.style.width = `${vibPct}%`;
    if (obs.vibration_rms > 3.0) {
      if (cardVibration) cardVibration.classList.add('alarm');
      if (meterVib) meterVib.style.background = '#EF4444';
      if (dispVib) dispVib.style.color = '#EF4444';
    } else {
      if (cardVibration) cardVibration.classList.remove('alarm');
      if (meterVib) meterVib.style.background = '#FDE68A';
      if (dispVib) dispVib.style.color = '#FFFFFF';
    }

    // 4 Cylinders CHT & EGT
    if (obs.cht && obs.cht.length >= 4) {
      for (let i = 0; i < 4; i++) {
        if (dispChts[i]) dispChts[i].textContent = `${obs.cht[i].toFixed(1)} °C`;
        if (dispEgts[i]) dispEgts[i].textContent = `${Math.round(obs.egt[i])} °C`;

        if (dashCyls[i]) {
          if (obs.cht[i] > 135 || obs.egt[i] > 840 || obs.egt[i] < 550) {
            dashCyls[i].classList.add('fault');
          } else {
            dashCyls[i].classList.remove('fault');
          }
        }
      }

      // Live Cylinder Balance & Spread
      const minCht = Math.min(...obs.cht);
      const maxCht = Math.max(...obs.cht);
      const spreadCht = maxCht - minCht;

      const minEgt = Math.min(...obs.egt);
      const maxEgt = Math.max(...obs.egt);
      const spreadEgt = maxEgt - minEgt;

      if (dispSpreadCht) dispSpreadCht.textContent = `${spreadCht.toFixed(1)} °C`;
      if (dispSpreadEgt) dispSpreadEgt.textContent = `${Math.round(spreadEgt)} °C`;

      if (badgeCylBalance) {
        if (spreadCht > 18 || spreadEgt > 60) {
          badgeCylBalance.textContent = 'SPREAD ALERT';
          badgeCylBalance.classList.add('chip-unbalanced');
        } else {
          badgeCylBalance.textContent = 'BALANCED';
          badgeCylBalance.classList.remove('chip-unbalanced');
        }
      }

      // Update Horizontal Comparison Bars
      for (let i = 0; i < 4; i++) {
        const normCht = Math.max(15, Math.min(100, ((obs.cht[i] - 50) / 100) * 100));
        const normEgt = Math.max(15, Math.min(100, ((obs.egt[i] - 400) / 500) * 100));
        if (barsCht[i]) barsCht[i].style.width = `${normCht}%`;
        if (barsEgt[i]) barsEgt[i].style.width = `${normEgt}%`;
        if (numBars[i]) numBars[i].textContent = `${Math.round(obs.cht[i])}° / ${Math.round(obs.egt[i])}°`;
      }
    }

    // 2. Digital Twin Degradation States
    if (deg) {
      if (dtEtaVol) dtEtaVol.textContent = `${deg.eta_vol_health_pct.toFixed(1)}%`;
      if (barEtaVol) barEtaVol.style.width = `${deg.eta_vol_health_pct}%`;
      if (dtEtaMech) dtEtaMech.textContent = `${deg.eta_mech_health_pct.toFixed(1)}%`;
      if (barEtaMech) barEtaMech.style.width = `${deg.eta_mech_health_pct}%`;
      if (dtEtaComb) dtEtaComb.textContent = `${deg.eta_comb_health_pct.toFixed(1)}%`;
      if (barEtaComb) barEtaComb.style.width = `${deg.eta_comb_health_pct}%`;
    }

    // 3. Expected vs Observed Residual Table
    if (exp && res) {
      if (expRpm) expRpm.textContent = Math.round(exp.rpm);
      if (obsRpm) obsRpm.textContent = Math.round(obs.rpm);
      setResidualDisplay(diffRpm, res.diff_rpm, 'RPM', 80, 200);

      if (expMap) expMap.textContent = exp.map_kpa.toFixed(1);
      if (obsMap) obsMap.textContent = obs.map_kpa.toFixed(1);
      setResidualDisplay(diffMap, res.diff_map, 'kPa', 5.0, 10.0);

      if (expOilP) expOilP.textContent = exp.oil_pressure_bar.toFixed(2);
      if (obsOilP) obsOilP.textContent = obs.oil_pressure_bar.toFixed(2);
      setResidualDisplay(diffOilP, res.diff_oil_p, 'bar', 0.6, 1.2, rowOilPress);

      if (expOilT) expOilT.textContent = exp.oil_temp_c.toFixed(1);
      if (obsOilT) obsOilT.textContent = obs.oil_temp_c.toFixed(1);
      setResidualDisplay(diffOilT, res.diff_oil_t, '°C', 8.0, 16.0, rowOilTemp);

      if (expCoolant) expCoolant.textContent = exp.coolant_temp_c.toFixed(1);
      if (obsCoolant) obsCoolant.textContent = obs.coolant_temp_c.toFixed(1);
      setResidualDisplay(diffCoolant, res.diff_coolant, '°C', 6.0, 12.0, rowCoolant);

      if (expCht3) expCht3.textContent = exp.cht[2].toFixed(1);
      if (obsCht3) obsCht3.textContent = obs.cht[2].toFixed(1);
      setResidualDisplay(diffCht3, res.diff_cht[2], '°C', 8.0, 16.0, rowCht3);

      if (expEgt3) expEgt3.textContent = exp.egt[2].toFixed(1);
      if (obsEgt3) obsEgt3.textContent = obs.egt[2].toFixed(1);
      setResidualDisplay(diffEgt3, res.diff_egt[2], '°C', 45.0, 90.0, rowEgt3);

      if (expVib) expVib.textContent = exp.vibration_rms.toFixed(2);
      if (obsVib) obsVib.textContent = obs.vibration_rms.toFixed(2);
      setResidualDisplay(diffVib, res.diff_vib, 'mm/s', 0.8, 1.8, rowVibration);
    }

    // Residual Distance D_res
    if (analytics) {
      const dres = analytics.residual_distance || 1.2;
      if (dtDres) dtDres.textContent = dres.toFixed(2);
      if (statDresVal) statDresVal.textContent = dres.toFixed(2);
      const dresPct = Math.min(100, (dres / 6.0) * 100);
      if (barDres) {
        barDres.style.width = `${dresPct}%`;
        if (dres > 2.5) {
          barDres.style.background = '#EF4444';
          if (dtDres) dtDres.style.color = '#EF4444';
        } else {
          barDres.style.background = '#FDE68A';
          if (dtDres) dtDres.style.color = '#FDE68A';
        }
      }

      // Update Active Diagnostics Card
      if (analytics.fault_diagnosis) {
        const fd = analytics.fault_diagnosis;
        const code = fd.code || 'FC-00';
        const name = fd.name || 'NOMINAL';
        if (advDiagCode) advDiagCode.textContent = `${code}: ${name.toUpperCase()}`;
        if (diagFaultName) diagFaultName.textContent = name;
        if (diagSubsystem) diagSubsystem.textContent = `Affected Subsystem: ${fd.subsystem || 'None (Healthy)'}`;
      }

      if (diagStatusBadge) {
        if (analytics.severity === 'CRITICAL') {
          diagStatusBadge.textContent = 'CRITICAL';
          diagStatusBadge.className = 'incident-badge badge-crit';
          if (incidentContainer) incidentContainer.classList.add('alarm');
        } else if (analytics.severity === 'WARNING' || analytics.severity === 'CAUTION') {
          diagStatusBadge.textContent = analytics.severity;
          diagStatusBadge.className = 'incident-badge badge-warn';
          if (incidentContainer) incidentContainer.classList.add('alarm');
        } else {
          diagStatusBadge.textContent = 'NOMINAL';
          diagStatusBadge.className = 'incident-badge';
          if (incidentContainer) incidentContainer.classList.remove('alarm');
        }
      }
    }

    // 4. Health, Risk & Operational Advisory
    if (hr) {
      const hScore = hr.health_score;
      const roundedHealth = Math.round(hScore);
      if (dispHealthNum) dispHealthNum.textContent = roundedHealth;
      if (dispHealthNumCockpit) dispHealthNumCockpit.textContent = roundedHealth;
      if (featureCardHealth) featureCardHealth.textContent = `${hScore.toFixed(1)}%`;

      // SVG circle perimeter is 2 * pi * 70 = 439.82
      const circumference = 439.82;
      const offset = circumference * (1 - hScore / 100.0);
      if (svgHealthMeter) {
        svgHealthMeter.style.strokeDashoffset = offset;
      }

      if (hScore >= 80) {
        if (svgHealthMeter) svgHealthMeter.style.stroke = '#39D353';
        if (badgeMissionRisk) {
          badgeMissionRisk.textContent = '• Full Envelope Clear';
          badgeMissionRisk.style.color = '#39D353';
        }
        if (dispRiskStatus) {
          dispRiskStatus.textContent = 'LOW RISK (GO)';
          dispRiskStatus.style.color = '#39D353';
        }
        if (statRiskVal) {
          statRiskVal.textContent = 'LOW RISK (GO)';
          statRiskVal.style.color = '#39D353';
        }
        if (featureCardRiskTitle) {
          featureCardRiskTitle.textContent = 'MISSION GO';
          featureCardRiskTitle.style.color = '#39D353';
        }
        if (topHealthStatus) {
          topHealthStatus.textContent = '• Nominal State';
          topHealthStatus.style.color = '#39D353';
        }
      } else if (hScore >= 60) {
        if (svgHealthMeter) svgHealthMeter.style.stroke = '#F59E0B';
        if (badgeMissionRisk) {
          badgeMissionRisk.textContent = '• Caution Envelope';
          badgeMissionRisk.style.color = '#F59E0B';
        }
        if (dispRiskStatus) {
          dispRiskStatus.textContent = 'MODERATE (CAUTION)';
          dispRiskStatus.style.color = '#F59E0B';
        }
        if (statRiskVal) {
          statRiskVal.textContent = 'MODERATE (CAUTION)';
          statRiskVal.style.color = '#F59E0B';
        }
        if (featureCardRiskTitle) {
          featureCardRiskTitle.textContent = 'CAUTION';
          featureCardRiskTitle.style.color = '#F59E0B';
        }
        if (topHealthStatus) topHealthStatus.textContent = '• Cautionary Wear';
      } else {
        if (svgHealthMeter) svgHealthMeter.style.stroke = '#EF4444';
        if (badgeMissionRisk) {
          badgeMissionRisk.textContent = '• RTB Abort Recommended';
          badgeMissionRisk.style.color = '#EF4444';
        }
        if (dispRiskStatus) {
          dispRiskStatus.textContent = 'HIGH RISK (RTB ABORT)';
          dispRiskStatus.style.color = '#EF4444';
        }
        if (statRiskVal) {
          statRiskVal.textContent = 'HIGH RISK (RTB ABORT)';
          statRiskVal.style.color = '#EF4444';
        }
        if (featureCardRiskTitle) {
          featureCardRiskTitle.textContent = 'RTB / ABORT';
          featureCardRiskTitle.style.color = '#EF4444';
        }
        if (topHealthStatus) topHealthStatus.textContent = '• Fault Detected';
      }

      if (dispRulVal) dispRulVal.textContent = hr.rul.display;
      if (featureCardRul) featureCardRul.textContent = hr.rul.display;
      if (dispRulCi) dispRulCi.textContent = hr.rul.confidence_interval;
      if (dispConfidence && analytics) {
        dispConfidence.textContent = `${analytics.confidence_pct}% (${analytics.severity})`;
      }
    }

    // Advisory Card
    if (adv) {
      if (advTitle) advTitle.textContent = adv.title;
      if (advRootCause) advRootCause.textContent = adv.root_cause_summary;
      if (advBadgeUrgency) advBadgeUrgency.textContent = adv.urgency;

      if (cardAdvisory) {
        if (analytics && analytics.is_anomaly) {
          cardAdvisory.classList.add('card-alarm');
        } else {
          cardAdvisory.classList.remove('card-alarm');
        }
      }

      // Pilot list
      if (advPilotList && adv.pilot_instructions) {
        advPilotList.innerHTML = adv.pilot_instructions.map(item => `<li>${item.replace(/^[0-9]+\.\s*/, '')}</li>`).join('');
      }
      // Maintenance list
      if (advMaintList && adv.maintenance_instructions) {
        advMaintList.innerHTML = adv.maintenance_instructions.map(item => `<li>${item.replace(/^•\s*/, '')}</li>`).join('');
      }
    }

    // Push into rolling history for canvas rendering
    updateChartBuffers(obs, analytics);
  }

  function setResidualDisplay(elem, val, unit, warnThreshold, critThreshold, rowElem = null) {
    if (!elem) return;
    const sign = val > 0 ? '+' : '';
    elem.textContent = `${sign}${val.toFixed(1)} ${unit}`;
    const absVal = Math.abs(val);

    elem.classList.remove('diff-warn', 'diff-crit');
    if (rowElem) rowElem.classList.remove('fault-row');

    if (absVal >= critThreshold) {
      elem.classList.add('diff-crit');
      if (rowElem) rowElem.classList.add('fault-row');
    } else if (absVal >= warnThreshold) {
      elem.classList.add('diff-warn');
    }
  }

  // Rolling Chart Buffers
  function updateChartBuffers(obs, analytics) {
    historyRpm.push(obs.rpm);
    historyMap.push(obs.map_kpa);
    historyCht3.push(obs.cht[2]);
    historyEgt3.push(obs.egt[2]);
    historyDres.push(analytics ? analytics.residual_distance : 1.0);

    for (let i = 0; i < 4; i++) {
      if (obs.cht && obs.cht[i] !== undefined) {
        historyCht[i].push(obs.cht[i]);
        if (historyCht[i].length > MAX_POINTS) historyCht[i].shift();
      }
    }

    if (historyRpm.length > MAX_POINTS) {
      historyRpm.shift();
      historyMap.shift();
      historyCht3.shift();
      historyEgt3.shift();
      historyDres.shift();
    }
  }

  // High-DPI Crisp Canvas Drawing Loop
  function renderCanvases() {
    const isLight = document.body.getAttribute('data-theme') === 'light';
    const primaryChartColor = isLight ? '#D97706' : '#FACC15';
    const secondaryChartColor = isLight ? '#2563EB' : 'rgba(250, 204, 21, 0.65)';
    const normalColor = isLight ? '#16A34A' : '#39D353';
    const alertColor = isLight ? '#DC2626' : '#EF4444';

    // Chart 1: RPM and MAP
    drawDualChart(canvasRpmMap, historyRpm, historyMap, 1000, 6000, 30, 110, primaryChartColor, secondaryChartColor, true);
    // Chart 2: CHT and EGT
    drawDualChart(canvasTemps, historyCht3, historyEgt3, 60, 160, 450, 900, primaryChartColor, secondaryChartColor, true);
    // Chart 3: Residual distance with dashed threshold line at 2.5
    drawThresholdChart(canvasResiduals, historyDres, 0.0, 7.0, 2.5, normalColor, alertColor);
    // Cylinder 4-Trend: 4-cylinder CHT lines
    drawCylTrend(canvasCylTrend, historyCht, 60, 150);

    requestAnimationFrame(renderCanvases);
  }

  function setupCanvasDpi(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  function drawDualChart(canvas, data1, data2, min1, max1, min2, max2, color1, color2, dash2 = false) {
    if (!canvas || canvas.clientWidth === 0) return;
    const { ctx, w, h } = setupCanvasDpi(canvas);

    ctx.clearRect(0, 0, w, h);

    // Subtle Gridlines
    const isLight = document.body.getAttribute('data-theme') === 'light';
    ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5);
    ctx.moveTo(0, h * 0.25); ctx.lineTo(w, h * 0.25);
    ctx.moveTo(0, h * 0.75); ctx.lineTo(w, h * 0.75);
    ctx.stroke();

    if (data1.length < 2) return;

    // Series 1 (Soft Light Yellow / Primary)
    ctx.strokeStyle = color1;
    ctx.lineWidth = 2.2;
    ctx.setLineDash([]);
    ctx.beginPath();
    for (let i = 0; i < data1.length; i++) {
      const x = (i / (MAX_POINTS - 1)) * w;
      const normY = Math.max(0, Math.min(1, (data1[i] - min1) / (max1 - min1)));
      const y = h - normY * (h - 12) - 6;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Series 2 (Light Yellow Family / Secondary)
    ctx.strokeStyle = color2;
    ctx.lineWidth = 1.8;
    if (dash2) ctx.setLineDash([4, 3]);
    else ctx.setLineDash([]);
    ctx.beginPath();
    for (let i = 0; i < data2.length; i++) {
      const x = (i / (MAX_POINTS - 1)) * w;
      const normY = Math.max(0, Math.min(1, (data2[i] - min2) / (max2 - min2)));
      const y = h - normY * (h - 12) - 6;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Draw 4-Cylinder Trend Lines (Light-Yellow Visual Family)
  function drawCylTrend(canvas, chts, minVal, maxVal) {
    if (!canvas || canvas.clientWidth === 0) return;
    const { ctx, w, h } = setupCanvasDpi(canvas);

    ctx.clearRect(0, 0, w, h);

    // Subtle Gridlines
    const isLightCyl = document.body.getAttribute('data-theme') === 'light';
    ctx.strokeStyle = isLightCyl ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5);
    ctx.stroke();

    if (!chts || !chts[0] || chts[0].length < 2) return;

    // Distinct styles: in light mode use high-contrast warm/cool tones, in dark mode use #FACC15 family
    const styles = isLightCyl ? [
      { color: '#B45309', width: 2.2, dash: [] },
      { color: '#D97706', width: 2.0, dash: [4, 3] },
      { color: '#2563EB', width: 1.8, dash: [] },
      { color: '#475569', width: 1.6, dash: [2, 2] }
    ] : [
      { color: '#FACC15', width: 2.0, dash: [] },
      { color: 'rgba(250, 204, 21, 0.75)', width: 1.8, dash: [4, 3] },
      { color: 'rgba(250, 204, 21, 0.5)', width: 1.6, dash: [] },
      { color: 'rgba(250, 204, 21, 0.35)', width: 1.5, dash: [2, 2] }
    ];

    for (let c = 0; c < 4; c++) {
      const data = chts[c];
      if (!data || data.length < 2) continue;

      ctx.strokeStyle = styles[c].color;
      ctx.lineWidth = styles[c].width;
      ctx.setLineDash(styles[c].dash);
      ctx.beginPath();

      for (let i = 0; i < data.length; i++) {
        const x = (i / (MAX_POINTS - 1)) * w;
        const normY = Math.max(0, Math.min(1, (data[i] - minVal) / (maxVal - minVal)));
        const y = h - normY * (h - 8) - 4;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  function drawThresholdChart(canvas, data, minVal, maxVal, threshold, normalColor, alertColor) {
    if (!canvas || canvas.clientWidth === 0) return;
    const { ctx, w, h } = setupCanvasDpi(canvas);

    ctx.clearRect(0, 0, w, h);

    // Gridlines
    const isLightThresh = document.body.getAttribute('data-theme') === 'light';
    ctx.strokeStyle = isLightThresh ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.5); ctx.lineTo(w, h * 0.5);
    ctx.stroke();

    // Threshold Line (dashed)
    const threshNorm = Math.max(0, Math.min(1, (threshold - minVal) / (maxVal - minVal)));
    const threshY = h - threshNorm * (h - 12) - 6;
    ctx.strokeStyle = isLightThresh ? 'rgba(220, 38, 38, 0.75)' : 'rgba(239, 68, 68, 0.5)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, threshY); ctx.lineTo(w, threshY);
    ctx.stroke();
    ctx.setLineDash([]);

    if (data.length < 2) return;

    // Plot data with smooth crisp stroke
    const latestVal = data[data.length - 1];
    ctx.strokeStyle = latestVal > threshold ? alertColor : normalColor;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = (i / (MAX_POINTS - 1)) * w;
      const normY = Math.max(0, Math.min(1, (data[i] - minVal) / (maxVal - minVal)));
      const y = h - normY * (h - 12) - 6;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // Mission Clock Updater
  setInterval(function () {
    const elapsedSec = Math.floor((Date.now() - missionStartTime) / 1000);
    const hrs = String(Math.floor(elapsedSec / 3600)).padStart(2, '0');
    const mins = String(Math.floor((elapsedSec % 3600) / 60)).padStart(2, '0');
    const secs = String(elapsedSec % 60).padStart(2, '0');
    if (hdrMissionClock) hdrMissionClock.textContent = `${hrs}:${mins}:${secs}`;
  }, 1000);

  // Navigation Pill Interactivity (3-Page Dedicated View Routing)
  function setupNavigation() {
    const navPills = document.querySelectorAll('.nav-pill');
    const pageViews = document.querySelectorAll('.page-view');

    function switchPage(target) {
      if (!target) return;

      // Update active nav pill state
      navPills.forEach(p => {
        if (p.getAttribute('data-nav') === target) {
          p.classList.add('active');
        } else {
          p.classList.remove('active');
        }
      });

      // Show target view, hide others
      pageViews.forEach(view => {
        if (view.id === `view-${target}`) {
          view.classList.remove('is-hidden');
        } else {
          view.classList.add('is-hidden');
        }
      });

      // Smoothly scroll to top of view
      window.scrollTo({ top: 0, behavior: 'smooth' });

      // Immediate canvas redraw on new view container
      requestAnimationFrame(() => {
        renderCanvases();
      });
    }

    navPills.forEach(pill => {
      pill.addEventListener('click', () => {
        const target = pill.getAttribute('data-nav');
        switchPage(target);
      });
    });

    // Quick Jump Buttons with [data-goto]
    document.querySelectorAll('[data-goto]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.getAttribute('data-goto');
        switchPage(target);
      });
    });

    // Advisory category pill toggles
    const advChips = document.querySelectorAll('.adv-chip');
    advChips.forEach(chip => {
      chip.addEventListener('click', () => {
        advChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
      });
    });
  }

  // Sun/Moon Theme Toggle with persistence
  function setupThemeToggle() {
    const themeBtn = document.getElementById('theme-toggle');
    if (!themeBtn) return;
    const iconSun = themeBtn.querySelector('.theme-icon-sun');
    const iconMoon = themeBtn.querySelector('.theme-icon-moon');

    function applyTheme(theme) {
      if (theme === 'light') {
        document.body.setAttribute('data-theme', 'light');
        if (iconSun) iconSun.style.display = 'block';
        if (iconMoon) iconMoon.style.display = 'none';
      } else {
        document.body.removeAttribute('data-theme');
        if (iconSun) iconSun.style.display = 'none';
        if (iconMoon) iconMoon.style.display = 'block';
      }
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

  // Initialize
  window.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    setupNavigation();
    setupThemeToggle();
    requestAnimationFrame(renderCanvases);
  });
})();
