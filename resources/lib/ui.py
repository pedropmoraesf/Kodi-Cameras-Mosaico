"""Interface de mosaico navegável pelo controle remoto Kodi."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
import xbmc
import xbmcgui
from . import cameras, onvif
from .live import MosaicStream, probe_page

TOOLBAR = ('+ Adicionar câmera', 'Editar', 'Ocultar', 'Excluir',
           'Página -', 'Página +', 'Zoom -', 'Zoom +')
BACK = (10, 92)

class Mosaic(xbmcgui.WindowDialog):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.cams = cameras.load(profile)
        self.page = self.slot = self.focus = 0
        self.ptz_mode = self.closed = False
        self.initialized = False
        self.live = MosaicStream()
        self.player = xbmc.Player()
        self.playback_url = self.live.url
        self.zoom_factors = {}
        self.stream_job = None
        self.stream_generation = 0
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.pending = None
        self.last_click = (None, 0.)
        self.addControl(xbmcgui.ControlImage(0, 0, 1280, 720,
                         os.path.join(os.path.dirname(os.path.dirname(__file__)), 'media', 'background.png')))
        self.title = xbmcgui.ControlLabel(25, 17, 1180, 42, '',
                       font='font30', textColor='0xFFFFFFFF')
        self.addControl(self.title)
        self.hint = xbmcgui.ControlLabel(25, 662, 1230, 23, '',
                      font='font13', textColor='0xFFE7EACB')
        self.note_label = xbmcgui.ControlLabel(25, 690, 1230, 23, '',
                      font='font13', textColor='0xFFABDDFD')
        self.addControl(self.hint)
        self.addControl(self.note_label)
        # Um único vídeo H.264 (960x540), composto a partir de quatro RTSP.
        # ControlVideoWindow exibe o vídeo do player em vez de quatro JPEGs.
        self.addControl(xbmcgui.ControlVideoWindow(160, 60, 960, 540))
        self.tiles = []
        for pos in range(4):
            x, y = 160 + 480 * (pos % 2), 60 + 270 * (pos // 2)
            button = xbmcgui.ControlButton(x, y + 225, 480, 44, 'Sem câmera')
            self.addControl(button)
            self.tiles.append(button)
        self.toolbar = []
        for i, label in enumerate(TOOLBAR):
            button = xbmcgui.ControlButton(25 + i * 154, 624, 150, 35, label)
            self.addControl(button)
            self.toolbar.append(button)
        self.buttons = self.tiles + self.toolbar
        self.render()

    def onInit(self):
        """O Kodi só aceita o foco inicial após a janela estar visível."""
        self.set_focus(self.focus)
        if not self.initialized:
            self.initialized = True
            self.request_live()

    def visible(self):
        return [c for c in self.cams if c.get('ativa', True)
                and not c.get('rtsp_hidden', False)]

    def page_cams(self):
        return self.visible()[self.page*4:self.page*4+4]

    def selected(self):
        page = self.page_cams()
        return page[self.slot] if self.slot < len(page) else None

    def message(self, msg):
        self.note_label.setLabel(msg)

    def set_focus(self, index):
        self.focus = max(0, min(len(self.buttons)-1, index))
        if self.focus < 4: self.slot = self.focus
        try: self.setFocus(self.buttons[self.focus])
        except RuntimeError: pass

    def render(self):
        pages = max(1, (len(self.visible())+3)//4)
        self.page = min(self.page, pages-1)
        page = self.page_cams()
        for i in range(4):
            if i < len(page):
                prefix = 'PTZ ▶ ' if self.ptz_mode and i == self.slot else ('► ' if self.slot == i else '')
                self.tiles[i].setLabel(prefix + page[i]['nome'])
            else:
                self.tiles[i].setLabel('— Sem câmera —')
        self.title.setLabel('CÂMERAS | MOSAICO    Página %d/%d' % (self.page+1, pages))
        self.hint.setLabel('PTZ: setas movimentam; OK/Voltar retorna à seleção' if self.ptz_mode
             else 'Setas: navegação | OK: PTZ | 1/3: zoom | Menu: outras opções')
        self.set_focus(self.focus)

    def owns_playback(self):
        try:
            return self.player.isPlayingVideo() and self.player.getPlayingFile().startswith(
                self.playback_url.split('?')[0])
        except (RuntimeError, OSError):
            return False

    def request_live(self):
        if not self.initialized or self.closed:
            return
        self.stream_generation += 1
        self.stop_own_playback()
        self.stream_job = (self.stream_generation,
                           self.executor.submit(probe_page, list(self.page_cams())))
        self.message('Conectando aos vídeos RTSP (sem conversão em JPEG)...')

    def stop_own_playback(self):
        if self.owns_playback():
            self.player.stop()

    def refresh(self):
        if self.stream_job and self.stream_job[1].done():
            generation, future = self.stream_job
            self.stream_job = None
            if generation == self.stream_generation and not self.closed:
                try:
                    sources = future.result()
                    if self.player.isPlayingVideo() and not self.owns_playback():
                        self.message('Outro vídeo está em reprodução; mosaico não foi iniciado.')
                    else:
                        self.live.configure(sources, self.zoom_factors)
                        self.player.play(self.playback_url, windowed=True)
                        online = sum(s['online'] for s in sources)
                        self.message('Mosaico ao vivo: %d/%d câmeras conectadas, 20 FPS.' %
                                     (online, len(sources)))
                except Exception:
                    self.message('Não foi possível iniciar o mosaico de vídeo.')
        if self.pending and self.pending.done():
            try:
                self.pending.result()
                self.message('Comando PTZ executado.')
            except Exception:
                self.message('PTZ não confirmado; confira suporte, porta e perfil ONVIF.')
            self.pending = None

    def persist(self):
        cameras.save(self.profile, self.cams)
        self.ptz_mode = False
        self.render()
        self.request_live()

    def change_page(self, amount):
        maxpage = max(0, (len(self.visible())-1)//4)
        nextpage = max(0, min(maxpage, self.page+amount))
        if nextpage != self.page:
            self.page, self.slot, self.focus = nextpage, 0, 0
            self.ptz_mode = False
            self.render()
            self.request_live()

    def zoom(self, delta):
        cam = self.selected()
        if cam:
            current = self.zoom_factors.get(cam['ip'], 1.)
            factor = round(max(1., min(4., current + delta)), 2)
            self.zoom_factors[cam['ip']] = factor
            self.request_live()
            self.message('Zoom digital: %.2fx, atualizando vídeo...' % factor)

    def move(self, pan=0., tilt=0., zoom=0.):
        cam = self.selected()
        if cam and (self.pending is None or self.pending.done()):
            self.pending = self.executor.submit(onvif.nudge, dict(cam),
                            pan=pan, tilt=tilt, zoom=zoom, seconds=0.32)
            self.message('Movimento ONVIF solicitado: '+cam['nome'])

    def add_camera(self):
        dialog = xbmcgui.Dialog()
        host = dialog.input('IP ou hostname da câmera').strip()
        if not host: return
        if any(c['ip'] == host for c in self.cams):
            dialog.ok('Câmeras', 'Este endereço já está cadastrado.')
            return
        name = dialog.input('Nome da câmera', defaultt=host).strip() or host
        user = dialog.input('Usuário RTSP/ONVIF', defaultt='admin').strip()
        secret = dialog.input('Senha da câmera',
                 option=getattr(xbmcgui, 'ALPHANUM_HIDE_INPUT', 0))
        path = dialog.input('Caminho RTSP', defaultt='/onvif2').strip() or '/onvif2'
        rtsp_port = dialog.input('Porta RTSP', defaultt='554', type=xbmcgui.INPUT_NUMERIC)
        onvif_port = dialog.input('Porta ONVIF', defaultt='5000', type=xbmcgui.INPUT_NUMERIC)
        try:
            cam = cameras.normalize(dict(ip=host, nome=name, usuario=user,
                senha=secret, caminho=path, porta=rtsp_port or 554,
                onvif_port=onvif_port or 5000))
        except (ValueError, TypeError):
            dialog.ok('Câmeras', 'IP, caminho ou portas inválidos.')
            return
        self.cams.append(cam)
        self.page = (len(self.visible())-1)//4
        self.focus = self.slot = (len(self.visible())-1)%4
        self.persist()
        self.message('Câmera adicionada. O cadastro permanece local.')

    def edit_camera(self):
        cam = self.selected()
        if not cam: return
        dialog = xbmcgui.Dialog()
        name = dialog.input('Nome', defaultt=cam['nome']).strip()
        if not name: return
        path = dialog.input('Caminho RTSP', defaultt=cam['caminho']).strip()
        user = dialog.input('Usuário', defaultt=cam['usuario']).strip()
        secret = dialog.input('Nova senha (vazio mantém a atual)',
                      option=getattr(xbmcgui, 'ALPHANUM_HIDE_INPUT', 0))
        rtsp_port = dialog.input('Porta RTSP', defaultt=str(cam.get('porta', 554)),
                                 type=xbmcgui.INPUT_NUMERIC)
        onvif_port = dialog.input('Porta ONVIF', defaultt=str(cam.get('onvif_port', 5000)),
                                  type=xbmcgui.INPUT_NUMERIC)
        changes = dict(cam, nome=name, caminho=path, usuario=user,
                       porta=rtsp_port or cam.get('porta',554),
                       onvif_port=onvif_port or cam.get('onvif_port',5000))
        if secret: changes['senha'] = secret
        try: updated = cameras.normalize(changes)
        except (ValueError, TypeError):
            dialog.ok('Câmeras', 'Dados inválidos.')
            return
        self.cams[self.cams.index(cam)] = updated
        self.persist()
        self.message('Cadastro atualizado.')

    def hide(self):
        cam = self.selected()
        if cam:
            cam['rtsp_hidden'] = True
            self.slot = self.focus = 0
            self.persist()

    def restore(self):
        hidden = [c for c in self.cams if c.get('rtsp_hidden') or not c.get('ativa', True)]
        if not hidden:
            self.message('Não há câmeras ocultas.')
            return
        choice = xbmcgui.Dialog().select('Mostrar câmera', [c['nome'] for c in hidden])
        if choice >= 0:
            hidden[choice].update(rtsp_hidden=False, ativa=True)
            self.persist()

    def delete_camera(self):
        cam = self.selected()
        if cam and xbmcgui.Dialog().yesno('Excluir câmera',
                             'Remover '+cam['nome']+' do cadastro local?'):
            self.cams.remove(cam)
            self.slot = self.focus = 0
            self.persist()

    def menu(self):
        items = ('Adicionar câmera', 'Editar selecionada', 'Ocultar selecionada',
                 'Reexibir câmera oculta', 'Excluir selecionada',
                 'Zoom digital +', 'Zoom digital -',
                 'Zoom óptico ONVIF +', 'Zoom óptico ONVIF -')
        index = xbmcgui.Dialog().select('Menu de câmeras', list(items))
        if index == 0: self.add_camera()
        elif index == 1: self.edit_camera()
        elif index == 2: self.hide()
        elif index == 3: self.restore()
        elif index == 4: self.delete_camera()
        elif index == 5: self.zoom(.25)
        elif index == 6: self.zoom(-.25)
        elif index == 7: self.move(zoom=.5)
        elif index == 8: self.move(zoom=-.5)

    def activate(self, index):
        if index < 4:
            self.set_focus(index)
            if self.selected():
                self.ptz_mode = not self.ptz_mode
                self.render()
            return
        command = index-4
        if command == 0: self.add_camera()
        elif command == 1: self.edit_camera()
        elif command == 2: self.hide()
        elif command == 3: self.delete_camera()
        elif command == 4: self.change_page(-1)
        elif command == 5: self.change_page(1)
        elif command == 6: self.zoom(-.25)
        elif command == 7: self.zoom(.25)

    def onClick(self, controlId):
        for index, item in enumerate(self.buttons):
            if item.getId() != controlId: continue
            now = time.monotonic()
            if self.last_click[0] != controlId or now-self.last_click[1] > .35:
                self.last_click = (controlId, now)
                self.activate(index)
            return

    def onAction(self, action):
        code = action.getId()
        if code in BACK:
            if self.ptz_mode:
                self.ptz_mode = False
                self.render()
            else:
                self.closed = True
            return
        if code == 117:
            self.menu()
            return
        if code in (5, 6):
            self.change_page(-1 if code == 5 else 1)
            return
        if code in (59, 61):
            self.zoom(-.25 if code == 59 else .25)
            return
        if code in (1, 2, 3, 4):
            dx, dy = {1:(-1,0), 2:(1,0), 3:(0,-1), 4:(0,1)}[code]
            if self.ptz_mode:
                self.move(pan=dx*.45, tilt=-dy*.45)
                return
            if self.focus >= 4:
                if dy: self.set_focus(self.slot)
                else: self.set_focus(4+(self.focus-4+dx) % len(TOOLBAR))
            else:
                row, col = divmod(self.focus, 2)
                if dy < 0 and row == 0 or dy > 0 and row == 1:
                    self.set_focus(4)
                elif dy:
                    self.set_focus((row+dy)*2+col)
                else:
                    self.set_focus(row*2+(col+dx)%2)
            self.render()
            return
        if code == 7:
            control_id = self.buttons[self.focus].getId()
            self.last_click = (control_id, time.monotonic())
            self.activate(self.focus)

    def finish(self):
        self.closed = True
        self.stream_generation += 1
        # Só parar vídeo se for o stream local iniciado pelo complemento.
        self.stop_own_playback()
        self.live.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
