"""Tests for Victron EV charger custom card registration."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from custom_components.victron_evse import (
    CARD_RESOURCE_BASE,
    CUSTOM_CARDS,
    RESOURCE_REGISTRATION_READY,
    _lovelace_resources,
    _retry_register_lovelace_resources,
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


class FakeReadOnlyResources:
    """Minimal YAML-mode Lovelace resources store."""

    def __init__(self, items: list[dict[str, str]] | None = None) -> None:
        self._items = list(items or [])

    async def async_get_info(self):
        return {"resources": len(self._items)}

    def async_items(self):
        return list(self._items)


class FakeLovelaceData:
    """Object-style Lovelace data wrapper used by some HA versions."""

    def __init__(self, resources: FakeResources) -> None:
        self.resources = resources


class FakeHass:
    """Minimal Home Assistant stub for custom-card registration tests."""

    def __init__(self, base_path: Path, lovelace_data=None) -> None:
        self.config = FakeConfig(base_path)
        self.data = {}
        self.tasks: list[asyncio.Task] = []
        if lovelace_data is not None:
            self.data["lovelace"] = lovelace_data

    async def async_add_executor_job(self, func, *args):
        return func(*args)

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


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


@pytest.mark.asyncio
async def test_register_custom_cards_retries_until_lovelace_is_ready(
    tmp_path, monkeypatch
):
    """Card registration should retry if Lovelace resources are not ready yet."""
    hass = FakeHass(tmp_path)
    wait_for_retry = asyncio.Event()

    monkeypatch.setattr(
        "custom_components.victron_evse.add_extra_js_url",
        lambda _hass, _url: None,
    )

    async def gated_sleep(_delay):
        await wait_for_retry.wait()

    monkeypatch.setattr("custom_components.victron_evse.asyncio.sleep", gated_sleep)

    await register_custom_cards(hass)

    assert "_cards_registered" not in hass.data["victron_evse"]
    assert len(hass.tasks) == 1

    resources = FakeResources()
    hass.data["lovelace"] = {"resources": resources}
    wait_for_retry.set()
    await asyncio.gather(*hass.tasks)

    expected_urls = [f"{CARD_RESOURCE_BASE}/{card_file}" for card_file in CUSTOM_CARDS]
    assert [item["url"] for item in resources.created] == expected_urls
    assert hass.data["victron_evse"]["_cards_registered"] is True


@pytest.mark.asyncio
async def test_register_custom_cards_does_not_retry_for_read_only_lovelace_resources(
    tmp_path, monkeypatch
):
    """Read-only Lovelace resource stores should not trigger futile retries."""
    hass = FakeHass(tmp_path, lovelace_data={"resources": FakeReadOnlyResources()})

    monkeypatch.setattr(
        "custom_components.victron_evse.add_extra_js_url",
        lambda _hass, _url: None,
    )

    await register_custom_cards(hass)

    assert len(hass.tasks) == 0
    assert "_resource_retry_task" not in hass.data["victron_evse"]
    assert "_cards_registered" not in hass.data["victron_evse"]


@pytest.mark.asyncio
async def test_retry_register_lovelace_resources_recovers_after_transient_error(
    tmp_path, monkeypatch
):
    """Transient Lovelace API failures should not abort the retry loop."""
    resources = FakeResources()
    hass = FakeHass(tmp_path, lovelace_data={"resources": resources})
    hass.data["victron_evse"] = {}
    wait_for_retry = asyncio.Event()
    attempts = 0

    async def flaky_register(_hass, card_urls):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("resources not ready")
        for card_url in card_urls:
            await resources.async_create_item({"url": card_url, "type": "module"})
        return RESOURCE_REGISTRATION_READY

    async def gated_sleep(_delay):
        await wait_for_retry.wait()

    monkeypatch.setattr(
        "custom_components.victron_evse._register_lovelace_resources",
        flaky_register,
    )
    monkeypatch.setattr("custom_components.victron_evse.asyncio.sleep", gated_sleep)

    retry_task = asyncio.create_task(
        _retry_register_lovelace_resources(
            hass,
            [f"{CARD_RESOURCE_BASE}/{card_file}" for card_file in CUSTOM_CARDS],
        )
    )
    hass.data["victron_evse"]["_resource_retry_task"] = retry_task
    wait_for_retry.set()
    await retry_task

    assert attempts == 2
    assert hass.data["victron_evse"]["_cards_registered"] is True
