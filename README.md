# Câmeras em Mosaico para Kodi

Complemento Python para Kodi 21+, em português brasileiro, com mosaico RTSP, PTZ ONVIF e zoom digital pelo controle remoto.

## Funções

- Mosaico de até quatro câmeras por página, com prévias JPEG RTSP atualizadas aproximadamente uma vez por segundo.
- Seleção por setas e OK; setas movem a câmera quando o modo PTZ está ativo.
- Botão **+ Adicionar câmera** para IP/host, nome, usuário, senha, portas e caminho RTSP.
- Editar, ocultar, restaurar, excluir câmeras e trocar de página.
- Zoom digital de 1x a 4x; tentativa de zoom óptico por ONVIF.
- Importação inicial do cadastro local Yoosee, quando existente.
- O complemento não usa comandos para parar, pausar ou reiniciar a reprodução do Kodi.

## Instalação

Requer Kodi com Python 3 e FFmpeg no sistema.

```sh
sudo apt install ffmpeg
git clone https://github.com/pedropmoraesf/Kodi-Cameras-Mosaico.git ~/.kodi/addons/script.cameras.mosaico
```

Abra em **Complementos → Programas → Câmeras em Mosaico**. Dependendo da instalação, pode ser necessário atualizar o catálogo local ou iniciar o Kodi novamente em momento oportuno.

## Controle remoto

- **Setas** no mosaico: seleção de câmeras e navegação pela barra de botões.
- **OK** na câmera: ativa/desativa o modo PTZ; setas movimentam a câmera em passos curtos.
- **Voltar**: sai do modo PTZ ou fecha o complemento.
- **1 e 3**: diminuir/aumentar zoom digital, também disponível na barra de botões.
- **Menu contextual**: inclui reexibir câmera oculta e testar zoom óptico.
- **Página anterior/próxima**: barra de botões ou teclas PageUp/PageDown.

## Conexões

O padrão é RTSP na porta 554 e caminho `/onvif2`, com ONVIF na porta 5000. Para outros modelos, configure as portas e o caminho corretos. O zoom óptico e o PTZ dependem do suporte real da câmera e de um perfil ONVIF válido.

O mosaico **não é vídeo fluido de 25/30 FPS**: são prévias de baixa taxa de quadros para limitar o consumo de CPU no Raspberry Pi 4. Câmeras sem RTSP ou com autenticação inválida podem permanecer sem imagem.

## Privacidade e segurança

- O arquivo `cameras.json` é gravado no perfil privado do Kodi com permissão 0600 no Linux; a configuração antiga, quando existente, só é lida localmente.
- **Nenhuma senha, endereço particular ou imagem de câmera faz parte deste repositório.**
- O FFmpeg recebe URLs RTSP autenticadas na linha de comando enquanto o painel está aberto. Não dê acesso shell a pessoas não confiáveis.
- Não exponha serviços RTSP/ONVIF à Internet; prefira rede privada/VPN.
- Ao fechar, o complemento encerra somente os processos FFmpeg que iniciou.

## Verificação

```sh
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
```

Licença: MIT.
