> **Versão estável: GravadorTelaWin 2.3 RC2.** Desenho validado no Windows, incluindo correção da camada que recebe cliques. Integrado na branch `main`.
> **Próxima prévia: GravadorTelaWin 2.4 RC1.** Barra flutuante com cores, espessuras e histórico desfazer/refazer. Consulte [README_V24.md](README_V24.md). Os recursos novos aguardam homologação real.

# Aplicativos Windows — GravadorTelaWin e Janela no Topo

Este repositório reúne ferramentas de uso local para Windows 10 e 11.

## Histórico: GravadorTelaWin 2.1.1 — correção para Chrome

Selecionar uma janela do Chrome podia produzir vídeo vazio/preto porque o capturador GDI por `HWND` não é confiável para aplicações aceleradas. A correção utiliza a área visível correspondente à janela, com captura do desktop. O aplicativo se minimiza ao iniciar e retomar. **Mantenha a janela visível e na mesma posição durante a gravação.** [Detalhes e testes](README_V21.md).

Este ajuste foi integrado à versão estável durante a evolução do projeto.

## GravadorTelaWin 2.1 — prévia RC1 (desempenho)

[**Novidades da v2.1**](README_V21.md): aceleração H.264 por GPU com autoteste e fallback de CPU, perfis de gravação, FPS real, velocidade do encoder, espaço livre e encerramento preventivo.

Esta seção descreve o ciclo de testes da v2.1. Esta é uma versão de teste, e o uso de GPU depende de driver e suporte do FFmpeg no PC. Aceleração de GPU não garante FPS maior em todos os casos.

**Download:** [Actions](../../actions), rotina **Testar e compilar GravadorTelaWin 2.1**, artefato `GravadorTelaWin-v2.1-PREVIA-Windows-x64` após a compilação bem-sucedida.

## GravadorTelaWin 2.0 — prévia RC1

A [documentação da versão 2.0](README_V2.md) apresenta as mudanças mais recentes: pré-visualização, gravação de janela individual, níveis de áudio, proteção e recuperação de gravações interrompidas e finalização atômica em MP4.

> **Registro histórico da prévia 2.0.** A versão atual está descrita no início deste README. O teste automático de compilação não garante que captura, áudio e seleção de janelas funcionem em todos os computadores.

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
