class VictronEvChargerEnergyCard extends HTMLElement {
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

  _display(entity, unit = "") {
    if (!entity || ["unknown", "unavailable"].includes(String(entity.state))) {
      return "Unavailable";
    }
    return `${entity.state}${unit}`;
  }

  render() {
    if (!this._hass) return;

    const suffixes = [
      "session_energy",
      "total_energy",
      "session_time_hms",
      "actual_charging_current",
      "detected_car_phases",
      "detected_phases",
    ];
    const prefix = this._resolvePrefix(
      ["sensor"],
      suffixes,
      [
        this.config.session_energy_entity,
        this.config.total_energy_entity,
        this.config.session_time_entity,
        this.config.current_entity,
        this.config.phases_entity,
      ]
    );
    const sessionEnergy = this._findEntity(["sensor"], ["session_energy"], this.config.session_energy_entity, prefix);
    const totalEnergy = this._findEntity(["sensor"], ["total_energy"], this.config.total_energy_entity, prefix);
    const sessionTime = this._findEntity(["sensor"], ["session_time_hms"], this.config.session_time_entity, prefix);
    const current = this._findEntity(["sensor"], ["actual_charging_current"], this.config.current_entity, prefix);
    const phases = this._findEntity(["sensor"], ["detected_car_phases", "detected_phases"], this.config.phases_entity, prefix);

    if (!sessionEnergy && !totalEnergy && !sessionTime && !current && !phases) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">No Victron EV charger energy entities found. Set <code>entity_prefix</code> or explicit entity IDs.</div></ha-card>
      `;
      return;
    }

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="wrap">
          <div class="header">Session & Energy</div>
          <div class="grid">
            <div class="tile">
              <div class="label">Session energy</div>
              <div class="value">${this._display(sessionEnergy, " kWh")}</div>
            </div>
            <div class="tile">
              <div class="label">Total energy</div>
              <div class="value">${this._display(totalEnergy, " kWh")}</div>
            </div>
            <div class="tile">
              <div class="label">Session time</div>
              <div class="value">${this._display(sessionTime)}</div>
            </div>
            <div class="tile">
              <div class="label">Actual current</div>
              <div class="value">${this._display(current, " A")}</div>
            </div>
            <div class="tile span">
              <div class="label">Detected phases</div>
              <div class="value">${this._display(phases)}</div>
            </div>
          </div>
        </div>
        <style>
          .wrap { padding: 16px; }
          .header {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
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

if (!customElements.get("victron-ev-charger-energy-card")) {
  customElements.define("victron-ev-charger-energy-card", VictronEvChargerEnergyCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "victron-ev-charger-energy-card")) {
  window.customCards.push({
    type: "victron-ev-charger-energy-card",
    name: "Victron EV Charger Energy Card",
    description: "Session and energy metrics for the Victron EV charger integration.",
  });
}
