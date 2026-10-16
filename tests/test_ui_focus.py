"""Verifica inicialização de foco sem precisar executar o Kodi."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

class FocusTests(unittest.TestCase):
    def test_on_init_sets_focus_after_window_opens(self):
        stub = types.SimpleNamespace(WindowDialog=object)
        with patch.dict(sys.modules, {'xbmcgui':stub, 'xbmc':types.SimpleNamespace()}):
            sys.modules.pop('resources.lib.ui', None)
            ui = importlib.import_module('resources.lib.ui')
            class Window(ui.Mosaic):
                def set_focus(self, index):
                    self.last_focus = index
            window = object.__new__(Window)
            window.focus = 0
            window.initialized = True
            window.onInit()
            self.assertEqual(window.last_focus, 0)
        sys.modules.pop('resources.lib.ui', None)

if __name__ == '__main__':
    unittest.main()
