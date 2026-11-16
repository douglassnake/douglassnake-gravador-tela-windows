# Janela no Topo v1.0

Ferramenta para **Windows 10 e Windows 11** que mantém uma janela escolhida sempre por cima das demais.

## Funcionalidades

- Selecionar uma janela pela lista de aplicativos abertos.
- Buscar pela janela ou nome do processo.
- Fixar e desafixar uma janela sem alterar seu tamanho ou posição.
- Fixar diversas janelas e desfazer todas as alterações desta sessão.
- Selecionar a janela clicando nela durante uma contagem de 5 segundos.
- Criar um atalho na Área de Trabalho.

## Como usar

1. Baixe o código deste diretório ou o artefato **JanelaNoTopo-Windows** da rotina de empacotamento em [Actions](../../actions).
2. Extraia todos os arquivos para a mesma pasta.
3. Clique duas vezes em **`INICIAR.bat`**.
4. Escolha uma janela na lista e clique em **FIXAR ACIMA**. Clique em **DESAFIXAR JANELA** para desfazer.

Para criar um atalho, execute `CRIAR_ATALHO.bat`.

**Requisitos:** Windows PowerShell 5.1 e .NET Framework (já disponíveis normalmente no Windows 10/11). Não precisa de Python, pip ou conexão com a internet.

## Como funciona

O script `JanelaNoTopo.ps1` usa Windows Forms e funções nativas do Windows (`EnumWindows`, `GetForegroundWindow` e `SetWindowPos`), sem módulos externos.

Os arquivos são copiados para `%LOCALAPPDATA%\JanelaNoTopo` durante a inicialização. Uma janela pode permanecer fixada após o fechamento do aplicativo; para reverter, abra novamente e use **DESAFIXAR JANELA**.

## Limitações

- Fixa a **janela inteira**, não apenas um recorte de tela.
- Aplicativos executados com permissões elevadas podem exigir iniciar este app como administrador.
- Tela cheia exclusiva, janelas protegidas e alertas do Windows podem sobrepor a janela fixada.
- O artefato do GitHub Actions é um **ZIP portátil**, não um instalador `.exe` assinado.
- Ainda é necessário validar a execução da versão publicada em um Windows real.

## Privacidade

O app funciona localmente, não envia dados à internet e não grava áudio ou vídeo. Em caso de falha, pode criar um log local em `%LOCALAPPDATA%\JanelaNoTopo\erro.log`.

## Licença

MIT, conforme a [licença do repositório](../LICENSE).
