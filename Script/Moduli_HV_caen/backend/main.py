"""
main.py
=======
Backend FastAPI per il controllo HV di uno o più moduli CAEN (DT5780),
definiti in config.json.

Avvio:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

(oppure semplicemente: ./start.sh dalla root del progetto)

La cartella ../frontend viene servita come sito statico su /
L'API REST vive sotto /api, il monitor live sotto /ws/monitor
"""

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config_loader import ConfigError
from errors import ConnectionError_
from manager import manager

app = FastAPI(title="CAEN HV Control")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------- #
# Modelli richiesta
# --------------------------------------------------------------------- #
class ConnectRequest(BaseModel):
    apply_config: bool = True


class VSetRequest(BaseModel):
    voltage: float = Field(ge=0, le=8000, description="Tensione target in Volt")


class ISetRequest(BaseModel):
    current: float = Field(ge=0, le=10000, description="Limite di corrente target in uA")


class PowerRequest(BaseModel):
    on: bool


class RampRequest(BaseModel):
    ramp_up: float = Field(gt=0, le=500)
    ramp_down: float = Field(gt=0, le=500)


class ReloadConfigRequest(BaseModel):
    config_path: str | None = None


# --------------------------------------------------------------------- #
# Errori comuni -> HTTP
# --------------------------------------------------------------------- #
def _handle(exc: Exception):
    if isinstance(exc, ConfigError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConnectionError_):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (ValueError, NotImplementedError)):
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------------------------- #
# Moduli / configurazione
# --------------------------------------------------------------------- #
@app.get("/api/modules")
def list_modules():
    return manager.list_modules()


@app.get("/api/status")
def status_all():
    return manager.all_status()


@app.post("/api/config/reload")
def reload_config(req: ReloadConfigRequest):
    try:
        cfg = manager.reload_config(req.config_path)
        return {"ok": True, "modules": [m.name for m in cfg.modules]}
    except ConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------------------------- #
# Connessione per modulo
# --------------------------------------------------------------------- #
@app.post("/api/modules/{name}/connect")
def connect(name: str, req: ConnectRequest):
    try:
        driver = manager.get(name)
        info = driver.connect(apply_config=req.apply_config)
        return {"ok": True, "info": info}
    except Exception as e:
        _handle(e)


@app.post("/api/modules/{name}/disconnect")
def disconnect(name: str):
    try:
        driver = manager.get(name)
        driver.disconnect()
        return {"ok": True}
    except Exception as e:
        _handle(e)


@app.post("/api/modules/{name}/apply-config")
def apply_config(name: str):
    try:
        driver = manager.get(name)
        driver.apply_config()
        return {"ok": True}
    except Exception as e:
        _handle(e)


@app.get("/api/modules/{name}/status")
def module_status(name: str):
    try:
        driver = manager.get(name)
        return driver.get_status()
    except Exception as e:
        _handle(e)


# --------------------------------------------------------------------- #
# Canali
# --------------------------------------------------------------------- #
@app.post("/api/modules/{name}/channels/{channel}/vset")
def set_vset(name: str, channel: int, req: VSetRequest):
    try:
        driver = manager.get(name)
        driver.set_vset(channel, req.voltage)
        return {"ok": True}
    except Exception as e:
        _handle(e)


@app.post("/api/modules/{name}/channels/{channel}/iset")
def set_iset(name: str, channel: int, req: ISetRequest):
    try:
        driver = manager.get(name)
        driver.set_iset(channel, req.current)
        return {"ok": True}
    except Exception as e:
        _handle(e)


@app.post("/api/modules/{name}/channels/{channel}/power")
def set_power(name: str, channel: int, req: PowerRequest):
    try:
        driver = manager.get(name)
        driver.set_power(channel, req.on)
        return {"ok": True}
    except Exception as e:
        _handle(e)


@app.post("/api/modules/{name}/channels/{channel}/ramp")
def set_ramp(name: str, channel: int, req: RampRequest):
    try:
        driver = manager.get(name)
        driver.set_ramp(channel, req.ramp_up, req.ramp_down)
        return {"ok": True}
    except Exception as e:
        _handle(e)


# --------------------------------------------------------------------- #
# Monitor live (tutti i moduli)
# --------------------------------------------------------------------- #
@app.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            try:
                await websocket.send_json({"ok": True, "modules": manager.all_status()})
            except WebSocketDisconnect:
                print("WebSocket client disconnected")
                return
            except Exception as e:
                await websocket.send_json({"ok": False, "error": str(e)})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# --------------------------------------------------------------------- #
# Frontend statico
# --------------------------------------------------------------------- #
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
