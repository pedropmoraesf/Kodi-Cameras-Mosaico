"""Testa negociação de RTSP sem acessar câmeras particulares."""
import tempfile
import unittest
from unittest.mock import patch
from resources.lib.preview import Preview

class FakeProcess:
    def poll(self):
        return None
    def terminate(self):
        pass
    def wait(self, timeout=None):
        return 0

class PreviewTransportTest(unittest.TestCase):
    def test_yoosee_prefers_udp_without_unsupported_timeout(self):
        cam = dict(ip='192.0.2.8', caminho='/onvif2',
                   porta=554, usuario='test', senha='example')
        commands = []
        def launch(command, **_kw):
            commands.append(command)
            return FakeProcess()
        with tempfile.TemporaryDirectory() as folder:
            preview = Preview(folder)
            with patch('resources.lib.preview.shutil.which', return_value='/usr/bin/ffmpeg'), patch(
                'resources.lib.preview.subprocess.Popen', side_effect=launch):
                preview.start('camera', cam)
                self.assertEqual(commands[-1][commands[-1].index('-rtsp_transport') + 1], 'udp')
                self.assertNotIn('-rw_timeout', commands[-1])
                preview.workers['camera']['start'] -= 11
                preview.sync([('camera', cam)])
                self.assertEqual(commands[-1][commands[-1].index('-rtsp_transport') + 1], 'tcp')
                preview.close()

if __name__ == '__main__':
    unittest.main()
