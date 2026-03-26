# Victron EV Charger Lovelace Examples

This directory contains standard Home Assistant Lovelace YAML examples for the `victron_evse` integration.

Unlike the sibling `fusionsolar_charger` project, these examples do not require custom JavaScript resources. They use only built-in Home Assistant cards, so you can paste them directly into a dashboard and adjust the entity IDs if needed.

## Files

- `victron_ev_charger_dashboard.yaml`: main example dashboard with status, controls, session data, and diagnostics

## Entity IDs

The example uses the default device name `Victron EV Charger`, so the entity IDs start with `victron_ev_charger_`.

If you named the device differently during setup:

- open Developer Tools -> States
- search for your charger entities
- replace the `victron_ev_charger_` prefix in the example YAML with your actual prefix

## Notes

- The example uses only entities created by this integration.
- EVCS-only diagnostics such as serial number, firmware version, and product ID appear only when the charger exposes them.
- If `auto_start` is unsupported by your charger profile, that tile will show as unavailable.
