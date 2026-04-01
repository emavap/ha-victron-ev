class VictronEvChargerControlCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._pendingCurrent = null;
  }

  static get AMBIGUOUS_PREFIX() {
    return "__ambiguous__";
  }

  setConfig(config) {
    this.config = config || {};
    if (this._hass) {
      this.render();
    }
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

  _isAvailable(entity) {
    if (!entity) return false;
    const state = this._normalize(entity.state);
    return state && !["unknown", "unavailable", "none"].includes(state);
  }

  _states() {
    return this._hass?.states || {};
  }

  _entityIds(domains) {
    return Object.keys(this._states()).filter((entityId) =>
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

  _collectPrefixes(domains, suffixes, configuredEntityIds = []) {
    const prefixes = new Set();

    for (const entityId of configuredEntityIds) {
      if (!entityId) {
        continue;
      }
      const prefix = this._extractPrefix(entityId, suffixes);
      if (prefix !== null) {
        prefixes.add(prefix);
      }
    }

    if (prefixes.size) {
      return prefixes;
    }

    const ids = this._entityIds(domains);
    for (const entityId of ids) {
      const prefix = this._extractPrefix(entityId, suffixes);
      if (prefix !== null) {
        prefixes.add(prefix);
      }
    }

    return prefixes;
  }

  _configuredEntityIds(configuredEntityIds = []) {
    return configuredEntityIds.filter((entityId) => typeof entityId === "string" && entityId.trim());
  }

  _configuredPrefixes(suffixes, configuredEntityIds = []) {
    const prefixes = new Set();
    for (const entityId of this._configuredEntityIds(configuredEntityIds)) {
      const prefix = this._extractPrefix(entityId, suffixes);
      if (prefix !== null) {
        prefixes.add(prefix);
      }
    }
    return prefixes;
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

  _resolvePrefix(domains, suffixes, configuredEntityIds = []) {
    if (typeof this.config.entity_prefix === "string" && this.config.entity_prefix.trim()) {
      return this.config.entity_prefix.trim();
    }
    const explicitIds = this._configuredEntityIds(configuredEntityIds);
    if (explicitIds.length === configuredEntityIds.length) {
      return null;
    }
    if (explicitIds.length) {
      const prefixes = this._configuredPrefixes(suffixes, configuredEntityIds);
      if (prefixes.size === 1) {
        return [...prefixes][0];
      }
      return VictronEvChargerControlCard.AMBIGUOUS_PREFIX;
    }

    const prefixes = this._collectPrefixes(domains, suffixes, configuredEntityIds);
    if (prefixes.size === 1) {
      return [...prefixes][0];
    }
    if (prefixes.size > 1) {
      return VictronEvChargerControlCard.AMBIGUOUS_PREFIX;
    }
    return null;
  }

  _findEntity(domains, suffixes, configuredEntityId, prefix = null) {
    const states = this._states();

    if (configuredEntityId) {
      return states[configuredEntityId] || null;
    }

    if (prefix === VictronEvChargerControlCard.AMBIGUOUS_PREFIX) {
      return null;
    }

    const ids = this._entityIds(domains);

    if (prefix !== null) {
      for (const domain of domains) {
        for (const suffix of suffixes) {
          const exactId = `${domain}.${prefix ? `${prefix}_` : ""}${suffix}`;
          if (states[exactId]) {
            return states[exactId];
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
        return states[found];
      }
    }

    return null;
  }

  _toggle(entityId) {
    return this._hass.callService("homeassistant", "toggle", {
      entity_id: entityId,
    });
  }

  _setMode(entityId, option) {
    return this._hass.callService("select", "select_option", {
      entity_id: entityId,
      option,
    });
  }

  _setCurrent(entityId, value) {
    return this._hass.callService("number", "set_value", {
      entity_id: entityId,
      value,
    });
  }

  render() {
    if (!this._hass) return;
    if (!this._hass.states) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">Waiting for Home Assistant state data...</div></ha-card>
      `;
      return;
    }

    const suffixes = [
      "charging",
      "charge_mode",
      "manual_charging_current",
      "auto_start",
    ];
    const configuredEntityIds = [
      this.config.charging_entity,
      this.config.mode_entity,
      this.config.current_entity,
      this.config.auto_start_entity,
    ];
    const prefix = this._resolvePrefix(
      ["switch", "select", "number"],
      suffixes,
      configuredEntityIds
    );

    if (prefix === VictronEvChargerControlCard.AMBIGUOUS_PREFIX) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">Multiple Victron EV charger entity groups found. Set <code>entity_prefix</code> or explicit entity IDs.</div></ha-card>
      `;
      return;
    }

    const chargingEntity = this._findEntity(
      ["switch"],
      ["charging"],
      this.config.charging_entity,
      prefix
    );
    const modeEntity = this._findEntity(
      ["select"],
      ["charge_mode"],
      this.config.mode_entity,
      prefix
    );
    const currentEntity = this._findEntity(
      ["number"],
      ["manual_charging_current"],
      this.config.current_entity,
      prefix
    );
    const autoStartEntity = this._findEntity(
      ["switch"],
      ["auto_start"],
      this.config.auto_start_entity,
      prefix
    );

    if (!chargingEntity && !modeEntity && !currentEntity && !autoStartEntity) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">No Victron EV charger control entities found. Set <code>entity_prefix</code> or explicit entity IDs.</div></ha-card>
      `;
      return;
    }

    const chargingAvailable = this._isAvailable(chargingEntity);
    const modeAvailable = this._isAvailable(modeEntity);
    const currentAvailable = this._isAvailable(currentEntity);
    const autoStartAvailable = this._isAvailable(autoStartEntity);

    if (![chargingAvailable, modeAvailable, currentAvailable, autoStartAvailable].some(Boolean)) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">The charger control entities are currently unavailable.</div></ha-card>
      `;
      return;
    }

    const actualCurrentValue = parseFloat(currentEntity?.state || "0");
    if (this._pendingCurrent) {
      const pending = this._pendingCurrent;
      const hasActualValue = Number.isFinite(actualCurrentValue);
      if (
        currentEntity?.entity_id !== pending.entityId
        || (hasActualValue && actualCurrentValue === pending.value)
        || (
          hasActualValue
          && Number.isFinite(pending.baseValue)
          && actualCurrentValue !== pending.baseValue
        )
        || Date.now() - pending.requestedAt > 10000
      ) {
        this._pendingCurrent = null;
      }
    }
    const currentValue = this._pendingCurrent?.value ?? actualCurrentValue;
    const currentMin = parseFloat(currentEntity?.attributes?.min ?? 6);
    const currentMax = parseFloat(currentEntity?.attributes?.max ?? 32);
    const activeMode = modeAvailable ? modeEntity.state : null;
    const modeOptions = modeAvailable ? modeEntity.attributes?.options || [] : [];

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="wrap">
          <div class="actions">
            ${chargingEntity ? `
              <button class="primary ${chargingEntity.state === "on" ? "on" : ""}" id="charging-toggle" ${chargingAvailable ? "" : "disabled"}>
                ${chargingAvailable
                  ? chargingEntity.state === "on"
                    ? "Stop Charging"
                    : "Start Charging"
                  : "Start/Stop Unavailable"}
              </button>
            ` : ""}
            ${autoStartEntity ? `
              <button class="${autoStartEntity.state === "on" ? "on" : ""}" id="auto-start-toggle" ${autoStartAvailable ? "" : "disabled"}>
                ${autoStartAvailable
                  ? `Auto Start: ${autoStartEntity.state === "on" ? "On" : "Off"}`
                  : "Auto Start Unavailable"}
              </button>
            ` : ""}
          </div>

          ${modeEntity ? `
            <div class="section">
              <div class="label">Charge mode</div>
              ${modeAvailable ? `
                <div class="chips">
                  ${modeOptions.map((option) => `
                    <button class="chip ${option === activeMode ? "selected" : ""}" data-mode="${this._escape(option)}">
                      ${this._escape(option)}
                    </button>
                  `).join("")}
                </div>
              ` : '<div class="note">Charge mode is currently unavailable.</div>'}
            </div>
          ` : ""}

          ${currentEntity ? `
            <div class="section">
              <div class="label">Manual current</div>
              ${currentAvailable ? `
                <div class="current-row">
                  <div class="current-value">${currentValue.toFixed(0)} A</div>
                  <div class="range">${currentMin}A - ${currentMax}A</div>
                </div>
                <input id="current-slider" type="range" min="${currentMin}" max="${currentMax}" step="1" value="${currentValue}">
              ` : '<div class="note">Manual current control is currently unavailable.</div>'}
            </div>
          ` : ""}
        </div>
        <style>
          .wrap { padding: 16px; }
          .actions, .chips { display: flex; flex-wrap: wrap; gap: 10px; }
          .section { margin-top: 16px; }
          .label {
            margin-bottom: 8px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--secondary-text-color);
          }
          button {
            border: 0;
            border-radius: 999px;
            padding: 10px 14px;
            cursor: pointer;
            background: var(--secondary-background-color);
            color: var(--primary-text-color);
            white-space: normal;
            text-align: center;
          }
          button:disabled {
            cursor: not-allowed;
            opacity: 0.55;
          }
          button.primary {
            background: var(--primary-color);
            color: var(--text-primary-color, white);
          }
          button.on, .chip.selected {
            box-shadow: inset 0 0 0 2px var(--primary-color);
          }
          .current-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 8px;
          }
          .current-value {
            font-size: 24px;
            font-weight: 700;
          }
          .range {
            color: var(--secondary-text-color);
            font-size: 13px;
          }
          .note {
            color: var(--secondary-text-color);
            font-size: 14px;
            overflow-wrap: anywhere;
          }
          input[type="range"] {
            width: 100%;
          }
          .empty {
            padding: 16px;
            color: var(--secondary-text-color);
          }
          code {
            font-family: monospace;
          }
          @media (max-width: 480px) {
            .current-row {
              flex-direction: column;
              align-items: flex-start;
            }
          }
        </style>
      </ha-card>
    `;

    if (chargingAvailable) {
      this.shadowRoot.getElementById("charging-toggle")?.addEventListener("click", () => {
        this._toggle(chargingEntity.entity_id);
      });
    }
    if (autoStartAvailable) {
      this.shadowRoot.getElementById("auto-start-toggle")?.addEventListener("click", () => {
        this._toggle(autoStartEntity.entity_id);
      });
    }
    this.shadowRoot.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this._setMode(modeEntity.entity_id, button.dataset.mode);
      });
    });

    const slider = this.shadowRoot.getElementById("current-slider");
    if (slider && currentEntity && currentAvailable) {
      slider.addEventListener("input", (event) => {
        this._pendingCurrent = {
          value: parseFloat(event.target.value),
          entityId: currentEntity.entity_id,
          baseValue: parseFloat(currentEntity.state || "0"),
          requestedAt: Date.now(),
        };
        this.render();
      });
      slider.addEventListener("change", (event) => {
        const value = parseFloat(event.target.value);
        this._pendingCurrent = {
          value,
          entityId: currentEntity.entity_id,
          baseValue: parseFloat(currentEntity.state || "0"),
          requestedAt: Date.now(),
        };
        this._setCurrent(currentEntity.entity_id, value).catch(() => {
          this._pendingCurrent = null;
          this.render();
        });
      });
    }
  }
}

if (!customElements.get("victron-ev-charger-control-card")) {
  customElements.define("victron-ev-charger-control-card", VictronEvChargerControlCard);
}
window.customCards = Array.isArray(window.customCards) ? window.customCards : [];
if (!window.customCards.some((card) => card.type === "victron-ev-charger-control-card")) {
  window.customCards.push({
    type: "victron-ev-charger-control-card",
    name: "Victron EV Charger Control Card",
    description: "Controls for charging, mode, current, and auto-start.",
  });
}
