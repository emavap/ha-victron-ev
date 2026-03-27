"""Tests for Victron EV charger custom card registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.victron_evse import (
    CARD_RESOURCE_BASE,
    CUSTOM_CARDS,
    _lovelace_resources,
    register_custom_cards,
)


class FakeConfig:
    """Minimal Home Assistant config stub."""

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path

    def path(self, *parts: str) -> str:
        return str(self._base_path.joinpath(*parts))


class FakeResources:
    """Minimal Lovelace resources store."""

    def __init__(self, items: list[dict[str, str]] | None = None) -> None:
        self._items = list(items or [])
        self.created: list[dict[str, str]] = []

    async def async_get_info(self):
        return {"resources": len(self._items)}

    def async_items(self):
        return list(self._items)

    async def async_create_item(self, item: dict[str, str]) -> None:
        self._items.append(item)
        self.created.append(item)


class FakeLovelaceData:
    """Object-style Lovelace data wrapper used by some HA versions."""

    def __init__(self, resources: FakeResources) -> None:
        self.resources = resources


class FakeHass:
    """Minimal Home Assistant stub for custom-card registration tests."""

    def __init__(self, base_path: Path, lovelace_data=None) -> None:
        self.config = FakeConfig(base_path)
        self.data = {}
        if lovelace_data is not None:
            self.data["lovelace"] = lovelace_data

    async def async_add_executor_job(self, func, *args):
        return func(*args)


@pytest.mark.asyncio
async def test_register_custom_cards_copies_files_and_resources(tmp_path, monkeypatch):
    """The integration should copy cards and register Lovelace resources automatically."""
    resources = FakeResources()
    hass = FakeHass(tmp_path, lovelace_data={"resources": resources})
    added_urls: list[str] = []

    monkeypatch.setattr(
        "custom_components.victron_evse.add_extra_js_url",
        lambda _hass, url: added_urls.append(url),
    )

    await register_custom_cards(hass)

    for folder in ("victron-ev-charger", "victron_evse"):
        target_dir = tmp_path / "www" / "community" / folder
        assert target_dir.exists()
        for card_file in CUSTOM_CARDS:
            assert (target_dir / card_file).exists()

    expected_urls = [f"{CARD_RESOURCE_BASE}/{card_file}" for card_file in CUSTOM_CARDS]
    assert added_urls == expected_urls
    assert [item["url"] for item in resources.created] == expected_urls
    assert hass.data["victron_evse"]["_cards_registered"] is True

    await register_custom_cards(hass)

    assert [item["url"] for item in resources.created] == expected_urls


@pytest.mark.asyncio
async def test_register_custom_cards_supports_object_lovelace_data(tmp_path, monkeypatch):
    """Card registration should work when hass.data['lovelace'] is an object, not a dict."""
    resources = FakeResources()
    hass = FakeHass(tmp_path, lovelace_data=FakeLovelaceData(resources))

    monkeypatch.setattr(
        "custom_components.victron_evse.add_extra_js_url",
        lambda _hass, _url: None,
    )

    await register_custom_cards(hass)

    assert len(resources.created) == len(CUSTOM_CARDS)
    assert _lovelace_resources(hass) is resources
