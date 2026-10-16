"""Testes da grade adaptativa e da paginação de 16 câmeras."""
import unittest
from resources.lib.layout import (PAGE_SIZE, VIEW_W, VIEW_H,
                                  grid_shape, cell_geometry, rectangles,
                                  page_count, target_fps)
from resources.lib.live import build_command, probe_page
from unittest.mock import patch


class DynamicLayoutTest(unittest.TestCase):
    def test_shapes_and_pages(self):
        expected = {0:(1,1), 1:(1,1), 2:(2,1), 3:(2,2),
                    4:(2,2), 5:(3,2), 6:(3,2),
                    7:(3,3), 9:(3,3), 10:(4,3), 16:(4,4)}
        for n, shape in expected.items():
            with self.subTest(n=n):
                self.assertEqual(grid_shape(n), shape)
                self.assertEqual(len(rectangles(n)), n)
        self.assertEqual(page_count(0), 1)
        self.assertEqual(page_count(16), 1)
        self.assertEqual(page_count(17), 2)
        self.assertEqual(page_count(33), 3)
        self.assertEqual(PAGE_SIZE, 16)

    def test_no_rectangles_overlap(self):
        for n in (1,2,3,5,9,10,16):
            rs=rectangles(n)
            for i,(x,y,w,h) in enumerate(rs):
                self.assertGreater(w, 0)
                self.assertGreater(h, 0)
                self.assertLessEqual(x+w,160+VIEW_W)
                self.assertLessEqual(y+h,60+VIEW_H)
                for j, (a,b,c,d) in enumerate(rs):
                    if j<=i:continue
                    self.assertTrue(x+w<=a or a+c<=x or y+h<=b or b+d<=y)

    def test_video_tracks_visible_camera_count(self):
        for n in (0,1,2,3,4,5,9,10,16,17):
            sources = [dict(online=False, camera=dict(ip='192.0.2.%d'%(i+1))) for i in range(n)]
            command = build_command(sources)
            k = min(max(n,1),16)
            self.assertEqual(command.count('-i'),k)
            graph = command[command.index('-filter_complex')+1]
            if k==1:
                self.assertNotIn('xstack=',graph)
            else:
                self.assertIn('xstack=inputs=%d'%k,graph)
            cols,rows,cw,ch = cell_geometry(k)
            self.assertIn('scale=%d:%d'%(cw,ch),graph)
            self.assertEqual(command[command.index('-r')+1],str(target_fps(k)))

    def test_probe_no_four_camera_truncation(self):
        cams = [dict(ip='192.0.2.%d'%(i+1)) for i in range(18)]
        def fake(cam, timeout=4):
            return dict(camera=cam,online=False,transport=None)
        with patch('resources.lib.live.probe',side_effect=fake):
            status = probe_page(cams)
        self.assertEqual(len(status),16)
        self.assertEqual(status[15]['camera'], cams[15])


if __name__ == '__main__':
    unittest.main()
