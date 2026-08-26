"""
config_loader.py
=================
Carica e valida il file di configurazione JSON.

Schema atteso (config.json), un blocco per ogni modulo CAEN collegato:

{
  "modules": [
    {
      "name": "DT5780_A",
      "model": "DT5780",
      "connection": {
        "link_type": "USB",
        "link_num": 0,
        "conet_node": 0,
        "vme_base": "0"
      },
      "n_channels": 2,
      "channels": [
        { "channel": 0, "vset": 800.0,  "ramp_up": 50.0, "ramp_down": 50.0 },
        { "channel": 1, "vset": 1000.0, "ramp_up": 50.0, "ramp_down": 50.0 }
      ]
    }
  ]
}

- "name" e' un identificativo libero, univoco, usato dall'API e dalla UI
  per riferirsi al modulo (utile se ne colleghi piu' di uno).
- "model" e' il nome del modello board (es. "DT5780"), usato per
  verificare che l'hardware collegato sia quello atteso.
- "n_channels" deve combaciare con il numero di elementi in "channels".
- I "channel" devono essere gli interi 0..n_channels-1, ciascuno una sola volta.
- "vset" >= 0, "ramp_up" > 0, "ramp_down" > 0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Errore nel file di configurazione."""


@dataclass
class ConnectionConfig:
    link_type: str
    link_num: int
    conet_node: int
    vme_base: str


@dataclass
class ChannelConfig:
    channel: int
    vset: float
    ramp_up: float
    ramp_down: float


@dataclass
class ModuleConfig:
    name: str
    model: str
    connection: ConnectionConfig
    n_channels: int
    channels: list[ChannelConfig] = field(default_factory=list)
    # "dpp" (default) = schede digitizer/DPP tipo DT5780, via CAENDPPLib.
    # "hvwrapper" = schede/crate HV standalone (es. V6533), via CAENHVWrapper.
    driver: str = "dpp"

    def channel(self, ch: int) -> ChannelConfig:
        for c in self.channels:
            if c.channel == ch:
                return c
        raise ConfigError(f"Nessuna configurazione trovata per il canale {ch}.")


@dataclass
class AppConfig:
    modules: list[ModuleConfig]

    def module(self, name: str) -> ModuleConfig:
        for m in self.modules:
            if m.name == name:
                return m
        raise ConfigError(f"Nessun modulo chiamato '{name}' in configurazione.")


def _require(d: dict, key: str, path: str):
    if key not in d:
        raise ConfigError(f"Campo mancante '{key}' in {path}.")
    return d[key]


def _load_connection(raw: dict, path: str) -> ConnectionConfig:
    conn_raw = _require(raw, "connection", path)
    return ConnectionConfig(
        link_type=str(_require(conn_raw, "link_type", f"{path}.connection")),
        link_num=int(_require(conn_raw, "link_num", f"{path}.connection")),
        conet_node=int(_require(conn_raw, "conet_node", f"{path}.connection")),
        vme_base=str(_require(conn_raw, "vme_base", f"{path}.connection")),
    )


def _load_channels(raw: dict, n_channels: int, path: str) -> list[ChannelConfig]:
    channels_raw = _require(raw, "channels", path)
    if not isinstance(channels_raw, list):
        raise ConfigError(f"'{path}.channels' deve essere una lista.")

    if len(channels_raw) != n_channels:
        raise ConfigError(
            f"{path}: 'n_channels'={n_channels} ma 'channels' contiene "
            f"{len(channels_raw)} elementi: devono coincidere."
        )

    channels: list[ChannelConfig] = []
    seen_indices: set[int] = set()

    for i, ch_raw in enumerate(channels_raw):
        ch_path = f"{path}.channels[{i}]"
        ch_num = int(_require(ch_raw, "channel", ch_path))
        vset = float(_require(ch_raw, "vset", ch_path))
        ramp_up = float(_require(ch_raw, "ramp_up", ch_path))
        ramp_down = float(_require(ch_raw, "ramp_down", ch_path))

        if ch_num < 0 or ch_num >= n_channels:
            raise ConfigError(
                f"{ch_path}.channel={ch_num} fuori range (atteso 0..{n_channels - 1})."
            )
        if ch_num in seen_indices:
            raise ConfigError(f"{path}: canale {ch_num} definito più di una volta.")
        seen_indices.add(ch_num)

        if vset < 0:
            raise ConfigError(f"{ch_path}.vset non può essere negativo.")
        if ramp_up <= 0:
            raise ConfigError(f"{ch_path}.ramp_up deve essere > 0.")
        if ramp_down <= 0:
            raise ConfigError(f"{ch_path}.ramp_down deve essere > 0.")

        channels.append(
            ChannelConfig(channel=ch_num, vset=vset, ramp_up=ramp_up, ramp_down=ramp_down)
        )

    channels.sort(key=lambda c: c.channel)
    return channels


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)

    if not path.exists():
        raise ConfigError(
            f"File di configurazione non trovato: {path}. "
            f"Copia config.example.json in config.json e adattalo."
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON non valido in {path}: {exc}") from exc

    modules_raw = _require(raw, "modules", str(path))
    if not isinstance(modules_raw, list) or len(modules_raw) == 0:
        raise ConfigError("'modules' deve essere una lista non vuota.")

    modules: list[ModuleConfig] = []
    seen_names: set[str] = set()

    for i, mod_raw in enumerate(modules_raw):
        mod_path = f"modules[{i}]"

        name = str(_require(mod_raw, "name", mod_path)).strip()
        if not name:
            raise ConfigError(f"{mod_path}.name non può essere vuoto.")
        if name in seen_names:
            raise ConfigError(f"Nome modulo duplicato: '{name}'.")
        seen_names.add(name)

        model = str(_require(mod_raw, "model", mod_path)).strip()

        driver = str(mod_raw.get("driver", "dpp")).strip().lower()
        if driver not in ("dpp", "hvwrapper"):
            raise ConfigError(
                f"{mod_path}.driver='{driver}' non valido (atteso 'dpp' o 'hvwrapper')."
            )

        connection = _load_connection(mod_raw, mod_path)

        n_channels = int(_require(mod_raw, "n_channels", mod_path))
        if n_channels <= 0:
            raise ConfigError(f"{mod_path}.n_channels deve essere maggiore di zero.")

        channels = _load_channels(mod_raw, n_channels, mod_path)

        modules.append(
            ModuleConfig(
                name=name,
                model=model,
                connection=connection,
                n_channels=n_channels,
                channels=channels,
                driver=driver,
            )
        )

    return AppConfig(modules=modules)
