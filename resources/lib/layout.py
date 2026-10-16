"""Grade compartilhada entre os quadros do Kodi e o compositor FFmpeg.

Nenhum elemento da interface precisa da existência de um Kodi em execução.
"""
import math

PAGE_SIZE = 16
VIEW_X = 160
VIEW_Y = 60
VIEW_W = 960
VIEW_H = 540
MIN_FPS = 12


def grid_shape(count):
    """Grade compacta de 1 a 16 vídeos, orientada a 16:9."""
    n = max(1, min(PAGE_SIZE, int(count)))
    cols = min(4, int(math.ceil(math.sqrt(n))))
    rows = int(math.ceil(n / cols))
    # Não criar uma coluna extra para a última fileira desnecessariamente.
    return cols, rows


def cell_geometry(count, width=VIEW_W, height=VIEW_H):
    """Dimensões do quadro e posições relativas ao mosaico."""
    cols, rows = grid_shape(count)
    # Todas as células têm tamanho igual; dimensões múltiplas de dois
    # preservam compatibilidade com vídeo YUV420.
    cw = max(2, (int(width) // cols) // 2 * 2)
    ch = max(2, (int(height) // rows) // 2 * 2)
    return cols, rows, cw, ch


def rectangles(count, x=VIEW_X, y=VIEW_Y, width=VIEW_W, height=VIEW_H):
    cols, _, cw, ch = cell_geometry(count, width, height)
    n = max(0, min(PAGE_SIZE, int(count)))
    return [(x + (i % cols) * cw, y + (i // cols) * ch, cw, ch)
            for i in range(n)]


def target_fps(count):
    """Mantém vídeo contínuo e reduz demanda quando a quantidade sobe."""
    if count <= 4:
        return 20
    if count <= 9:
        return 15
    return MIN_FPS


def page_count(count):
    return max(1, (max(0, count) + PAGE_SIZE - 1) // PAGE_SIZE)
