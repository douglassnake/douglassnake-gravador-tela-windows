# GravadorTelaWin v2.7 RC5 — Interface compacta com rolagem

**Prévia para Windows 10/11 x64.** Exclusivamente uma mudança de interface sobre a v2.7 RC4 (Android scrcpy USB). O motor de gravação não foi alterado. A versão estável v2.6 permanece intocada na branch `main`.

## Problema corrigido

Na RC4 a janela inicial tinha dimensão fixa de 1040×1110, frequentemente ultrapassando a altura da tela; opções e botões ficavam fora do campo de visão. O título interno ainda mencionava RC1.

## Interface RC5

- Altura inicial limitada à resolução disponível (até 780 px), tamanho mínimo de 900×560 px e redimensionamento livre.
- Painel central rolável com **barra vertical permanente**, roda do mouse e touchpad (eventos normais do Tk), inclusive quando a fonte Android está selecionada.
- Botões **Iniciar, Pausar/Retomar, Recuperar Vídeo e Desenhar** ancorados em rodapé fixo. O tempo, o status e o desempenho permanecem visíveis mesmo após rolar o formulário.
- Cabeçalho compacto com título correto RC5, estado `PRONTO`, `GRAVANDO`, `PAUSADO` ou `PROCESSANDO` e paleta azul-escura com cartões e bordas.
- Campos de caminho e câmera Android organizados para ocupar menos espaço; mensagem ADB em linha inteira para não estourar a largura em janelas menores.
- A roda do mouse não captura eventos de menus de seleção (`Combobox`), listas ou outros aplicativos. O formulário é independente da camada de desenho.
- Funcionalidades e comandos da RC4 preservados, inclusive captura única, captura dupla por regiões, câmera UVC e câmera Android scrcpy via USB.

## Instalação e teste

1. Faça backup do executável da RC4 e use uma pasta nova para a RC5.
2. Baixe o executável gerado pelo workflow `build-v27-ui.yml`, ou extraia este pacote e execute `INICIAR.bat`.
3. Reduza a altura da janela e use roda do mouse ou a barra de rolagem para alcançar `03 CONFIGURAÇÕES` e `04 DESTINO DOS ARQUIVOS`.
4. Confirme que os quatro botões permanecem na parte inferior após rolar.
5. Conecte o Galaxy A12 com ADB autorizado, selecione a fonte B `Câmera Android via scrcpy (USB)`, indique seu `scrcpy.exe` e repita uma gravação de 30 segundos com pausa/retomada.
6. Confira `AreaA.mp4`, `AreaB.mp4` e o diagnóstico existente da RC4.

**Nota:** a janela de saída de scrcpy e seu encerramento seguro continuam sujeitos à homologação física. A RC5 não resolve problemas de FPS da captura dupla por GDI nem acrescenta sincronização exata dos vídeos.

## Validação automatizada

```bash
python -m unittest discover -s tests -p 'test_v27*.py' -v
xvfb-run -a env PYTHONPATH=. python tests/smoke_v27_rc5_layout.py
xvfb-run -a env PYTHONPATH=. python tests/smoke_v27_scrcpy_gui.py
xvfb-run -a env PYTHONPATH=. python tests/smoke_v27_usb_gui.py
```

A compilação Windows ocorre via GitHub Actions. O teste de interface em Linux/Xvfb verifica a rolagem, o rodapé fixo e a integração do seletor scrcpy; o teste real no Windows continua obrigatório.

## Reversão

Se a RC5 apresentar qualquer comportamento inesperado, retorne à RC4 homologada para o teste Android ou à v2.6 estável (`main`). A branch RC5 e o PR ficam separados e em draft até a aprovação.
