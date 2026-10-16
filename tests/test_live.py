"""Testes sem reprodução Kodi e sem conexão com câmeras particulares."""
import json
import unittest
from unittest.mock import patch
from urllib import error, request
from resources.lib import live


class LiveVideoTest(unittest.TestCase):
    def test_continuous_video_instead_of_jpegs(self):
        cam = dict(ip='192.0.2.22', porta=554, caminho='/onvif2',
                   usuario='test', senha='example')
        sources = [dict(camera=cam, online=True, transport='udp'),
                   dict(camera=cam, online=False, transport=None)]
        cmd = live.build_command(sources, {cam['ip']: 1.5})
        self.assertEqual(cmd.count('-i'), 4)
        self.assertEqual(cmd[cmd.index('-f', cmd.index('-filter_complex'))+1], 'mpegts')
        self.assertEqual(cmd[-1], 'pipe:1')
        self.assertNotIn('image2', cmd)
        self.assertNotIn('fps=1,', ' '.join(cmd))
        self.assertIn('xstack=inputs=4', cmd[cmd.index('-filter_complex')+1])
        self.assertIn('crop=trunc(iw/1.500', cmd[cmd.index('-filter_complex')+1])
        self.assertIn('udp', cmd)
        self.assertIn('-re', cmd)  # Slate a velocidade real.

    def test_fps_range(self):
        low = live.build_command([], fps=2)
        high = live.build_command([], fps=99)
        self.assertEqual(low[low.index('-r')+1], '10')
        self.assertEqual(high[high.index('-r')+1], '30')

    def test_unavailable_rtsp_yields_black_slate(self):
        cam = dict(ip='192.0.2.33', porta=554, caminho='/onvif2',
                   usuario='test', senha='example')
        with patch('resources.lib.live.subprocess.run', side_effect=OSError):
            status = live.probe(cam, timeout=1)
        self.assertFalse(status['online'])
        self.assertIsNone(status['transport'])
        cmd = live.build_command([status])
        self.assertIn('color=c=black:s=480x270:r=20', cmd)

    def test_http_only_localhost_and_token(self):
        server = live.MosaicStream()
        try:
            self.assertEqual(server.httpd.server_address[0], '127.0.0.1')
            with self.assertRaises(error.HTTPError) as cm:
                request.urlopen('http://127.0.0.1:%d/mosaic.ts?key=wrong' %
                                server.httpd.server_address[1], timeout=2)
            self.assertEqual(cm.exception.code, 404)
            self.assertIn('key=', server.url)
        finally:
            server.close()


if __name__ == '__main__':
    unittest.main()
