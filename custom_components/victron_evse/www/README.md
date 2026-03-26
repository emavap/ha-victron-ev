# Victron EV Charger Custom Lovelace Cards

This directory contains custom Lovelace cards for the `victron_evse` integration.

## Available Cards

- `victron-ev-charger-status-card.js`
- `victron-ev-charger-control-card.js`
- `victron-ev-charger-energy-card.js`
- `victron-ev-charger-info-card.js`

## Installation

Copy the `.js` files to your Home Assistant `www` directory, for example:

```bash
mkdir -p /config/www/community/victron-ev-charger/
cp custom_components/victron_evse/www/*.js /config/www/community/victron-ev-charger/
```

Then add them as Lovelace resources:

```yaml
resources:
  - url: /local/community/victron-ev-charger/victron-ev-charger-status-card.js
    type: module
  - url: /local/community/victron-ev-charger/victron-ev-charger-control-card.js
    type: module
  - url: /local/community/victron-ev-charger/victron-ev-charger-energy-card.js
    type: module
  - url: /local/community/victron-ev-charger/victron-ev-charger-info-card.js
    type: module
```

The cards can auto-detect the main integration entities in a single-charger setup. The safest setup is to define `entity_prefix` so every card binds to the same charger, especially if you have multiple chargers.

```yaml
type: custom:victron-ev-charger-status-card
entity_prefix: victron_ev_charger
```

Replace `victron_ev_charger` with the actual object ID prefix from Home Assistant. If you prefer, you can also provide explicit entity IDs.

## Common Options

- `entity_prefix`: object ID prefix shared by the charger entities, for example `victron_ev_charger`

## Card-Specific Options

### Status Card

- `status_entity`
- `power_entity`
- `vehicle_connected_entity`
- `charging_active_entity`

### Control Card

- `charging_entity`
- `mode_entity`
- `current_entity`
- `auto_start_entity`

### Energy Card

- `session_energy_entity`
- `total_energy_entity`
- `session_time_entity`
- `current_entity`
- `phases_entity`

### Info Card

- `register_profile_entity`
- `product_id_entity`
- `serial_number_entity`
- `firmware_version_entity`
- `charger_position_entity`
- `display_enabled_entity`

## Example

```yaml
type: vertical-stack
cards:
  - type: custom:victron-ev-charger-status-card
    entity_prefix: victron_ev_charger
  - type: custom:victron-ev-charger-control-card
    entity_prefix: victron_ev_charger
  - type: custom:victron-ev-charger-info-card
    entity_prefix: victron_ev_charger
```
