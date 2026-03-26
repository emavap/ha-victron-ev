# Victron EV Charger for Home Assistant

This repository contains a HACS-installable custom integration for Victron EV chargers. It replaces the original package-style YAML setup with a native Home Assistant integration that supports UI setup through config flow.

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

## Configuration

The config flow asks for:

- Charger name
- Host or static IP
- Modbus TCP port
- Register profile (`Auto-detect`, `EVCS`, or `EVSE`)
- Modbus slave ID

The options flow lets you tune:

- Register profile override
- Active polling interval
- Idle polling interval
- Modbus timeout

## Repository layout

The repository only contains the HACS custom integration, packaging metadata, and tests. The old package-style YAML files and dashboard examples have been removed.
