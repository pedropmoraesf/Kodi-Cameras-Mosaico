# -*- coding: utf-8 -*-
"""Ponto de entrada do complemento para Kodi 21+."""
import os
import xbmc
import xbmcaddon
import xbmcvfs
from resources.lib.ui import Mosaic

def main():
    addon = xbmcaddon.Addon()
    profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    screen = Mosaic(profile)
    monitor = xbmc.Monitor()
    try:
        screen.show()
        while not screen.closed and not monitor.waitForAbort(0.7):
            screen.refresh()
    finally:
        screen.finish()
        screen.close()

if __name__ == '__main__':
    main()
