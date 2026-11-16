# GravadorTelaWin — gravador de tela para Windows

Aplicativo de gravação de tela para **Windows 10 e 11 (64 bits)**, com interface gráfica em português. Grava vídeos em **MP4 (H.264)** e permite capturar áudio do microfone e/ou do computador.

> **Versão estável de referência: 1.3.** A inicialização da versão 1.3 foi confirmada em teste de usuário no Windows. O executável produzido por compilação automática deve ser validado em um computador Windows antes de ser distribuído amplamente.

## Recursos

- Captura da tela inteira, de um monitor específico ou de uma região selecionada.
- Gravação local em MP4/H.264.
- Áudio do microfone, áudio do computador (quando disponível) e combinação dos dois.
- Pausa, retomada e finalização da gravação.
- Opções de 15, 24, 30 e 60 FPS e ajuste de qualidade.
- Atalhos de teclado: **Ctrl + Shift + R** para iniciar/parar; **Ctrl + Shift + P** para pausar/retomar.
- Escolha da pasta de saída (padrão: `Vídeos\GravadorTela`).

## Instalação no Windows (modo automático)

1. Baixe os arquivos deste repositório: **Code → Download ZIP**.
2. Extraia o ZIP para uma pasta. Pode estar em unidade de rede, mas o aplicativo copiará os arquivos necessários para o disco local.
3. Clique duas vezes em **`INICIAR.bat`**.
4. A versão 1.3 procura Python 3.11–3.13 x64 e, se necessário, instala Python 3.12.10 para o usuário atual a partir de `python.org`, verifica o instalador e prepara um ambiente virtual local.
5. Na interface, escolha o monitor/área e clique para começar a gravar.

A primeira instalação requer internet para baixar Python e as bibliotecas do PyPI. O aplicativo **não envia os vídeos gravados para servidores**; são salvos localmente na pasta selecionada.

> **Avisos de segurança:** o arquivo `.exe` gerado localmente não é assinado digitalmente. O Windows pode exibir alerta do SmartScreen. Analise o código e confirme a procedência antes de executar. Grave conteúdo de terceiros somente com as autorizações aplicáveis.

## Executável `.exe` independente

No Windows, depois de configurar o aplicativo, execute **`GERAR_EXE.bat`**. O arquivo resultante estará em:

```text
%LOCALAPPDATA%\GravadorTelaWin\dist\GravadorTelaWin.exe
```

Também existe uma rotina em **GitHub Actions**: na aba **Actions**, execute `Build Windows EXE`, ou aguarde a compilação após uma atualização na branch `main`. O `.exe` aparece como *artefato* para baixar na execução da rotina. Esse artefato não é uma versão de lançamento (Release) assinada.

## Publicação do projeto no GitHub e divulgação no X

O projeto inclui dois assistentes para Windows:

1. **`PUBLICAR_GITHUB.bat`**: prepara uma cópia local somente com arquivos aprovados, usa o GitHub CLI (`gh`) e publica o projeto no repositório **público** `douglassnake/gravador-tela-windows`. Exige **Git**, **GitHub CLI** e autenticação na conta `douglassnake` pelo navegador. Se faltarem ferramentas, o script indica como instalá-las. Não salva tokens nem incorpora vídeos e logs ao repositório.
2. **`ABRIR_PUBLICACAO_X.bat`**: depois que o README estiver acessível no GitHub, abre a tela de publicação do X.com com um texto pronto. **O post não é enviado automaticamente**; revise e clique em Publicar no X.

Caso prefira o método manual, crie um repositório público e vazio em [GitHub / new](https://github.com/new) com o nome `gravador-tela-windows`, instale [GitHub CLI](https://cli.github.com/) e use o `PUBLICAR_GITHUB.bat` para enviar os arquivos. O script protege repositórios que já possuam um histórico diferente.

Não publique o link do GitHub nem divulgue um `.exe` antes de confirmar que o repositório e a compilação estão disponíveis. O **GitHub Actions** disponibiliza o executável como artefato; ele não é automaticamente um instalador assinado ou uma Release.

## Diagnóstico de problemas

Execute `DIAGNOSTICO.bat` e consulte:

```text
%LOCALAPPDATA%\GravadorTelaWin\diagnostico_completo.txt
```

**Não publique diagnósticos sem revisar:** eles podem conter nomes de usuário, caminhos de rede e outras informações sobre o computador.

## Estrutura

| Arquivo | Finalidade |
| --- | --- |
| `gravador_tela.py` | Interface e mecanismo de captura de vídeo/áudio. |
| `INSTALAR.ps1` | Detecção e preparação do Python no Windows. |
| `preparar_ambiente.py` | Criação/recuperação do ambiente virtual e compilação. |
| `verificar_python.py` | Validação dos componentes de Python. |
| `INICIAR.bat` | Inicia a instalação ou abre o programa. |
| `GERAR_EXE.bat` | Compila o executável com PyInstaller. |
| `DIAGNOSTICO.bat` | Reúne informações de diagnóstico. |
| `PUBLICAR_GITHUB.bat` | Publica os arquivos aprovados em um repositório público. |
| `ABRIR_PUBLICACAO_X.bat` | Abre o rascunho da divulgação no X.com. |

## Tecnologias

Python, Tkinter, FFmpeg (via `imageio-ffmpeg`), MSS, SoundCard/WASAPI, NumPy, Pillow e PyInstaller (somente para compilação).

## Licença

Distribuído sob a licença [MIT](LICENSE). As dependências e o FFmpeg possuem licenças próprias; verifique seus termos antes de redistribuir builds binários.
