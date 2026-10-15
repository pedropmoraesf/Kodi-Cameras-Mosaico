"""Interface de mosaico navegável pelo controle remoto Kodi."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
import xbmcgui
from . import cameras, onvif
from .preview import Preview

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
        self.preview = Preview(os.path.join(profile, 'previews'))
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.last_frames = {}
        self.last_click = (None, 0.)
        self.addControl(xbmcgui.ControlImage(0, 0, 1280, 720,
                         os.path.join(os.path.dirname(os.path.dirname(__file__)), 'media', 'background.png')))
        self.title = xbmcgui.ControlLabel(25, 17, 1180, 42, '',
                       font='font30', textColor='0xFFFFFFFF')
        self.addControl(self.title)
        self.hint = xbmcgui.ControlLabel(25, 657, 1230, 26, '',
                      font='font13', textColor='0xFFE7EACB')
        self.note_label = xbmcgui.ControlLabel(25, 687, 1230, 26, '',
                      font='font13', textColor='0xFFABDDFD')
        self.addControl(self.hint)
        self.addControl(self.note_label)
        self.images, self.tiles = [], []
        for pos in range(4):
            x, y = 25 + 625 * (pos % 2), 69 + 287 * (pos // 2)
            image = xbmcgui.ControlImage(x, y, 605, 238, '', aspectRatio=2)
            button = xbmcgui.ControlButton(x, y + 239, 605, 38, 'Sem câmera')
            self.addControl(image)
            self.addControl(button)
            self.images.append(image)
            self.tiles.append(button)
        self.toolbar = []
        for i, label in enumerate(TOOLBAR):
            button = xbmcgui.ControlButton(25 + i * 154, 620, 150, 35, label)
            self.addControl(button)
            self.toolbar.append(button)
        self.buttons = self.tiles + self.toolbar
        self.render()

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
        self.preview.sync([(c['ip'], c) for c in page])
        for i in range(4):
            if i < len(page):
                prefix = 'PTZ ▶ ' if self.ptz_mode and i == self.slot else ('► ' if self.slot == i else '')
                self.tiles[i].setLabel(prefix + page[i]['nome'])
            else:
                self.tiles[i].setLabel('— Sem câmera —')
                self.images[i].setImage('', False)
        self.title.setLabel('CÂMERAS | MOSAICO    Página %d/%d' % (self.page+1, pages))
        self.hint.setLabel('PTZ: setas movimentam; OK/Voltar retorna à seleção' if self.ptz_mode
             else 'Setas: navegação | OK: PTZ | 1/3: zoom | Menu: outras opções')
        self.set_focus(self.focus)

    def refresh(self):
        for i, cam in enumerate(self.page_cams()):
            p = self.preview.image_path(cam['ip'])
            try: stamp = p.stat().st_mtime_ns
            except OSError: continue
            if self.last_frames.get(i) != (str(p), stamp):
                self.images[i].setImage(str(p), False)
                self.last_frames[i] = (str(p), stamp)
        if self.pending and self.pending.done():
            try:
                self.pending.result()
                self.message('Comando PTZ executado.')
            except Exception:
                self.message('PTZ não confirmado; confira suporte, porta e perfil ONVIF.')
            self.pending = None
        self.preview.sync([(c['ip'], c) for c in self.page_cams()])

    def persist(self):
        cameras.save(self.profile, self.cams)
        self.ptz_mode = False
        self.last_frames.clear()
        self.render()

    def change_page(self, amount):
        maxpage = max(0, (len(self.visible())-1)//4)
        nextpage = max(0, min(maxpage, self.page+amount))
        if nextpage != self.page:
            self.page, self.slot, self.focus = nextpage, 0, 0
            self.ptz_mode = False
            self.last_frames.clear()
            self.render()

    def zoom(self, delta):
        cam = self.selected()
        if cam:
            factor = self.preview.set_digital_zoom(cam['ip'], cam, delta)
            self.message('Zoom digital da câmera: %.2fx' % factor)

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
        self.preview.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
