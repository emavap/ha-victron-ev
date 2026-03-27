"""The Victron EVSE integration."""

from __future__ import annotations

from pathlib import Path
import logging
import shutil

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    DOMAIN as LOVELACE_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import VictronEvseCoordinator

_LOGGER = logging.getLogger(__name__)

CUSTOM_CARDS = [
    "victron-ev-charger-status-card.js",
    "victron-ev-charger-control-card.js",
    "victron-ev-charger-energy-card.js",
    "victron-ev-charger-info-card.js",
]
CARD_RESOURCE_BASE = "/local/community/victron-ev-charger"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration from YAML."""
    return True


def _lovelace_resources(hass: HomeAssistant):
    """Return the Lovelace resources manager when available."""
    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if lovelace_data is None:
        return None
    if isinstance(lovelace_data, dict):
        return lovelace_data.get("resources")
    return getattr(lovelace_data, "resources", None)


async def _register_lovelace_resources(
    hass: HomeAssistant, card_urls: list[str]
) -> None:
    """Register custom cards as Lovelace module resources when available."""
    lovelace_resources = _lovelace_resources(hass)
    if lovelace_resources is None or not hasattr(lovelace_resources, "async_create_item"):
        return

    await lovelace_resources.async_get_info()
    existing_urls = {
        item.get(CONF_URL) for item in (lovelace_resources.async_items() or [])
    }
    for card_url in card_urls:
        if card_url in existing_urls:
            continue
        await lovelace_resources.async_create_item(
            {
                CONF_URL: card_url,
                CONF_RESOURCE_TYPE_WS: "module",
            }
        )
        _LOGGER.info("Registered Lovelace resource: %s", card_url)


async def register_custom_cards(hass: HomeAssistant) -> None:
    """Copy and register custom Lovelace cards for the integration."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_cards_registered"):
        return

    component_dir = Path(__file__).resolve().parent
    source_www_dir = component_dir / "www"
    target_dirs = [
        Path(hass.config.path("www")) / "community" / "victron-ev-charger",
        Path(hass.config.path("www")) / "community" / "victron_evse",
    ]

    def _copy_cards() -> tuple[list[str], list[Path]]:
        copied: list[str] = []
        missing: list[Path] = []

        for target_dir in target_dirs:
            target_dir.mkdir(parents=True, exist_ok=True)

        for card_file in CUSTOM_CARDS:
            source_path = source_www_dir / card_file
            if not source_path.exists():
                missing.append(source_path)
                continue
            for target_dir in target_dirs:
                shutil.copy2(source_path, target_dir / card_file)
            copied.append(card_file)

        return copied, missing

    try:
        copied_cards, missing_cards = await hass.async_add_executor_job(_copy_cards)
        card_urls = [f"{CARD_RESOURCE_BASE}/{card_file}" for card_file in copied_cards]

        for card_url in card_urls:
            add_extra_js_url(hass, card_url)
        await _register_lovelace_resources(hass, card_urls)

        for missing in missing_cards:
            _LOGGER.warning("Custom card file not found: %s", missing)

        domain_data["_cards_registered"] = True
        _LOGGER.info("Victron EV charger custom card registration completed")
    except Exception as err:
        _LOGGER.error("Failed to register custom cards: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron EVSE from a config entry."""
    await register_custom_cards(hass)
    coordinator = VictronEvseCoordinator(hass, entry)
    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data.setdefault(DOMAIN, {}).pop(entry.entry_id, None)
        await coordinator.async_close()
        raise

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: VictronEvseCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry after data or option changes."""
    await hass.config_entries.async_reload(entry.entry_id)
