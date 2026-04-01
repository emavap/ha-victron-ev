class VictronEvChargerInfoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
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
    return 3;
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
      return VictronEvChargerInfoCard.AMBIGUOUS_PREFIX;
    }

    const prefixes = this._collectPrefixes(domains, suffixes, configuredEntityIds);
    if (prefixes.size === 1) {
      return [...prefixes][0];
    }
    if (prefixes.size > 1) {
      return VictronEvChargerInfoCard.AMBIGUOUS_PREFIX;
    }
    return null;
  }

  _findEntity(domains, suffixes, configuredEntityId, prefix = null) {
    const states = this._states();

    if (configuredEntityId) {
      return states[configuredEntityId] || null;
    }

    if (prefix === VictronEvChargerInfoCard.AMBIGUOUS_PREFIX) {
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

  _row(label, entity) {
    if (!entity || ["unknown", "unavailable"].includes(String(entity.state))) {
      return "";
    }
    return `
      <div class="row">
        <div class="label">${this._escape(label)}</div>
        <div class="value">${this._escape(entity.state)}</div>
      </div>
    `;
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

  render() {
    if (!this._hass) return;
    if (!this._hass.states) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">Waiting for Home Assistant state data...</div></ha-card>
      `;
      return;
    }

    const suffixes = [
      "register_profile",
      "product_id",
      "serial_number",
      "firmware_version",
      "charger_position",
      "display_enabled",
      "display_enabled_raw",
    ];
    const configuredEntityIds = [
      this.config.register_profile_entity,
      this.config.product_id_entity,
      this.config.serial_number_entity,
      this.config.firmware_version_entity,
      this.config.charger_position_entity,
      this.config.display_enabled_entity,
      this.config.display_enabled_raw_entity,
    ];
    const prefix = this._resolvePrefix(
      ["sensor", "binary_sensor"],
      suffixes,
      configuredEntityIds
    );

    if (prefix === VictronEvChargerInfoCard.AMBIGUOUS_PREFIX) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">Multiple Victron EV charger entity groups found. Set <code>entity_prefix</code> or explicit entity IDs.</div></ha-card>
      `;
      return;
    }
    const registerProfile = this._findEntity(
      ["sensor"],
      ["register_profile"],
      this.config.register_profile_entity,
      prefix
    );
    const productId = this._findEntity(
      ["sensor"],
      ["product_id"],
      this.config.product_id_entity,
      prefix
    );
    const serialNumber = this._findEntity(
      ["sensor"],
      ["serial_number"],
      this.config.serial_number_entity,
      prefix
    );
    const firmwareVersion = this._findEntity(
      ["sensor"],
      ["firmware_version"],
      this.config.firmware_version_entity,
      prefix
    );
    const chargerPosition = this._findEntity(
      ["sensor"],
      ["charger_position"],
      this.config.charger_position_entity,
      prefix
    );
    const displayEnabled = this._findEntity(
      ["binary_sensor"],
      ["display_enabled"],
      this.config.display_enabled_entity,
      prefix
    );
    const displayEnabledRaw = this._findEntity(
      ["sensor"],
      ["display_enabled_raw"],
      this.config.display_enabled_raw_entity,
      prefix
    );

    const rows = [
      this._row("Register profile", registerProfile),
      this._row("Product ID", productId),
      this._row("Serial number", serialNumber),
      this._row("Firmware version", firmwareVersion),
      this._row("Charger position", chargerPosition),
      this._row("Display enabled", displayEnabled),
      this._row("Display enabled raw", displayEnabledRaw),
    ].filter(Boolean);

    if (!rows.length) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="empty">No diagnostic entities are currently available for this charger.</div></ha-card>
      `;
      return;
    }

    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="wrap">
          <div class="header">Diagnostics</div>
          ${rows.join("")}
        </div>
        <style>
          .wrap { padding: 16px; }
          .header {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
          }
          .row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
            gap: 12px;
            padding: 10px 0;
            border-top: 1px solid var(--divider-color);
          }
          .row:first-of-type {
            border-top: 0;
          }
          .label {
            color: var(--secondary-text-color);
            overflow-wrap: anywhere;
          }
          .value {
            font-weight: 600;
            text-align: right;
            overflow-wrap: anywhere;
          }
          .empty {
            padding: 16px;
            color: var(--secondary-text-color);
          }
          @media (max-width: 480px) {
            .row {
              grid-template-columns: 1fr;
              gap: 6px;
            }
            .value {
              text-align: left;
            }
          }
        </style>
      </ha-card>
    `;
  }
}

if (!customElements.get("victron-ev-charger-info-card")) {
  customElements.define("victron-ev-charger-info-card", VictronEvChargerInfoCard);
}
window.customCards = Array.isArray(window.customCards) ? window.customCards : [];
if (!window.customCards.some((card) => card.type === "victron-ev-charger-info-card")) {
  window.customCards.push({
    type: "victron-ev-charger-info-card",
    name: "Victron EV Charger Info Card",
    description: "Diagnostic and device information for the Victron EV charger integration.",
  });
}
