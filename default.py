# -*- coding: utf-8 -*-
"""Ponto de entrada do complemento para Kodi 21+."""
import os
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from resources.lib.ui import Mosaic

def main():
    # Abrir o addon enquanto outro vídeo está tocando nunca deve substituí-lo.
    if xbmc.Player().isPlayingVideo():
        xbmcgui.Dialog().notification('Câmeras',
            'Finalize o vídeo atual antes de abrir o mosaico.',
            xbmcgui.NOTIFICATION_INFO, 3500)
        return
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
