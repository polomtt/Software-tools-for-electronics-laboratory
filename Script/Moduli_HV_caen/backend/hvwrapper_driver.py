"""
hvwrapper_driver.py
====================
Driver per moduli HV standalone (es. CAEN V6533) via CAENHVWrapper
(binding ufficiale py-caen-libs -> caen_libs.caenhvwrapper), tipicamente
raggiunti tramite un bridge VME-USB come il V1718.

A differenza di CAENDPP (dove i parametri HV sono campi fissi di una
struct), qui i parametri di canale (VSet, VMon, IMon, Pw, Status, RUp,
RDwn, ...) sono identificati per NOME STRINGA e la libreria li espone a
runtime tramite get_ch_param_info()/get_ch_param_prop(). Questo driver
scopre i nomi disponibili alla connessione invece di averli hardcoded,
scegliendo tra un elenco di alias comuni per essere robusto a piccole
differenze tra board/firmware.

Sequenza reale CAENHVWrapper (da manuale ufficiale):
    Device.open(SystemType.V65XX, LinkType.USB, "LinkNum_ConetNode_VMEBaseAddress")
        -> get_crate_map()  per scoprire slot/canali della board
        -> get_ch_param_info(slot, channel)  per scoprire i nomi dei parametri
        -> get_ch_param() / set_ch_param()   per leggere/scrivere
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
    last_error: str | None = None

    # Statica, letta una sola volta alla connessione: "+" / "-" / None se
    # la board non espone un parametro di polarita' leggibile.
    polarity: str | None = None


# Alias comuni per i nomi parametro sulle board V65xx/HV standalone.
# La libreria li espone case-sensitive: proviamo diverse varianti note
# invece di assumerne una sola.
_PARAM_ALIASES = {
    "vset": ("VSet", "V0Set", "Vset"),
    "vmon": ("VMon", "Vmon"),
    "imon": ("IMon", "IMonH", "IMonL", "Imon"),
    "power": ("Pw", "POn", "Pw1"),
    "ramp_up": ("RUp", "RampUp"),
    "ramp_down": ("RDwn", "RDWN", "RampDown"),
    "status": ("Status", "ChStatus"),
    # Polarita': fissata dall'hardware della scheda (non e' scrivibile), ma
    # la libreria spesso la espone in sola lettura come parametro ENUM/STRING.
    "polarity": ("Pol", "POL", "Polarity"),
}


class HVWrapperModuleDriver:
    """
    Driver per un singolo modulo HV standalone, stessa interfaccia
    pubblica di ModuleDriver (module_driver.py) cosi' manager.py e
    main.py possono usarli in modo intercambiabile.
    """

    def __init__(self, config: ModuleConfig):
        self.config = config
        self.name = config.name
        self.model = config.model
        self.N_CHANNELS = config.n_channels

        self._connected = False
        self._device = None          # caen_libs.caenhvwrapper.Device
        self._slot: Optional[int] = None
        self._link_info: dict = {}

        # Nomi parametro effettivamente trovati sulla board (risolti alla
        # connessione, una volta per tutte).
        self._param_names: dict[str, str] = {}

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
            from caen_libs import caenhvwrapper

            system_type = self._parse_system_type(caenhvwrapper, self.model)
            link_type = self._parse_link_type(caenhvwrapper, conn_cfg.link_type)
            arg = f"{int(conn_cfg.link_num)}_{int(conn_cfg.conet_node)}_{str(conn_cfg.vme_base).strip()}"

            device = caenhvwrapper.Device.open(system_type, link_type, arg)

            try:
                boards = device.get_crate_map()

                slot = None
                board_info = None
                for i, b in enumerate(boards):
                    if b is not None:
                        slot = i
                        board_info = b
                        break

                if slot is None:
                    raise ConnectionError_(
                        f"Modulo '{self.name}': nessuna board rilevata sul bus "
                        f"(controlla indirizzo VME e collegamento del bridge)."
                    )

                if board_info.n_channel < self.N_CHANNELS:
                    raise ConnectionError_(
                        f"Modulo '{self.name}': la board dichiara {board_info.n_channel} "
                        f"canali, ma config.json ne richiede {self.N_CHANNELS}."
                    )

                self._device = device
                self._slot = slot

                self._param_names = self._resolve_param_names(device, slot, 0)
                self._resolve_polarities(device, slot)

                self._link_info = {
                    "link_type": link_type.name,
                    "link_num": int(conn_cfg.link_num),
                    "conet_node": int(conn_cfg.conet_node),
                    "vme_base": str(conn_cfg.vme_base),
                    "slot": slot,
                    "model": board_info.model,
                    "description": board_info.description,
                    "serial": str(board_info.serial_number),
                    "channels": int(board_info.n_channel),
                    "firmware": str(board_info.fw_version),
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
                "Impossibile importare caen_libs.caenhvwrapper. "
                "Installa py-caen-libs e le librerie CAEN native "
                "(CAENHVWrapper, CAENVMELib/CAENComm necessari per il bridge) — vedi install.sh."
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
        self._slot = None
        self._link_info = {}
        self._param_names = {}

    @property
    def connected(self) -> bool:
        return self._connected

    # =======================================================================
    # RISOLUZIONE NOMI PARAMETRO (dinamica, non hardcoded)
    # =======================================================================

    def _resolve_param_names(self, device, slot: int, channel: int) -> dict[str, str]:
        available = set(device.get_ch_param_info(slot, channel))
        resolved: dict[str, str] = {}

        for key, aliases in _PARAM_ALIASES.items():
            for alias in aliases:
                if alias in available:
                    resolved[key] = alias
                    break

        missing = [k for k in ("vset", "vmon", "power") if k not in resolved]
        if missing:
            raise ConnectionError_(
                f"Modulo '{self.name}': non trovo i parametri {missing} tra quelli "
                f"esposti dalla board ({sorted(available)}). Aggiungi il nome giusto "
                f"a _PARAM_ALIASES in hvwrapper_driver.py."
            )

        return resolved

    def _resolve_polarities(self, device, slot: int):
        """
        Legge la polarita' di ogni canale, se la board la espone. Statica
        (non cambia mentre il modulo e' acceso), quindi la leggiamo una
        sola volta qui invece che ad ogni refresh. Un fallimento su un
        singolo canale non blocca la connessione: la polarita' resta None
        e la UI semplicemente non la mostra per quel canale.
        """
        if "polarity" not in self._param_names:
            return

        param_name = self._param_names["polarity"]

        for channel in self._channels:
            try:
                prop = device.get_ch_param_prop(slot, channel, param_name)
                raw = device.get_ch_param(slot, [channel], param_name)[0]

                label: str | None = None
                if isinstance(raw, str):
                    label = raw.strip()
                elif prop.enum:
                    idx = int(raw)
                    if 0 <= idx < len(prop.enum):
                        label = prop.enum[idx].strip()

                if label:
                    normalized = label.upper()
                    if normalized.startswith("POS") or normalized == "+":
                        label = "+"
                    elif normalized.startswith("NEG") or normalized == "-":
                        label = "-"

                with self._lock:
                    self._channels[channel].polarity = label

            except Exception:
                # Non tutte le board/firmware espongono questo parametro in
                # lettura in questo modo: lasciamo semplicemente None.
                pass

    def _param(self, key: str) -> str:
        try:
            return self._param_names[key]
        except KeyError as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': parametro '{key}' non disponibile su questa board."
            ) from exc

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
        slot = self._require_slot()

        try:
            device.set_ch_param(slot, [channel], self._param("vset"), voltage)
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore impostando VSet del canale {channel}: {exc}"
            ) from exc

        with self._lock:
            self._channels[channel].vset = voltage
        self._try_refresh(channel)

    def set_power(self, channel: int, on: bool):
        self._check_connected()
        self._check_channel(channel)

        device = self._require_device()
        slot = self._require_slot()

        try:
            device.set_ch_param(slot, [channel], self._param("power"), 1 if on else 0)
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore cambiando power del canale {channel}: {exc}"
            ) from exc

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
        slot = self._require_slot()

        try:
            if "ramp_up" in self._param_names:
                device.set_ch_param(slot, [channel], self._param("ramp_up"), ramp_up)
            if "ramp_down" in self._param_names:
                device.set_ch_param(slot, [channel], self._param("ramp_down"), ramp_down)
        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore impostando la rampa del canale {channel}: {exc}"
            ) from exc

        self._try_refresh(channel)

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
                "polarity": s.polarity,
            }

    # =======================================================================
    # HELPERS
    # =======================================================================

    @staticmethod
    def _parse_system_type(caenhvwrapper, model: str):
        normalized = model.strip().upper()
        try:
            return caenhvwrapper.SystemType[normalized]
        except KeyError:
            # V6533/V6534/ecc. sono board della famiglia V65XX
            if normalized.startswith("V65"):
                return caenhvwrapper.SystemType.V65XX
            raise ValueError(
                f"Impossibile mappare model='{model}' a un caenhvwrapper.SystemType. "
                f"Usa uno dei nomi validi (es. 'V65XX', 'SY1527', 'SY4527', ...)."
            )

    @staticmethod
    def _parse_link_type(caenhvwrapper, value: str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "tcpip": caenhvwrapper.LinkType.TCPIP,
            "tcp": caenhvwrapper.LinkType.TCPIP,
            "rs232": caenhvwrapper.LinkType.RS232,
            "serial": caenhvwrapper.LinkType.RS232,
            "caenet": caenhvwrapper.LinkType.CAENET,
            "usb": caenhvwrapper.LinkType.USB,
            "optlink": caenhvwrapper.LinkType.OPTLINK,
            "optical": caenhvwrapper.LinkType.OPTLINK,
            "optical_link": caenhvwrapper.LinkType.OPTLINK,
            "usb_vcp": caenhvwrapper.LinkType.USB_VCP,
            "usb3": caenhvwrapper.LinkType.USB3,
            "a4818": caenhvwrapper.LinkType.A4818,
        }
        try:
            return mapping[normalized]
        except KeyError as exc:
            valid = ", ".join(sorted(mapping))
            raise ValueError(
                f"Tipo di collegamento non supportato: {value!r}. Valori accettati: {valid}"
            ) from exc

    def _require_device(self):
        if self._device is None:
            raise ConnectionError_(f"Modulo '{self.name}': device non inizializzato.")
        return self._device

    def _require_slot(self) -> int:
        if self._slot is None:
            raise ConnectionError_(f"Modulo '{self.name}': slot non inizializzato.")
        return self._slot

    def _refresh_channels(self):
        for channel in range(self.N_CHANNELS):
            self._try_refresh(channel)

    def _try_refresh(self, channel: int):
        try:
            self._refresh_channel(channel)
        except ConnectionError_ as exc:
            with self._lock:
                self._channels[channel].last_error = str(exc)

    def _refresh_channel(self, channel: int):
        device = self._require_device()
        slot = self._require_slot()

        try:
            vmon = float(device.get_ch_param(slot, [channel], self._param("vmon"))[0])
            imon = 0.0
            if "imon" in self._param_names:
                imon = float(device.get_ch_param(slot, [channel], self._param("imon"))[0])

            power_raw = device.get_ch_param(slot, [channel], self._param("power"))[0]
            power_on = bool(power_raw)

            ramp_up = None
            ramp_down = None
            if "ramp_up" in self._param_names:
                ramp_up = float(device.get_ch_param(slot, [channel], self._param("ramp_up"))[0])
            if "ramp_down" in self._param_names:
                ramp_down = float(device.get_ch_param(slot, [channel], self._param("ramp_down"))[0])

            status_text = ""
            if "status" in self._param_names:
                status_raw = device.get_ch_param(slot, [channel], self._param("status"))[0]
                status_text = self._decode_status_bitmask(int(status_raw))

            with self._lock:
                s = self._channels[channel]
                s.vmon = vmon
                s.imon = imon
                s.power_on = power_on
                if ramp_up is not None:
                    s.ramp_up = ramp_up
                if ramp_down is not None:
                    s.ramp_down = ramp_down
                s.status = status_text or self._infer_status(power_on, s.vset, vmon)
                s.last_error = None

        except Exception as exc:
            raise ConnectionError_(
                f"Modulo '{self.name}': errore leggendo stato HV del canale {channel}: {exc}"
            ) from exc

    @staticmethod
    def _infer_status(power_on: bool, vset: float, vmon: float) -> str:
        if not power_on:
            return "OFF"
        if vmon < vset - 0.5:
            return "RAMPING UP"
        return "ON"

    @staticmethod
    def _decode_status_bitmask(status: int) -> str:
        """
        Il parametro Status delle board V65xx e' tipicamente una bitmask
        (bit0=ON, bit1=RUP, bit2=RDWN, bit3=OVC, bit4=OVV, ...). Decodifica
        solo i bit piu' comuni; se non riconosciuto ritorna stringa vuota
        cosi' il chiamante usa _infer_status come fallback.
        """
        if status & 0x08:  # OVC - overcurrent
            return "OVERCURRENT"
        if status & 0x02:  # RUP - ramping up
            return "RAMPING UP"
        if status & 0x04:  # RDWN - ramping down
            return "RAMPING DOWN"
        if status & 0x01:  # ON
            return "ON"
        return "OFF"

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
                    "polarity": s.polarity,
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
