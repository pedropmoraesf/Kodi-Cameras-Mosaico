"""Gerenciador de configurações privadas das câmeras."""
import json
from pathlib import Path
import os
import tempfile
from urllib.parse import quote

def normalize(c):
    host = str(c.get("ip", "")).strip()
    if not host or any(x in host for x in " /\\:@?#\n\r"):
        raise ValueError("Host inválido")
    port = int(c.get("porta", 554))
    ptzport = int(c.get("onvif_port", 5000))
    if not (1 <= port <= 65535 and 1 <= ptzport <= 65535):
        raise ValueError("Porta inválida")
    path = str(c.get("caminho", "/onvif2"))
    if not path.startswith("/") or "\n" in path or "\r" in path:
        raise ValueError("Caminho inválido")
    return {"nome": str(c.get("nome") or host)[:80], "ip": host,
            "porta": port, "caminho": path, "usuario": str(c.get("usuario", "admin")),
            "senha": str(c.get("senha", "")), "onvif_port": ptzport,
            "onvif_profile": str(c.get("onvif_profile", "IPCProfilesToken0")),
            "ativa": bool(c.get("ativa", True)),
            "rtsp_hidden": bool(c.get("rtsp_hidden", False))}
def stream_url(c):
    user = quote(c["usuario"], safe="")
    pw = quote(c["senha"], safe="")
    auth = (user + ":" + pw + "@") if user or pw else ""
    return "rtsp://" + auth + c["ip"] + ":" + str(c["porta"]) + c["caminho"]

def save(profile, cameras):
    directory = Path(profile)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / "cameras.json"
    data = json.dumps([normalize(c) for c in cameras], indent=2, ensure_ascii=False)
    fd, temp = tempfile.mkstemp(prefix=".cameras-", dir=str(directory), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(data + "\n")
        os.replace(temp, target)
        os.chmod(target, 0o600)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def load(profile, migrate=True):
    directory = Path(profile)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / "cameras.json"
    if target.exists():
        raw = json.loads(target.read_text(encoding="utf-8"))
    else:
        raw = []
        legacy = Path.home() / ".config/yoosee/cameras.json"
        if migrate and legacy.is_file():
            try:
                raw = json.loads(legacy.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw = []
        if isinstance(raw, dict):
            raw = raw.get("cameras", [])
        if not isinstance(raw, list):
            raw = []
        save(directory, raw)
    if isinstance(raw, dict):
        raw = raw.get("cameras", [])
    result = []
    for cam in raw:
        try:
            entry = normalize(cam)
            if entry["ip"] not in [x["ip"] for x in result]:
                result.append(entry)
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return result
