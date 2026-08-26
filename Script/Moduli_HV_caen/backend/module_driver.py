"""
module_driver.py
=================
Driver per un singolo modulo CAEN (fisicamente un DT5780), guidato da un
ModuleConfig letto da config.json. Parla con l'hardware reale tramite
CAENDPP (binding ufficiale py-caen-libs -> caen_libs.caendpplib).

Sequenza reale CAENDPP:
    Device.open()
        -> ConnectionParams(...)
        -> Device.add_board(...)
        -> board_id
        -> operazioni HV sul board_id
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

from config_loader import ModuleConfig, ConfigError
from errors import ConnectionError_


@dataclass
class ChannelState:
    vset: float = 0.0
    vmon: float = 0.0
    imon: float = 0.0

    power_on: bool = False

    ramp_up: float = 50.0
    ramp_down: float = 50.0

    status: str = "OFF"

    # Ultimo errore capitato leggendo il monitor di QUESTO canale (None se
    # l'ultima lettura e' andata a buon fine). Non blocca i comandi: e'
    # solo diagnostico, per capire dalla UI cosa non va senza congelare
    # tutto il resto.
    last_error: str | None = None


class ModuleDriver:
    """Driver per un singolo modulo CAEN, configurato da un ModuleConfig."""

    def __init__(self, config: ModuleConfig):
        self.config = config
        self.name = config.name
        self.model = config.model
        self.N_CHANNELS = config.n_channels

        self._connected = False
        self._device = None                     # caen_libs.caendpplib.Device
        self._board_id: Optional[int] = None
        self._handle = None
        self._link_info: dict = {}

        # Stato iniziale dei canali = valori di default dalla config
        self._channels = {
            c.channel: ChannelState(
                vset=c.vset,
                ramp_up=c.ramp_up,
                ramp_down=c.ramp_down,
            )
            for c in config.channels
        }

        self._lock = threading.Lock()

    # =======================================================================
    # CONFIGURAZIONE
    # =======================================================================

    def update_config(self, config: ModuleConfig):
        """Sostituisce la config del modulo. Consentito solo se disconnesso."""
        if self._connected:
            raise ConnectionError_(
                f"Modulo '{self.name}': disconnetti prima di ricaricare la configurazione."
            )
        if config.name != self.name:
            raise ConfigError(
                f"Nome modulo cambiato ('{self.name}' -> '{config.name}'): "
                f"ricrea il driver invece di aggiornarlo."
            )

        self.config = config
        self.model = config.model
        self.N_CHANNELS = config.n_channels
        self._channels = {
            c.channel: ChannelState(
                vset=c.vset,
                ramp_up=c.ramp_up,
                ramp_down=c.ramp_down,
            )
            for c in config.channels
        }

    def apply_config(self):
        """
        Spinge su hardware VSet/RampUp/RampDown letti dalla config per
        tutti i canali di questo modulo. Non tocca il power (resta
        un'azione esplicita dell'utente, per sicurezza).
        """
        self._check_connected()
        for ch_cfg in self.config.channels:
            self.set_vset(ch_cfg.channel, ch_cfg.vset)
            self.set_ramp(ch_cfg.channel, ch_cfg.ramp_up, ch_cfg.ramp_down)

    # =======================================================================
    # CONNESSIONE
    # =======================================================================

    def connect(self, apply_config: bool = True) -> dict:
        if self._connected:
            self.disconnect()

        conn_cfg = self.config.connection

        try:
            from caen_libs import caendpplib

            connection_type = self._parse_connection_type(caendpplib, conn_cfg.link_type)
            vme_base_address = self._parse_vme_base(conn_cfg.vme_base)

            device = caendpplib.Device.open()

            try:
                params = caendpplib.ConnectionParams(
                    link_type=connection_type,
                    link_num=int(conn_cfg.link_num),
                    conet_node=int(conn_cfg.conet_node),
                    vme_base_address=vme_base_address,
                )

                board_id = device.add_board(params)
                info = device.get_dpp_info(board_id)

                expected_model = getattr(caendpplib.BoardModel, self.model.upper(), None)
                if expected_model is not None and info.model != expected_model:
                    raise ConnectionError_(
                        f"Modulo '{self.name}': board collegata ma modello inatteso "
                        f"({info.model_name}, atteso {self.model})."
                    )

                if info.hv_channels < self.N_CHANNELS:
                    raise ConnectionError_(
                        f"Modulo '{self.name}': la board dichiara {info.hv_channels} "
                        f"canali HV, ma config.json ne richiede {self.N_CHANNELS}."
                    )

                self._device = device
                self._handle = device.handle
                self._board_id = board_id

                self._link_info = {
                    "link_type": connection_type.name,
                    "link_num": int(conn_cfg.link_num),
                    "conet_node": int(conn_cfg.conet_node),
                    "vme_base": vme_base_address,
                    "board_id": board_id,
                    "model": info.model_name.strip(),
                    "serial": str(info.serial_number),
                    "firmware": info.roc_firmware_rel.strip(),
                    "channels": int(info.channels),
                    "hv_channels": int(info.hv_channels),
                }

                self._connected = True
                self._refresh_channels()

                if apply_config:
                    self.apply_config()

                return dict(self._link_info)

            except Exception:
                try:
                    device.close()
                except Exception:
                    pass
                raise

        except ImportError as exc:
            raise ConnectionError_(
                "Impossibile importare caen_libs.caendpplib. "
                "Installa py-caen-libs e le librerie CAEN native "
                "(CAENDPPLib, CAENComm/driver necessari) — vedi install.sh."
            ) from exc

        except Exception as exc:
            if isinstance(exc, (ConnectionError_, ConfigError)):
                raise
            raise ConnectionError_(
                f"Modulo '{self.name}': errore durante la connessione: {exc}"
            ) from exc

    def disconnect(self):
        if self._device is not None:
            try:
                self._device.close()
            finally:
                self._device = None

        self._connected = False
        self._handle = None
        self._board_id = None
        self._link_info = {}

    @property
    def connected(self) -> bool:
        return self._connected

    # =======================================================================
    # HV - VSET / POWER / RAMP
    # =======================================================================

    def set_vset(self, channel: int, voltage: float):
        self._check_connected()
        self._check_channel(channel)

        voltage = float(voltage)
        if voltage < 0:
            raise ValueError("La tensione non puo' essere negativa.")

        device = self._require_device()
        board_id = self._require_board_id()

        try:
            config = device.get_hv_channel_configuration(board_id, channel)

            if voltage > config.v_max:
                raise ValueError(
                    f"VSet={voltage} V supera VMax={config.v_max} V del canale {channel}."
                )

            config.v_set = voltage
            device.set_hv_channel_configuration(board_id, channel, config)
            # Il comando e' andato a buon fine a questo punto: se la
            # rilettura successiva fallisce non consideriamo il comando
            # fallito, solo il monitor momentaneamente non aggiornato
            # (vedi last_error nello stato del canale).
            self._try_refresh(channel)

        except ValueError:
            raise
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore impostando VSet del canale {channel}: {exc}"
            ) from exc

    def set_power(self, channel: int, on: bool):
        self._check_connected()
        self._check_channel(channel)

        device = self._require_device()
        board_id = self._require_board_id()

        try:
            device.set_hv_channel_power_on(board_id, channel, bool(on))
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore cambiando power del canale {channel}: {exc}"
            ) from exc

        # Il comando ON/OFF e' arrivato all'hardware: aggiorniamo lo stato
        # locale subito (cosi' la UI riflette il cambio anche se la
        # rilettura hardware sotto fallisce) e proviamo a risincronizzare
        # dal device senza far fallire la chiamata se il monitor ha un
        # problema momentaneo.
        with self._lock:
            self._channels[channel].power_on = bool(on)
            self._channels[channel].status = "RAMPING UP" if on else "RAMPING DOWN"

        self._try_refresh(channel)

    def set_ramp(self, channel: int, ramp_up: float, ramp_down: float):
        self._check_connected()
        self._check_channel(channel)

        ramp_up = float(ramp_up)
        ramp_down = float(ramp_down)
        if ramp_up <= 0:
            raise ValueError("RampUp deve essere > 0 V/s.")
        if ramp_down <= 0:
            raise ValueError("RampDown deve essere > 0 V/s.")

        device = self._require_device()
        board_id = self._require_board_id()

        try:
            config = device.get_hv_channel_configuration(board_id, channel)
            config.ramp_up = ramp_up
            config.ramp_down = ramp_down
            device.set_hv_channel_configuration(board_id, channel, config)
            self._try_refresh(channel)
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore impostando la rampa del canale {channel}: {exc}"
            ) from exc

    # =======================================================================
    # STATUS
    # =======================================================================

    def get_status(self) -> dict:
        self._check_connected()
        self._refresh_channels()
        with self._lock:
            return self._make_status_dict()

    def get_channel_status(self, channel: int) -> dict:
        self._check_connected()
        self._check_channel(channel)
        self._try_refresh(channel)
        with self._lock:
            s = self._channels[channel]
            return {
                "channel": channel,
                "vset": s.vset,
                "vmon": round(s.vmon, 2),
                "imon": round(s.imon, 3),
                "power_on": s.power_on,
                "status": s.status,
                "ramp_up": s.ramp_up,
                "ramp_down": s.ramp_down,
                "last_error": s.last_error,
                "polarity": None,  # non applicabile alle schede DPP (HV integrata)
            }

    def get_hv_configuration(self, channel: int) -> dict:
        self._check_connected()
        self._check_channel(channel)

        device = self._require_device()
        board_id = self._require_board_id()

        try:
            config = device.get_hv_channel_configuration(board_id, channel)
            return {
                "channel": channel,
                "vset": float(config.v_set),
                "iset": float(config.i_set),
                "ramp_up": float(config.ramp_up),
                "ramp_down": float(config.ramp_down),
                "vmax": float(config.v_max),
                "power_down_mode": config.pw_down_mode.name,
            }
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore leggendo configurazione HV "
                f"del canale {channel}: {exc}"
            ) from exc

    # =======================================================================
    # HELPERS CAENDPP
    # =======================================================================

    @staticmethod
    def _parse_connection_type(caendpplib, value: str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "usb": caendpplib.ConnectionType.USB,
            "optical": caendpplib.ConnectionType.PCI_OPTICAL_LINK,
            "optical_link": caendpplib.ConnectionType.PCI_OPTICAL_LINK,
            "pci_optical_link": caendpplib.ConnectionType.PCI_OPTICAL_LINK,
            "conet": caendpplib.ConnectionType.PCI_OPTICAL_LINK,
            "eth": caendpplib.ConnectionType.ETH,
            "ethernet": caendpplib.ConnectionType.ETH,
            "serial": caendpplib.ConnectionType.SERIAL,
            "usb_a4818": caendpplib.ConnectionType.USB_A4818,
            "eth_v4718": caendpplib.ConnectionType.ETH_V4718,
            "usb_v4718": caendpplib.ConnectionType.USB_V4718,
        }
        try:
            return mapping[normalized]
        except KeyError as exc:
            valid = ", ".join(sorted(mapping))
            raise ValueError(
                f"Tipo di collegamento non supportato: {value!r}. Valori accettati: {valid}"
            ) from exc

    @staticmethod
    def _parse_vme_base(value: str | int) -> int:
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if not text:
            return 0
        try:
            return int(text, 0)
        except ValueError:
            try:
                return int(text, 16)
            except ValueError as exc:
                raise ValueError(f"VME base address non valido: {value!r}") from exc

    def _require_device(self):
        if self._device is None:
            raise ConnectionError_(f"Modulo '{self.name}': device non inizializzato.")
        return self._device

    def _require_board_id(self) -> int:
        if self._board_id is None:
            raise ConnectionError_(f"Modulo '{self.name}': board non inizializzata.")
        return self._board_id

    def _refresh_channels(self):
        """
        Aggiorna tutti i canali. Un canale che fallisce NON blocca gli
        altri: l'errore viene registrato in last_error di quel canale
        (visibile nella UI) invece di far fallire l'intera risposta.
        """
        for channel in range(self.N_CHANNELS):
            self._try_refresh(channel)

    def _try_refresh(self, channel: int):
        """Come _refresh_channel, ma non solleva eccezioni: registra
        l'errore in last_error del canale e mantiene gli ultimi valori
        noti invece di propagare il fallimento a chi ha chiamato."""
        try:
            self._refresh_channel(channel)
        except ConnectionError_ as exc:
            with self._lock:
                self._channels[channel].last_error = str(exc)

    def _refresh_channel(self, channel: int):
        device = self._require_device()
        board_id = self._require_board_id()

        try:
            config = device.get_hv_channel_configuration(board_id, channel)
            power_on = device.get_hv_channel_power_on(board_id, channel)
            monitoring = device.read_hv_channel_monitoring(board_id, channel)
            status_code = device.get_hv_channel_status(board_id, channel)

            try:
                status_string = device.get_hv_status_string(board_id, status_code)
            except Exception:
                status_string = f"STATUS_{status_code}"

            status_string = status_string.strip()

            with self._lock:
                s = self._channels[channel]
                s.vset = float(config.v_set)
                s.ramp_up = float(config.ramp_up)
                s.ramp_down = float(config.ramp_down)
                s.power_on = bool(power_on)
                s.vmon = float(monitoring.v_mon)
                s.imon = float(monitoring.i_mon)
                s.status = self._normalize_status(status_string, s.power_on, s.vset, s.vmon)
                s.last_error = None  # lettura riuscita: cancella eventuale errore precedente

        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore leggendo stato HV del canale {channel}: {exc}"
            ) from exc

    @staticmethod
    def _normalize_status(status: str, power_on: bool, vset: float, vmon: float) -> str:
        text = status.strip()
        if not text:
            if not power_on:
                return "OFF"
            if vmon < vset - 0.5:
                return "RAMPING UP"
            return "ON"

        upper = text.upper()
        if "OVER" in upper and "CURRENT" in upper:
            return "OVERCURRENT"
        if "RAMP" in upper and "UP" in upper:
            return "RAMPING UP"
        if "RAMP" in upper and "DOWN" in upper:
            return "RAMPING DOWN"
        if upper in {"ON", "POWER ON", "POWER_ON"}:
            return "ON"
        if upper in {"OFF", "POWER OFF", "POWER_OFF"}:
            return "OFF"
        return text

    def _make_status_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "connected": self._connected,
            "link_info": dict(self._link_info),
            "channels": {
                ch: {
                    "vset": s.vset,
                    "vmon": round(s.vmon, 2),
                    "imon": round(s.imon, 3),
                    "power_on": s.power_on,
                    "status": s.status,
                    "ramp_up": s.ramp_up,
                    "ramp_down": s.ramp_down,
                    "last_error": s.last_error,
                    "polarity": None,
                }
                for ch, s in self._channels.items()
            },
        }

    def _check_connected(self):
        if not self._connected:
            raise ConnectionError_(
                f"Modulo '{self.name}' non connesso. Chiama /api/modules/{self.name}/connect prima."
            )

    def _check_channel(self, channel: int):
        if channel not in self._channels:
            raise ValueError(f"Canale {channel} non valido (0-{self.N_CHANNELS - 1}).")
