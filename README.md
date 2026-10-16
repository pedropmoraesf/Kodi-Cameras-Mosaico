# Câmeras em Mosaico para Kodi

Complemento para **Kodi 21+**: até 16 câmeras IP RTSP simultâneas por página, mosaico de **vídeo contínuo** e PTZ/zoom pelo controle remoto da TV ou Kore.

## Vídeo contínuo — versão 0.2.0 beta

O mosaico **não usa mais imagens JPEG a 1 FPS**. Para contornar a limitação de uma superfície de vídeo por player Kodi, um FFmpeg local lê até 16 fluxos RTSP e os compõe em **um único H.264/MPEG-TS**, entregue ao reprodutor do próprio Kodi por HTTP **somente em 127.0.0.1**. A interface apresenta o mosaico no controle `xbmcgui.ControlVideoWindow`, com botões sobre cada câmera. A taxa-alvo adapta-se à quantidade: **20 FPS para até 4 câmeras, 15 FPS para 5 a 9 e 12 FPS para 10 a 16**, com resolução máxima de aproximadamente **960×540** (células redimensionadas automaticamente); a taxa efetiva depende da CPU, da rede e das câmeras. Não é equivalente à decodificação independente por hardware do VLC, e o desempenho real no Pi 4 ainda requer validação visual.

- Até **16 câmeras por página**, simultaneamente. Câmeras além da 16ª aparecem em outras páginas, sem limite fixo para o cadastro.
- Uma câmera que não responde ao exame RTSP inicial é substituída por quadro preto, sem bloquear as outras.
- RTSP UDP/TCP é examinado por câmera; para Yoosee `/onvif1` e `/onvif2`, UDP tem prioridade.
- PTZ ONVIF por setas, zoom digital de 1× a 4×, tentativa de zoom óptico ONVIF; o suporte PTZ precisa ser validado nas câmeras.
- Botão **+ Adicionar câmera**, edição, exclusão, ocultação, restauração e paginação.
- O cadastro é salvo apenas no perfil local do usuário.

## Proteção de vídeo em reprodução

Se **outro vídeo já estiver em reprodução no Kodi**, o complemento **não inicia o mosaico nem para o vídeo**: exibe um aviso. Nenhuma ação ocorre automaticamente durante a reprodução. Ao abrir o mosaico quando não há vídeo em reprodução, o complemento utiliza o player Kodi para seu próprio vídeo. Ao fechar, interrompe apenas o fluxo criado pelo complemento.

O mosaico é atualizado na **próxima abertura do complemento**. Não é necessário reiniciar o Kodi, mas abrir o complemento durante uma sessão de vídeo não é recomendado.

## Instalação

Requer Kodi 21+, Python 3 e FFmpeg/FFprobe instalados:

```sh
sudo apt install ffmpeg
git clone https://github.com/pedropmoraesf/Kodi-Cameras-Mosaico.git ~/.kodi/addons/script.cameras.mosaico
```

Abra por **Complementos → Programas → Câmeras em Mosaico**. No Raspberry Pi da instalação original, foi adicionado um atalho **Câmeras** diretamente ao menu inicial da skin Arctic: Zephyr – Reloaded; esse atalho depende da skin local e não acompanha o ZIP.

## Controles

- Setas: seleção da câmera e navegação pelos botões.
- OK sobre uma câmera: ativa/desativa o modo PTZ; no modo PTZ, as setas movimentam a câmera.
- Voltar: sai do modo PTZ ou fecha o complemento.
- Teclas 1/3 ou botões Zoom -/+: alteram zoom digital da câmera, recriando o vídeo composto.
- Menu contextual: reexibir câmera oculta, testar zoom óptico, adicionar e editar.
- Página anterior/próxima: botões de navegação ou teclas PageUp/PageDown.

## Segurança

O arquivo `cameras.json` é privado (0600 no Linux), não é enviado ao GitHub e pode ser importado da configuração local Yoosee. O servidor de vídeo é vinculado à interface de loopback (127.0.0.1), com URL contendo token de sessão. Credenciais RTSP são passadas ao FFmpeg na linha de comando do próprio Raspberry Pi; usuários com acesso de processos podem vê-las. Nunca exponha RTSP/ONVIF diretamente na Internet.

## Testes e limites

```sh
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
```

Os testes automatizados são executados **sem abrir o Kodi** e sem interromper vídeos. A saída H.264 composta, o foco no controle, a latência e o PTZ precisam de um teste integrado em momento em que não esteja assistindo a outro conteúdo. A antiga implementação de prévias JPEG permanece apenas como código legado não utilizado.

Licença: MIT.

## Grade dinâmica (0.2.1)

Ao adicionar, ocultar, reexibir ou excluir câmeras, a quantidade e o tamanho
dos quadrinhos são recalculados automaticamente para preencher a área do
vídeo. Exemplos: uma câmera = 1×1, duas = 2×1, três ou quatro = 2×2,
cinco ou seis = 3×2, sete a nove = 3×3, dez a doze = 4×3 e treze a
dezesseis = 4×4. O botão e os movimentos de seleção do controle remoto
acompanham as novas posições. A partir da 17ª câmera, é criada uma nova
página, acessível na barra de navegação. O cadastro permite novas páginas
sem limite fixo de câmeras.

O Raspberry Pi 4 pode não sustentar 16 streams simultâneos com boa fluidez;
a taxa-alvo é reduzida para 15 ou 12 FPS quando necessário. O uso real
com várias câmeras ainda exige validação visual e testes de desempenho.
