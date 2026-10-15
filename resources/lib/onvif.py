"""ONVIF PTZ mínimo (WS-Security UsernameToken digest). Nunca registrar credenciais."""
import base64
import datetime
import hashlib
import os
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

SOAP = "http://www.w3.org/2003/05/soap-envelope"
PTZ = "http://www.onvif.org/ver20/ptz/wsdl"
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"

class PTZError(Exception):
    pass

def call(cam, command, inner="", timeout=3.0):
    user = cam.get("usuario", "admin")
    password = cam.get("senha", "")
    created = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = os.urandom(16)
    digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + password.encode()).digest()).decode()
    dest = "http://{}:{}/onvif/ptz_service".format(cam["ip"], cam.get("onvif_port", 5000))
    header = (
        '<wsse:Security xmlns:wsse="{wsse}" xmlns:wsu="{wsu}">'
        '<wsse:UsernameToken><wsse:Username>{user}</wsse:Username>'
        '<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</wsse:Password>'
        '<wsse:Nonce>{nonce}</wsse:Nonce><wsu:Created>{created}</wsu:Created>'
        '</wsse:UsernameToken></wsse:Security>'
    ).format(wsse=WSSE, wsu=WSU, user=escape(user), digest=digest,
             nonce=base64.b64encode(nonce).decode(), created=created)
    document = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="{soap}" xmlns:p="{ptz}" xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
        '<s:Header>{security}<wsa:Action>{ptz}/{op}</wsa:Action>'
        '<wsa:MessageID>urn:uuid:{uuid}</wsa:MessageID><wsa:To>{dest}</wsa:To></s:Header>'
        '<s:Body><p:{op}>{body}</p:{op}></s:Body></s:Envelope>'
    ).format(soap=SOAP, ptz=PTZ, security=header, op=command, uuid=uuid.uuid4(), dest=dest, body=inner)
    basic = base64.b64encode((user + ":" + password).encode()).decode()
    request = urllib.request.Request(dest, document.encode(),
                 {"Content-Type": "application/soap+xml; charset=utf-8",
                  "Authorization": "Basic " + basic}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            root = ET.fromstring(reply.read(100000))
    except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError) as ex:
        raise PTZError("Falha na comunicação ONVIF (" + type(ex).__name__ + ")") from None
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "Fault":
            raise PTZError("Câmera recusou o comando ONVIF")
    if not any(e.tag.rsplit("}", 1)[-1] == command + "Response" for e in root.iter()):
        raise PTZError("Câmera não confirmou " + command)
    return root

def move(cam, pan=0.0, tilt=0.0, zoom=0.0):
    token = escape(cam.get("onvif_profile", "IPCProfilesToken0"))
    body = ('<p:ProfileToken>{}</p:ProfileToken><p:Velocity>'
            '<p:PanTilt x="{:.2f}" y="{:.2f}"/><p:Zoom x="{:.2f}"/>'
            '</p:Velocity><p:Timeout>PT1S</p:Timeout>').format(token, pan, tilt, zoom)
    return call(cam, "ContinuousMove", body)

def stop(cam):
    token = escape(cam.get("onvif_profile", "IPCProfilesToken0"))
    body = "<p:ProfileToken>{}</p:ProfileToken><p:PanTilt>true</p:PanTilt><p:Zoom>true</p:Zoom>".format(token)
    try:
        call(cam, "Stop", body)
    except PTZError:
        move(cam, 0, 0, 0)

def nudge(cam, pan=0.0, tilt=0.0, zoom=0.0, seconds=0.38):
    try:
        move(cam, pan, tilt, zoom)
        time.sleep(seconds)
    finally:
        # Parada garantida mesmo em caso de erro de movimento.
        try:
            stop(cam)
        except PTZError:
            pass
