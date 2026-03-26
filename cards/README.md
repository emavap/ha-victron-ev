# Victron EV Charger Lovelace Examples

This directory contains Lovelace YAML examples for the `victron_evse` integration.

These examples are built on top of the custom cards shipped in [custom_components/victron_evse/www/README.md](../custom_components/victron_evse/www/README.md).

## Files

- `victron_ev_charger_dashboard.yaml`: example dashboard layout using the custom Victron EV charger cards

## Entity IDs

The example dashboard sets `entity_prefix: victron_ev_charger` on each card so all cards bind to the same charger.

If your entity IDs use a different prefix, replace `victron_ev_charger` with the actual object ID prefix from `Developer Tools -> States`.

If you have multiple chargers or want precise control, configure explicit entity IDs in the custom card YAML instead.

## Notes

- The example uses only entities created by this integration.
- EVCS-only diagnostics such as serial number, firmware version, and product ID appear only when the charger exposes them.
- If `auto_start` or start/stop control is unsupported, the control card disables those buttons instead of showing active controls.
