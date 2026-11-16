# Opens X.com's compose window with a prepared draft; does NOT send a post.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/douglassnake/douglassnake-gravador-tela-windows'
$RawReadme = 'https://raw.githubusercontent.com/douglassnake/douglassnake-gravador-tela-windows/main/README.md'
$Post = @'
GravadorTelaWin v1.3: aplicativo gratuito e de codigo aberto para gravar a tela do Windows em MP4. Escolha um monitor ou uma regiao, capture audio e pause/retome suas gravacoes. Confira o projeto:
https://github.com/douglassnake/douglassnake-gravador-tela-windows
'@
try {
    # Do not invite people to an uncreated repository.
    Invoke-WebRequest -Uri $RawReadme -Method Head -UseBasicParsing -TimeoutSec 20 | Out-Null
    $uri = 'https://x.com/intent/post?text=' + [Uri]::EscapeDataString($Post.Trim())
    Start-Process $uri
    Write-Host 'Rascunho aberto no X.com. Revise o conteudo e clique em Publicar.'
} catch {
    Write-Host 'O README publico ainda nao esta disponivel. Publique o repositorio no GitHub antes de divulgar.' -ForegroundColor Yellow
    Write-Host $RepoUrl
    exit 1
}
