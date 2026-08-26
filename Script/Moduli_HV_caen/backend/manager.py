"""
manager.py
==========
Tiene in memoria un ModuleDriver per ciascun modulo dichiarato in
config.json e offre un punto unico da cui FastAPI pesca gli oggetti,
per nome modulo.
"""

from __future__ import annotations

import os
from pathlib import Path

from config_loader import AppConfig, ConfigError, ModuleConfig, load_config
from module_driver import ModuleDriver
from hvwrapper_driver import HVWrapperModuleDriver
from errors import ConnectionError_

# Percorso del file di configurazione: relativo a questo file di default,
# cosi' funziona a prescindere dalla cartella da cui lanci uvicorn.
# Sovrascrivibile con la variabile d'ambiente CAEN_CONFIG_PATH.
DEFAULT_CONFIG_PATH = Path(
    os.environ.get("CAEN_CONFIG_PATH", str(Path(__file__).resolve().parent / "config.json"))
)


def _make_driver(m: ModuleConfig):
    """Sceglie la classe driver giusta in base a ModuleConfig.driver."""
    if m.driver == "hvwrapper":
        return HVWrapperModuleDriver(m)
    return ModuleDriver(m)  # "dpp", default


class CAENManager:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH):
        self._config_path = Path(config_path)
        self.config: AppConfig = load_config(self._config_path)
        self._modules: dict[str, ModuleDriver | HVWrapperModuleDriver] = {
            m.name: _make_driver(m) for m in self.config.modules
        }

    # ------------------------------------------------------------------ #
    def list_modules(self) -> list[dict]:
        return [
            {"name": d.name, "model": d.model, "n_channels": d.N_CHANNELS, "connected": d.connected}
            for d in self._modules.values()
        ]

    def get(self, name: str) -> ModuleDriver | HVWrapperModuleDriver:
        try:
            return self._modules[name]
        except KeyError as exc:
            raise ConfigError(f"Nessun modulo chiamato '{name}'.") from exc

    def all_status(self) -> dict:
        result = {}
        for name, d in self._modules.items():
            result[name] = d.get_status() if d.connected else {
                "name": d.name, "model": d.model, "connected": False,
                "link_info": {}, "channels": {},
            }
        return result

    # ------------------------------------------------------------------ #
    def reload_config(self, config_path: str | Path | None = None) -> AppConfig:
        """
        Ricarica config.json. Moduli gia' connessi vengono lasciati stare
        (per non staccare hardware attivo a sorpresa) — disconnetti prima
        i moduli che vuoi ricaricare, se e' cambiato il loro numero di canali.
        """
        if config_path is not None:
            self._config_path = Path(config_path)

        new_config = load_config(self._config_path)

        for m in new_config.modules:
            existing = self._modules.get(m.name)
            if existing is None:
                self._modules[m.name] = _make_driver(m)
            elif not existing.connected:
                existing.update_config(m)
            # se e' connesso e la config e' cambiata, lo segnaliamo lasciandolo
            # con la vecchia config finche' non viene disconnesso esplicitamente

        # rimuovi moduli non piu' presenti in config (solo se disconnessi)
        removed = set(self._modules) - {m.name for m in new_config.modules}
        for name in removed:
            if not self._modules[name].connected:
                del self._modules[name]

        self.config = new_config
        return new_config

    def disconnect_all(self):
        for d in self._modules.values():
            if d.connected:
                d.disconnect()


manager = CAENManager()
