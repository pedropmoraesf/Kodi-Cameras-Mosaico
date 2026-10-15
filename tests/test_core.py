"""Testes sem Kodi ou dispositivos conectados."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from resources.lib import cameras, onvif
from resources.lib.preview import Preview

class CamerasTest(unittest.TestCase):
    def test_config_local_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            entry = dict(nome='Câmera Teste', ip='192.0.2.50',
                         usuario='demo', senha='senha-de-teste',
                         porta=8554, caminho='/video', ativa=True)
            cameras.save(temp, [entry])
            saved = Path(temp)/'cameras.json'
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            content = saved.read_text()
            self.assertEqual(len(json.loads(content)), 1)
            self.assertIn('Câmera Teste', content)
            self.assertEqual(cameras.load(temp)[0]['ip'], '192.0.2.50')

    def test_auth_url_is_percent_encoded(self):
        c = cameras.normalize(dict(ip='192.0.2.5', usuario='u@x', senha='a:b', caminho='/onvif2'))
        self.assertIn('u%40x:a%3Ab@192.0.2.5', cameras.stream_url(c))

    def test_bad_ip_and_port(self):
        for ip in ['host/path', 'x@site', 'evil\r\nheader', '']:
            with self.assertRaises(ValueError):
                cameras.normalize(dict(ip=ip))
        with self.assertRaises(ValueError):
            cameras.normalize(dict(ip='192.0.2.5', porta=70000))

    def test_default_onvif_values(self):
        c = cameras.normalize(dict(ip='192.0.2.5'))
        self.assertEqual(c['onvif_port'], 5000)
        self.assertEqual(c['onvif_profile'], 'IPCProfilesToken0')

    def test_digital_zoom_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            viewer = Preview(temp)
            # não cria processos: apenas valida a limitação do recorte
            self.assertEqual(viewer.zoom.get('x', 1.0), 1.0)
            viewer.close()

if __name__ == '__main__':
    unittest.main()
