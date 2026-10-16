"""Bridge RTSP -> mosaico H.264/MPEG-TS servido apenas em localhost.

Até 16 feeds contínuos por página compõem um único vídeo reproduzido pelo Kodi.
Nenhum comando manipula o player até o usuário abrir explicitamente o addon.
"""
import concurrent.futures
import http.server
import secrets
import socketserver
import subprocess
import threading
from .cameras import stream_url
from .layout import PAGE_SIZE, VIEW_W, VIEW_H, cell_geometry, target_fps


def preferred_transport(cam):
    return 'udp' if cam.get('caminho', '').lower() in ('/onvif1', '/onvif2') else 'tcp'


def probe(cam, timeout=4):
    """Verifica vídeo em UDP ou TCP. Falhas geram quadro preto, não travam o mosaico."""
    for transport in (preferred_transport(cam), 'tcp' if preferred_transport(cam) == 'udp' else 'udp'):
        command = ['ffprobe', '-v', 'error', '-rtsp_transport', transport,
                   '-select_streams', 'v:0', '-show_entries', 'stream=codec_name',
                   '-of', 'csv=p=0', stream_url(cam)]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=timeout, check=False)
            if result.returncode == 0 and result.stdout.strip():
                return dict(camera=cam, transport=transport, online=True)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return dict(camera=cam, transport=None, online=False)


def probe_page(cams, timeout=4):
    """Até 16 câmeras por página, verificadas em até quatro threads."""
    cameras = list(cams[:PAGE_SIZE])
    if not cameras:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(cameras))) as pool:
        futures = [pool.submit(probe, cam, timeout) for cam in cameras]
        return [f.result() for f in futures]


def build_command(sources, zoom=None, fps=None, width=VIEW_W, height=VIEW_H):
    """Compor 1..16 câmeras dinamicamente em um único vídeo.

    A grade acompanha a quantidade real de fontes sem criar slots extras.
    Fontes indisponíveis usam vídeo preto contínuo com o mesmo FPS.
    """
    zoom = zoom or {}
    source_list = list(sources[:PAGE_SIZE])
    if not source_list:
        source_list = [None]
    count = len(source_list)
    cols, rows, cw, ch = cell_geometry(count, width, height)
    fps = max(10, min(30, int(fps if fps is not None else target_fps(count))))
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-fflags', '+genpts']
    filters = []
    for index, src in enumerate(source_list):
        if src and src.get('online'):
            command += ['-rtsp_transport', src['transport'], '-i',
                        stream_url(src['camera'])]
        else:
            command += ['-re', '-f', 'lavfi', '-i',
                        'color=c=black:s=%dx%d:r=%d' % (cw, ch, fps)]
        z = 1.
        if src:
            z = max(1., min(4., float(zoom.get(src['camera']['ip'], 1.))))
        ops = []
        if z > 1.01:
            ops.append('crop=trunc(iw/%.3f/2)*2:trunc(ih/%.3f/2)*2' % (z, z))
        ops += ['scale=%d:%d:flags=fast_bilinear' % (cw, ch),
                'fps=%d' % fps, 'setsar=1', 'setpts=PTS-STARTPTS']
        filters.append('[%d:v]%s[v%d]' % (index, ','.join(ops), index))

    if count == 1:
        filters.append('[v0]format=yuv420p[out]')
    else:
        positions = ['%d_%d' % ((i % cols) * cw, (i // cols) * ch)
                     for i in range(count)]
        filters.append(''.join('[v%d]' % i for i in range(count)) +
                       'xstack=inputs=%d:layout=%s:shortest=0:fill=black,' %
                       (count, '|'.join(positions)) +
                       'format=yuv420p[out]')

    command += ['-filter_complex', ';'.join(filters), '-map', '[out]',
                '-an', '-sn', '-dn', '-c:v', 'libx264', '-preset', 'ultrafast',
                '-tune', 'zerolatency', '-threads', '2', '-r', str(fps),
                '-g', str(fps), '-keyint_min', str(fps),
                '-sc_threshold', '0', '-pix_fmt', 'yuv420p',
                '-b:v', '1800k', '-maxrate', '2500k', '-bufsize', '500k',
                '-flush_packets', '1', '-muxdelay', '0', '-muxpreload', '0',
                '-f', 'mpegts', 'pipe:1']
    return command


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MosaicStream:
    """Servidor limitado a 127.0.0.1, com token exclusivo e um cliente ativo."""
    def __init__(self):
        self.token = secrets.token_urlsafe(24)
        self.command = None
        self.process = None
        self.lock = threading.RLock()
        self.closed = False
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                return  # Nunca imprimir dados privados nem URLs.

            def do_GET(self):
                if self.path != '/mosaic.ts?key=' + outer.token:
                    self.send_error(404)
                    return
                with outer.lock:
                    if outer.closed or outer.command is None:
                        self.send_error(503)
                        return
                    command = list(outer.command)
                    outer._terminate_locked()
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp2t')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                            start_new_session=True)
                except OSError:
                    return
                with outer.lock:
                    if outer.closed:
                        proc.terminate()
                        return
                    outer.process = proc
                try:
                    while not outer.closed:
                        chunk = proc.stdout.read(1316)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                except (ConnectionError, OSError):
                    pass
                finally:
                    with outer.lock:
                        if outer.process is proc:
                            outer._terminate_locked()
                    if proc.poll() is None:
                        proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)

        self.httpd = _ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return 'http://127.0.0.1:%d/mosaic.ts?key=%s' % (
            self.httpd.server_address[1], self.token)

    def configure(self, sources, zoom=None, fps=None):
        with self.lock:
            self.command = build_command(sources, zoom, fps)

    def _terminate_locked(self):
        proc = self.process
        self.process = None
        if proc and proc.poll() is None:
            proc.terminate()

    def close(self):
        with self.lock:
            self.closed = True
            self._terminate_locked()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
