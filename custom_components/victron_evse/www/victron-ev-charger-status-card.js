class VictronEvChargerStatusCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this.config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 4;
  }

  _normalize(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  _escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => {
      const map = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      };
      return map[char] || char;
    });
  }

  _titleCase(value) {
    return String(value)
      .split(/[_\s-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  _isAvailable(entity) {
    if (!entity) return false;
    const state = this._normalize(entity.state);
    return state && !["unknown", "unavailable", "none"].includes(state);
  }

  _entityIds(domains) {
    return Object.keys(this._hass.states).filter((entityId) =>
      domains.some((domain) => entityId.startsWith(`${domain}.`))
    );
  }

  _objectId(entityId) {
    return entityId.split(".")[1] || "";
  }

  _extractPrefix(entityId, suffixes) {
    const objectId = this._objectId(entityId);
    for (const suffix of suffixes) {
      if (objectId === suffix) {
        return "";
      }
      if (objectId.endsWith(`_${suffix}`)) {
        return objectId.slice(0, -(suffix.length + 1));
      }
    }
    return null;
  }

  _resolvePrefix(domains, suffixes, configuredEntityIds = []) {
    if (typeof this.config.entity_prefix === "string" && this.config.entity_prefix.trim()) {
      return this.config.entity_prefix.trim();
    }

    for (const entityId of configuredEntityIds) {
      if (!entityId) {
        continue;
      }
      const prefix = this._extractPrefix(entityId, suffixes);
      if (prefix !== null) {
        return prefix;
      }
    }

    const ids = this._entityIds(domains);
    for (const suffix of suffixes) {
      const found = ids.find((entityId) => this._objectId(entityId).endsWith(`_${suffix}`));
      if (found) {
        return this._extractPrefix(found, [suffix]);
      }
    }

    return null;
  }

  _findEntity(domains, suffixes, configuredEntityId, prefix = null) {
    if (configuredEntityId && this._hass.states[configuredEntityId]) {
      return this._hass.states[configuredEntityId];
    }

    const ids = this._entityIds(domains);

    if (prefix !== null) {
      for (const domain of domains) {
        for (const suffix of suffixes) {
          const exactId = `${domain}.${prefix ? `${prefix}_` : ""}${suffix}`;
          if (this._hass.states[exactId]) {
            return this._hass.states[exactId];
          }
        }
      }
    }

    for (const suffix of suffixes) {
      const found = ids.find((entityId) => {
        const objectId = this._objectId(entityId);
        if (prefix !== null) {
          return objectId.startsWith(`${prefix}_`) && objectId.endsWith(`_${suffix}`);
        }
        return entityId.endsWith(`_${suffix}`) || entityId.endsWith(`.${suffix}`);
      });
      if (found) {
        return this._hass.states[found];
      }
    }

    return null;
  }

  _displayName(entity, prefix) {
    if (typeof this.config.name === "string" && this.config.name.trim()) {
      return this.config.name.trim();
    }

    const friendlyName = String(entity?.attributes?.friendly_name ?? "")
      .replace(/\bcharger status\b/i, "")
      .replace(/\s{2,}/g, " ")
      .trim();
    if (friendlyName) {
      return friendlyName;
    }

    if (prefix) {
      return this._titleCase(prefix);
    }

    return "Victron EV Charger";
  }

  _metric(label, value, hint = "") {
    return `
      <div class="metric">
        <div class="metric-label">${this._escape(label)}</div>
        <div class="metric-value">${this._escape(value)}</div>
        ${hint ? `<div class="metric-hint">${this._escape(hint)}</div>` : ""}
      </div>
    `;
  }

  render() {
    if (!this._hass) return;

    const suffixes = [
      "charger_status",
      "charging_power",
      "vehicle_connected",
      "charging_active",
    ];
    const prefix = this._resolvePrefix(
      ["sensor", "binary_sensor"],
      suffixes,
      [
        this.config.status_entity,
        this.config.power_entity,
        this.config.vehicle_connected_entity,
        this.config.charging_active_entity,
      ]
    );

    const statusEntity = this._findEntity(
      ["sensor"],
      ["charger_status"],
      this.config.status_entity,
      prefix
    );
    const powerEntity = this._findEntity(
      ["sensor"],
      ["charging_power"],
      this.config.power_entity,
      prefix
    );
    const connectedEntity = this._findEntity(
      ["binary_sensor"],
      ["vehicle_connected"],
      this.config.vehicle_connected_entity,
      prefix
    );
    const activeEntity = this._findEntity(
      ["binary_sensor"],
      ["charging_active"],
      this.config.charging_active_entity,
      prefix
    );

    if (!statusEntity && !powerEntity && !connectedEntity && !activeEntity) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div class="card-content empty">
            No Victron EV charger entities found. Set <code>entity_prefix</code> or provide explicit entity IDs.
          </div>
        </ha-card>
      `;
      return;
    }

    const statusText = this._isAvailable(statusEntity) ? statusEntity.state : "Unknown";
    const rawPower = this._isAvailable(powerEntity) ? parseFloat(powerEntity.state || "0") : null;
    const power = Number.isFinite(rawPower) ? rawPower : null;
    const connected = this._normalize(connectedEntity?.state) === "on";
    const charging = this._normalize(activeEntity?.state) === "on";
    const maxPowerKw = Math.max(parseFloat(this.config.max_power_kw ?? "22") || 22, 1);
    const fillWidth = power === null ? 0 : Math.max(0, Math.min(power / maxPowerKw, 1)) * 100;

    const palette = charging
      ? {
          accent: "#24c47d",
          accentSoft: "rgba(36, 196, 125, 0.18)",
          accentGlow: "rgba(36, 196, 125, 0.32)",
          badge: "Charging",
          icon: "mdi:lightning-bolt",
          stateClass: "charging",
          subline: power && power > 0 ? `Delivering ${power.toFixed(1)} kW` : "Charging session active",
        }
      : connected
        ? {
            accent: "#3ea6ff",
            accentSoft: "rgba(62, 166, 255, 0.18)",
            accentGlow: "rgba(62, 166, 255, 0.26)",
            badge: "Connected",
            icon: "mdi:ev-plug-type2",
            stateClass: "connected",
            subline: "Vehicle detected and ready to charge",
          }
        : {
            accent: "#8b95a7",
            accentSoft: "rgba(139, 149, 167, 0.18)",
            accentGlow: "rgba(139, 149, 167, 0.2)",
            badge: "Standby",
            icon: "mdi:ev-station",
            stateClass: "idle",
            subline: "Waiting for a vehicle to connect",
          };

    const chargerName = this._displayName(statusEntity, prefix);
    const powerText = power === null ? "Unavailable" : `${power.toFixed(1)} kW`;
    const loadText = power === null ? "No reading" : `${Math.round(fillWidth)}% of ${maxPowerKw} kW`;

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div
          class="shell ${palette.stateClass}"
          style="--accent:${palette.accent}; --accent-soft:${palette.accentSoft}; --accent-glow:${palette.accentGlow}; --fill:${fillWidth}%"
        >
          <div class="hero">
            <div class="copy">
              <div class="eyebrow">Victron charger</div>
              <div class="title-row">
                <div class="title">${this._escape(chargerName)}</div>
                <div class="badge">
                  <span class="badge-dot"></span>
                  ${this._escape(palette.badge)}
                </div>
              </div>
              <div class="headline">${this._escape(statusText)}</div>
              <div class="subline">${this._escape(palette.subline)}</div>

              <div class="metrics">
                ${this._metric("Power now", powerText, loadText)}
                ${this._metric("Vehicle", connected ? "Connected" : "Disconnected")}
                ${this._metric("Output", charging ? "Active" : "Idle")}
              </div>

              <div class="meter">
                <div class="meter-header">
                  <span>Charge load</span>
                  <span>${this._escape(powerText)}</span>
                </div>
                <div class="meter-track">
                  <div class="meter-fill"></div>
                </div>
              </div>
            </div>

            <div class="visual" aria-hidden="true">
              <div class="ambient"></div>
              <div class="charger-stage"></div>
              <div class="charger-body">
                <div class="charger-screen">
                  <ha-icon icon="${palette.icon}"></ha-icon>
                </div>
                <div class="charger-led"></div>
                <div class="charger-port"></div>
              </div>
              <div class="charger-cable"></div>
              <div class="charger-plug">
                <span></span>
                <span></span>
              </div>
              <div class="pulse pulse-a"></div>
              <div class="pulse pulse-b"></div>
            </div>
          </div>
        </div>
        <style>
          :host {
            display: block;
          }
          ha-card {
            overflow: hidden;
            border-radius: 28px;
          }
          .shell {
            padding: 22px;
            background:
              radial-gradient(circle at top left, var(--accent-soft), transparent 42%),
              linear-gradient(145deg, rgba(15, 23, 42, 0.96), rgba(24, 31, 46, 0.92));
            color: #f8fafc;
          }
          .hero {
            display: grid;
            grid-template-columns: minmax(0, 1.25fr) minmax(240px, 0.9fr);
            gap: 22px;
            align-items: center;
          }
          .eyebrow {
            font-size: 12px;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: rgba(248, 250, 252, 0.7);
          }
          .title-row {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            margin-top: 10px;
          }
          .title {
            font-size: 28px;
            line-height: 1.05;
            font-weight: 700;
          }
          .badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 12px;
            border-radius: 999px;
            background: var(--accent-soft);
            color: #f8fafc;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
          }
          .badge-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 14px var(--accent-glow);
          }
          .headline {
            margin-top: 14px;
            font-size: 34px;
            line-height: 1.05;
            font-weight: 700;
          }
          .subline {
            margin-top: 8px;
            max-width: 30rem;
            color: rgba(226, 232, 240, 0.82);
            font-size: 15px;
            line-height: 1.5;
          }
          .metrics {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 18px;
          }
          .metric {
            padding: 14px;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(8px);
          }
          .metric-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: rgba(226, 232, 240, 0.72);
          }
          .metric-value {
            margin-top: 8px;
            font-size: 21px;
            font-weight: 700;
          }
          .metric-hint {
            margin-top: 6px;
            font-size: 12px;
            color: rgba(226, 232, 240, 0.7);
          }
          .meter {
            margin-top: 18px;
            padding: 14px 16px 16px;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
          }
          .meter-header {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 10px;
            font-size: 13px;
            color: rgba(226, 232, 240, 0.78);
          }
          .meter-track {
            height: 12px;
            border-radius: 999px;
            background: rgba(148, 163, 184, 0.22);
            overflow: hidden;
          }
          .meter-fill {
            width: var(--fill);
            height: 100%;
            border-radius: inherit;
            background:
              linear-gradient(90deg, rgba(255, 255, 255, 0.35), transparent 30%),
              linear-gradient(90deg, var(--accent), rgba(255, 255, 255, 0.92));
            box-shadow: 0 0 22px var(--accent-glow);
            transition: width 240ms ease;
          }
          .visual {
            position: relative;
            min-height: 280px;
            border-radius: 24px;
            background:
              radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.08), transparent 38%),
              linear-gradient(180deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.02));
            border: 1px solid rgba(255, 255, 255, 0.08);
            overflow: hidden;
          }
          .ambient {
            position: absolute;
            inset: 24px 24px auto auto;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--accent-glow), transparent 70%);
            filter: blur(12px);
            opacity: 0.9;
          }
          .charger-stage {
            position: absolute;
            left: 50%;
            bottom: 26px;
            width: 70%;
            height: 18px;
            transform: translateX(-50%);
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.55);
            box-shadow: 0 20px 42px rgba(15, 23, 42, 0.5);
          }
          .charger-body {
            position: absolute;
            left: 50%;
            bottom: 38px;
            width: 128px;
            height: 202px;
            transform: translateX(-50%);
            border-radius: 34px 34px 22px 22px;
            background: linear-gradient(180deg, #f8fafc 0%, #dce5ef 54%, #c3cfdd 100%);
            box-shadow:
              inset 0 2px 0 rgba(255, 255, 255, 0.75),
              0 24px 48px rgba(15, 23, 42, 0.28);
          }
          .charger-body::before {
            content: "";
            position: absolute;
            inset: 10px 10px auto;
            height: 56px;
            border-radius: 24px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(226, 232, 240, 0.56));
          }
          .charger-screen {
            position: absolute;
            top: 30px;
            left: 50%;
            width: 72px;
            height: 72px;
            transform: translateX(-50%);
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.9));
            display: grid;
            place-items: center;
            color: var(--accent);
            box-shadow:
              inset 0 0 0 1px rgba(255, 255, 255, 0.08),
              0 10px 24px rgba(15, 23, 42, 0.3);
          }
          .charger-screen ha-icon {
            --mdc-icon-size: 34px;
          }
          .charger-led {
            position: absolute;
            left: 50%;
            bottom: 68px;
            width: 74px;
            height: 10px;
            transform: translateX(-50%);
            border-radius: 999px;
            background: var(--accent);
            box-shadow: 0 0 16px var(--accent-glow);
            opacity: 0.92;
          }
          .charger-port {
            position: absolute;
            left: 50%;
            bottom: 26px;
            width: 42px;
            height: 20px;
            transform: translateX(-50%);
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.82);
          }
          .charger-cable {
            position: absolute;
            right: 72px;
            bottom: 118px;
            width: 98px;
            height: 110px;
            border: 8px solid rgba(226, 232, 240, 0.88);
            border-left: 0;
            border-bottom: 0;
            border-radius: 0 80px 0 0;
            filter: drop-shadow(0 10px 16px rgba(15, 23, 42, 0.18));
          }
          .charger-plug {
            position: absolute;
            right: 28px;
            bottom: 184px;
            width: 30px;
            height: 54px;
            border-radius: 16px 16px 12px 12px;
            background: linear-gradient(180deg, #f8fafc, #cfd8e3);
            box-shadow: 0 10px 18px rgba(15, 23, 42, 0.22);
          }
          .charger-plug span {
            position: absolute;
            top: -8px;
            width: 4px;
            height: 16px;
            border-radius: 999px;
            background: #cbd5e1;
          }
          .charger-plug span:first-child {
            left: 8px;
          }
          .charger-plug span:last-child {
            right: 8px;
          }
          .pulse {
            position: absolute;
            border-radius: 50%;
            border: 1px solid var(--accent-soft);
            opacity: 0;
          }
          .pulse-a {
            right: 14px;
            bottom: 158px;
            width: 74px;
            height: 74px;
          }
          .pulse-b {
            right: 2px;
            bottom: 146px;
            width: 98px;
            height: 98px;
          }
          .charging .badge-dot,
          .charging .charger-led,
          .charging .meter-fill,
          .charging .pulse {
            animation: pulse 1.8s ease-in-out infinite;
          }
          .charging .pulse-b {
            animation-delay: 0.35s;
          }
          .connected .charger-led {
            opacity: 0.78;
          }
          .idle .charger-led {
            opacity: 0.42;
          }
          .empty {
            padding: 16px;
            color: var(--secondary-text-color);
          }
          code {
            font-family: monospace;
          }
          @keyframes pulse {
            0% {
              opacity: 0.45;
              transform: scale(0.96);
            }
            50% {
              opacity: 1;
              transform: scale(1);
            }
            100% {
              opacity: 0.45;
              transform: scale(0.96);
            }
          }
          @media (max-width: 860px) {
            .hero {
              grid-template-columns: 1fr;
            }
            .visual {
              min-height: 240px;
              order: -1;
            }
          }
          @media (max-width: 640px) {
            .shell {
              padding: 18px;
            }
            .title {
              font-size: 24px;
            }
            .headline {
              font-size: 28px;
            }
            .metrics {
              grid-template-columns: 1fr;
            }
          }
        </style>
      </ha-card>
    `;
  }
}

if (!customElements.get("victron-ev-charger-status-card")) {
  customElements.define("victron-ev-charger-status-card", VictronEvChargerStatusCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "victron-ev-charger-status-card")) {
  window.customCards.push({
    type: "victron-ev-charger-status-card",
    name: "Victron EV Charger Status Card",
    description: "Hero status overview with a live charger visual for the Victron EV charger integration.",
  });
}
