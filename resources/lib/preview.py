"""Pré-visualização RTSP leve para controles ControlImage do Kodi."""
import os
import shutil
import subprocess
import time
from pathlib import Path
from .cameras import stream_url

class Preview:
    """Um processo ffmpeg por câmera visível; não interfere no xbmc.Player."""
    def __init__(self, cache_dir, max_width=600):
        self.folder = Path(cache_dir)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.width = max_width
        self.workers = {}
        self.zoom = {}
        # FFmpeg pode negociar somente TCP ou somente UDP, conforme a câmera.
        self.transports = {}
        self.presented = {}
        self.snapshots = {}
        # Remover arquivos temporários abandonados por execuções anteriores.
        for old in self.folder.glob('frame_*.jpg'):
            try:
                old.unlink()
            except OSError:
                pass

    def image_path(self, key):
        return self.folder / ('cam_%s.jpg' % key)

    def frame_for_display(self, key):
        """Disponibiliza um nome novo para cada JPEG; Kodi não recarrega a mesma URL.

        Cria hard link para o quadro que FFmpeg substituiu atomicamente.
        Retém quatro quadros por câmera enquanto a UI termina o carregamento.
        """
        source = self.image_path(key)
        try:
            stat = source.stat()
        except OSError:
            return None
        version = (stat.st_ino, stat.st_mtime_ns)
        previous = self.presented.get(key)
        if previous and previous[0] == version:
            return previous[1]
        # Inode no nome previne colisão se o processo reiniciar rapidamente.
        target = self.folder / ('frame_%s_%s_%s.jpg' %
                                (key, stat.st_ino, stat.st_mtime_ns))
        try:
            os.link(source, target)
        except FileExistsError:
            pass
        except OSError:
            try:
                shutil.copyfile(source, target)
            except OSError:
                return None
        history = self.snapshots.setdefault(key, [])
        history.append(target)
        while len(history) > 4:
            old = history.pop(0)
            try:
                old.unlink()
            except OSError:
                pass
        self.presented[key] = (version, target)
        return target

    def start(self, key, cam):
        self.stop(key)
        # Fluxos Yoosee /onvif1 e /onvif2 frequentemente exigem UDP.
        default_transport = 'udp' if cam.get('caminho', '').lower() in ('/onvif1', '/onvif2') else 'tcp'
        self.transports.setdefault(key, default_transport)
        if shutil.which('ffmpeg') is None:
            return
        path = self.image_path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        z = self.zoom.get(key, 1.0)
        # O recorte digital é centralizado; só é aplicado na câmera escolhida.
        if z > 1.01:
            crop = 'crop=trunc(iw/{:.2f}/2)*2:trunc(ih/{:.2f}/2)*2'.format(z, z)
            vf = crop + ',scale={}:{}:force_original_aspect_ratio=decrease,fps=1'.format(self.width, 338)
        else:
            vf = 'scale={}:{}:force_original_aspect_ratio=decrease,fps=1'.format(self.width, 338)
        cmd = [
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-rtsp_transport', self.transports.get(key, 'tcp'),
            '-i', stream_url(cam), '-an', '-sn', '-dn',
            '-threads', '1', '-vf', vf, '-q:v', '6',
            '-f', 'image2', '-update', '1', '-atomic_writing', '1', '-y', str(path)
        ]
        # As credenciais ficam na linha de comando do ffmpeg (não em logs).
        # Nunca registrar cmd, exception repr ou URL RTSP.
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            self.workers[key] = {'proc': p, 'cam': dict(cam), 'start': time.monotonic()}
        except OSError:
            pass

    def sync(self, cameras):
        """Executa apenas para câmeras da página atual."""
        expected = {str(i): dict(cam) for i, cam in cameras}
        for key in list(self.workers):
            if key not in expected or self.workers[key]['cam'] != expected[key]:
                self.stop(key)
        for key, cam in expected.items():
            entry = self.workers.get(key)
            if entry is None:
                self.start(key, cam)
                continue
            age = time.monotonic() - entry['start']
            # Sem quadros por tempo prolongado, tentar o outro transporte.
            # Uma câmera que já produziu um JPEG mantém o transporte válido.
            if age > 9 and not self.image_path(key).is_file():
                current = self.transports.get(key, 'tcp')
                self.transports[key] = 'udp' if current == 'tcp' else 'tcp'
                self.start(key, cam)
            elif entry['proc'].poll() is not None and age > 12:
                self.start(key, cam)

    def set_digital_zoom(self, key, cam, delta):
        current = self.zoom.get(key, 1.0)
        new = round(max(1., min(4., current + delta)), 2)
        if new != current:
            self.zoom[key] = new
            self.start(key, cam)
        return new

    def stop(self, key):
        item = self.workers.pop(key, None)
        if not item:
            return
        proc = item['proc']
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.2)

    def close(self):
        for key in list(self.workers):
            self.stop(key)
        for frames in self.snapshots.values():
            for frame in frames:
                try:
                    frame.unlink()
                except OSError:
                    pass
        self.snapshots.clear()
        self.presented.clear()
