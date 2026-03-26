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
    return 3;
  }

  _normalize(value) {
    return String(value ?? "").trim().toLowerCase();
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
    const power = this._isAvailable(powerEntity)
      ? parseFloat(powerEntity.state || "0")
      : 0;
    const connected = this._normalize(connectedEntity?.state) === "on";
    const charging = this._normalize(activeEntity?.state) === "on";
    const accent = charging ? "#2e7d32" : connected ? "#1565c0" : "#616161";
    const icon = charging ? "mdi:battery-charging" : connected ? "mdi:power-plug" : "mdi:ev-station";

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="wrap">
          <div class="hero" style="--accent:${accent}">
            <ha-icon icon="${icon}"></ha-icon>
            <div>
              <div class="label">Status</div>
              <div class="value">${statusText}</div>
            </div>
          </div>
          <div class="grid">
            <div class="tile">
              <div class="label">Power</div>
              <div class="value">${power.toFixed(1)} kW</div>
            </div>
            <div class="tile">
              <div class="label">Vehicle</div>
              <div class="value">${connected ? "Connected" : "Disconnected"}</div>
            </div>
            <div class="tile span">
              <div class="label">Charging</div>
              <div class="value">${charging ? "Active" : "Idle"}</div>
              <div class="bar"><div class="fill" style="width:${Math.max(0, Math.min(power / 22, 1)) * 100}%"></div></div>
            </div>
          </div>
        </div>
        <style>
          .wrap { padding: 16px; }
          .hero {
            display: grid;
            grid-template-columns: 40px 1fr;
            gap: 12px;
            align-items: center;
            margin-bottom: 14px;
          }
          ha-icon {
            color: var(--accent);
            --mdc-icon-size: 32px;
          }
          .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
          }
          .tile {
            border-radius: 14px;
            padding: 12px;
            background: var(--secondary-background-color);
          }
          .span { grid-column: 1 / -1; }
          .label {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--secondary-text-color);
          }
          .value {
            margin-top: 6px;
            font-size: 20px;
            font-weight: 600;
          }
          .bar {
            margin-top: 10px;
            height: 8px;
            border-radius: 999px;
            background: rgba(127, 127, 127, 0.18);
            overflow: hidden;
          }
          .fill {
            height: 100%;
            border-radius: inherit;
            background: var(--accent);
          }
          .empty {
            padding: 16px;
            color: var(--secondary-text-color);
          }
          code {
            font-family: monospace;
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
    description: "Status overview for the Victron EV charger integration.",
  });
}
