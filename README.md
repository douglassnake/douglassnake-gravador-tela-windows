# Aplicativos Windows — GravadorTelaWin e Janela no Topo

Este repositório reúne ferramentas de uso local para Windows 10 e 11.

## GravadorTelaWin 2.1.1 — correção da janela Chrome

A captura por janela foi ajustada para reutilizar a captura de **área visível**, em vez de `gdigrab(hwnd=...)`. Para vídeo do Chrome, mantenha a janela aberta e na mesma posição, sem cobri-la. O gravador minimiza automaticamente ao iniciar. [Detalhes e teste](README_V21.md).

Prévia em `fix/captura-janela-chrome`, sem substituir `main`.

## GravadorTelaWin 2.1 — prévia RC1 (desempenho)

[**Novidades da v2.1**](README_V21.md): aceleração H.264 por GPU com autoteste e fallback de CPU, perfis de gravação, FPS real, velocidade do encoder, espaço livre e encerramento preventivo.

O código continua em **branch separada** para preservar a versão estável da `main`. Esta é uma versão de teste, e o uso de GPU depende de driver e suporte do FFmpeg no PC. Aceleração de GPU não garante FPS maior em todos os casos.

**Download:** [Actions](../../actions), rotina **Testar e compilar GravadorTelaWin 2.1**, artefato `GravadorTelaWin-v2.1-PREVIA-Windows-x64` após a compilação bem-sucedida.

## GravadorTelaWin 2.0 — prévia RC1

A [documentação da versão 2.0](README_V2.md) apresenta as mudanças mais recentes: pré-visualização, gravação de janela individual, níveis de áudio, proteção e recuperação de gravações interrompidas e finalização atômica em MP4.

> **Esta versão é de validação.** A v1.3 permanece a referência que já funcionou no Windows. O teste automático de compilação não garante que captura, áudio e seleção de janelas funcionem em todos os computadores.

**Download do executável de prévia:** abra [GitHub Actions](../../actions), selecione **Testar e compilar GravadorTelaWin 2.0** e baixe o artefato `GravadorTelaWin-v2-PREVIA-Windows-x64` após uma execução concluída.

**Instalação alternativa:** baixe os arquivos desta branch, extraia e execute `INICIAR.bat`. Será preparado um ambiente Python local, caso necessário.

## Janela no Topo v1.0

O [Janela no Topo](janela-no-topo/README.md) permite selecionar e fixar uma janela acima das demais. É independente do gravador; funciona com PowerShell e não requer Python.

## GravadorTelaWin — recursos compartilhados

- Tela inteira, monitor ou área personalizada; MP4/H.264.
- Microfone e áudio do computador, com pausa e retomada.
- 15, 24, 30 e 60 FPS, perfis de qualidade, pasta de saída.
- Atalhos globais: **Ctrl + Shift + R** (iniciar/encerrar), **Ctrl + Shift + P** (pausar/retomar).
- Captura local: o aplicativo não envia vídeos à nuvem.

## Requisitos, suporte e transparência

O desenvolvimento usa Python, Tkinter, FFmpeg (distribuído via `imageio-ffmpeg`), MSS, Pillow, SoundCard/WASAPI e PyInstaller. O build automatizado gera um executável Windows sem instalar Python no computador de destino; o código pode ser iniciado com `INICIAR.bat` e instalação de dependências.

Diagnósticos e arquivos temporários podem conter dados do computador: **revise antes de compartilhá-los**. Não envie seus vídeos ou logs para um repositório público.

Licença do projeto: [MIT](LICENSE); dependências possuem termos próprios.
