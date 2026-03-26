# Victron EV Charger for Home Assistant

This repository contains a HACS-installable custom integration for Victron EV chargers with UI setup through Home Assistant config flow.

## Features

- HACS-compatible repository layout
- Home Assistant config flow and reconfigure support
- Native entities instead of YAML templates
- Direct Modbus TCP communication
- Support for both the legacy EVSE register map and the current EVCS register map
- Automatic fast polling while the charger is active and slower polling while idle

## Exposed entities

- Sensors for charging power, status, current, energy, session time, and detected phases
- Binary sensors for vehicle connection, charging activity, and start/stop availability
- A number entity for manual charging current
- A select entity for the charger mode
- Switches for charging start/stop and auto-start

## Installation

1. Add this repository to HACS as a custom repository of type `Integration`.
2. Install `Victron EV Charger`.
3. Restart Home Assistant.
4. Add the integration from `Settings -> Devices & services`.

## Prerequisites

- The charger must be reachable over your network with a fixed IP address or stable hostname.
- Modbus TCP must be enabled on the charger.
- The Modbus port and slave ID in Home Assistant must match the charger configuration.

## Configuration

The config flow asks for:

- Charger name
- Host or static IP
- Modbus TCP port
- Register profile (`Auto-detect`, `EVCS`, or `EVSE`)
- Modbus slave ID
- Modbus timeout

To change the IP address or port later, open the integration in Home Assistant and use `Reconfigure`. The reconfigure flow lets you update the host, port, profile, slave ID, and timeout without removing and re-adding the device.

The options flow lets you tune:

- Register profile override
- Active polling interval
- Idle polling interval
- Modbus timeout

## Lovelace Cards

Custom Lovelace cards for this integration are included in [custom_components/victron_evse/www/README.md](custom_components/victron_evse/www/README.md).

An example dashboard layout using those cards is available in [cards/victron_ev_charger_dashboard.yaml](cards/victron_ev_charger_dashboard.yaml).

## Repository layout

The repository contains the HACS custom integration, packaging metadata, tests, local/CI validation files, custom Lovelace cards, and example dashboard YAML.

## Validation

The repository includes a Docker-based test environment and a GitHub Actions workflow that run the test suite for the custom integration.
