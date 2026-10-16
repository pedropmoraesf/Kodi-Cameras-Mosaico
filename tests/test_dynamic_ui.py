"""Teste de distribuição, foco e paginação com controles Kodi simulados."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch
from resources.lib.layout import PAGE_SIZE, rectangles

class FakeButton:
    def __init__(self):
        self.visible = True
        self.position = (0,0)
        self.width = 0
        self.height = 0
        self.label = ''
    def setVisible(self, value): self.visible = value
    def setPosition(self, x, y): self.position = (x,y)
    def setWidth(self, value): self.width = value
    def setHeight(self, value): self.height = value
    def setLabel(self, value): self.label = value

class DynamicUITest(unittest.TestCase):
    def test_resize_and_second_page(self):
        with patch.dict(sys.modules, {
            'xbmcgui': types.SimpleNamespace(WindowDialog=object),
            'xbmc': types.SimpleNamespace()
        }):
            sys.modules.pop('resources.lib.ui', None)
            ui = importlib.import_module('resources.lib.ui')
            class Window(ui.Mosaic):
                def setFocus(self, control): self.control = control
            w = object.__new__(Window)
            w.cams = [dict(ip='192.0.2.%d'%i, nome='Câmera %d'%i, ativa=True)
                      for i in range(1,5)]
            w.page=w.slot=w.focus=0
            w.ptz_mode=False
            w.tiles = [FakeButton() for _ in range(PAGE_SIZE)]
            w.toolbar = [FakeButton() for _ in range(8)]
            w.buttons = w.tiles + w.toolbar
            w.title = FakeButton()
            w.hint = FakeButton()
            try:
                w.render()
                self.assertEqual(sum(x.visible for x in w.tiles),4)
                self.assertEqual(w.tiles[0].width,480)
                w.cams.append(dict(ip='192.0.2.5', nome='Câmera 5', ativa=True))
                w.render()
                self.assertEqual(sum(x.visible for x in w.tiles),5)
                self.assertEqual(w.tiles[4].width,320)
                x,y,wid,hei = rectangles(5)[4]
                self.assertEqual(w.tiles[4].position,
                                 (x,y+hei-max(20,min(38,hei//5))))
                for i in range(6,19):
                    w.cams.append(dict(ip='192.0.2.%d'%i, nome='Câmera %d'%i, ativa=True))
                w.render()
                self.assertEqual(sum(x.visible for x in w.tiles),16)
                self.assertIn('Página 1/2',w.title.label)
                w.page=1
                w.render()
                self.assertEqual(sum(x.visible for x in w.tiles),2)
                self.assertEqual(w.tiles[0].width,480)
                self.assertIn('Página 2/2',w.title.label)
                w.set_focus(15)
                self.assertEqual(w.focus,1)
                w.cams[16]['rtsp_hidden']=True
                w.render()
                self.assertEqual(sum(x.visible for x in w.tiles),1)
            finally:
                sys.modules.pop('resources.lib.ui', None)

if __name__ == '__main__':
    unittest.main()
