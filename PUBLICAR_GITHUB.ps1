# Publishes this source package into a new public GitHub repository.
# Requires Git and GitHub CLI (gh) installed on Windows.
# Does not request or store access tokens. Uses 'gh auth login'.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repository = 'douglassnake/douglassnake-gravador-tela-windows'
$RepositoryUrl = "https://github.com/$Repository"
$Source = $PSScriptRoot
$Destination = Join-Path $env:LOCALAPPDATA 'GravadorTelaWin\FonteGithub'
$Files = @(
    '.gitattributes', '.gitignore', 'LICENSE', 'README.md', 'CHANGELOG.md',
    'DIVULGACAO_X.md', 'requirements.txt', 'gravador_tela.py',
    'preparar_ambiente.py', 'verificar_python.py', 'INSTALAR.ps1',
    'INICIAR.bat', 'DIAGNOSTICO.bat', 'GERAR_EXE.bat',
    'ABRIR_PASTA_LOCAL.bat', 'PUBLICAR_GITHUB.ps1',
    'PUBLICAR_GITHUB.bat', 'ABRIR_PUBLICACAO_X.ps1',
    'ABRIR_PUBLICACAO_X.bat', '.github/workflows/build-windows.yml'
)

function Assert-Code([string]$Label) {
    if ($LASTEXITCODE -ne 0) { throw "$Label falhou (codigo $LASTEXITCODE)." }
}

try {
    Write-Host '=== GravadorTelaWin 1.3 - Publicar no GitHub ===' -ForegroundColor Cyan
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA nao encontrado.' }
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        throw "Git nao instalado. Instale em https://git-scm.com/downloads/win ou execute: winget install --id Git.Git -e"
    }
    if (-not (Get-Command gh.exe -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI nao instalado. Instale em https://cli.github.com/ ou execute: winget install --id GitHub.cli -e"
    }

    & gh auth status
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Conecte sua conta GitHub na janela do navegador.' -ForegroundColor Yellow
        & gh auth login --hostname github.com --web --git-protocol https
        Assert-Code 'Autenticacao GitHub'
    }
    $Login = (& gh api user --jq '.login' | Out-String).Trim()
    Assert-Code 'Consulta do usuario GitHub'
    if ($Login -ne 'douglassnake') {
        throw "Conta GitHub conectada: $Login. Esta publicacao exige a conta douglassnake. Execute 'gh auth switch'."
    }
    $Id = (& gh api user --jq '.id' | Out-String).Trim()
    Assert-Code 'Consulta do ID GitHub'

    # Always create the Git repository from a controlled allowlist on the local disk.
    # Never add recordings, logs, venvs, or arbitrary files from a network share.
    foreach ($file in $Files) {
        $sourceFile = Join-Path $Source $file
        if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
            throw "Arquivo necessario ausente: $file"
        }
        $destinationFile = Join-Path $Destination $file
        $destinationDir = Split-Path -Parent $destinationFile
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
        Copy-Item -LiteralPath $sourceFile -Destination $destinationFile -Force
    }
    Push-Location $Destination
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $Destination '.git'))) {
            & git init -b main
            Assert-Code 'Inicializacao Git'
        }
        & git config user.name $Login
        Assert-Code 'Configuracao do autor'
        & git config user.email "$Id+$Login@users.noreply.github.com"
        Assert-Code 'Configuracao do email privado'
        & git add -- $Files
        Assert-Code 'Selecao dos arquivos'
        & git diff --cached --quiet
        if ($LASTEXITCODE -ne 0) {
            & git commit -m 'Publicar GravadorTelaWin v1.3'
            Assert-Code 'Commit Git'
        }

        # A pre-existing repository is only accepted if it has no commits or if
        # this local folder already has the correct matching origin.
        $remoteNames = @(& git remote)
        Assert-Code 'Verificacao de remotes Git'
        $remotePresent = ($remoteNames -contains 'origin')
        $remoteUrl = ''
        if ($remotePresent) {
            $remoteUrl = (& git remote get-url origin | Out-String).Trim()
            Assert-Code 'Consulta do remote Git'
        }
        if ($remotePresent -and ($remoteUrl -notmatch '(^|[/:])douglassnake/douglassnake-gravador-tela-windows(\.git)?$')) {
            throw "Remote 'origin' aponta para outro projeto: $remoteUrl"
        }

        $repositoryFound = $false
        try {
            $view = (& gh repo view $Repository --json name --jq '.name' 2>$null | Out-String).Trim()
            $repositoryFound = ($LASTEXITCODE -eq 0 -and $view -eq 'gravador-tela-windows')
        } catch { $repositoryFound = $false }
        if (-not $repositoryFound) {
            Write-Host "Criando repositorio PUBLICO: $Repository" -ForegroundColor Yellow
            & gh repo create $Repository --public --description 'Gravador de tela para Windows: MP4, audio, multiplos monitores e pausa' --source $Destination --remote origin --push
            Assert-Code 'Criacao e envio ao GitHub'
        } else {
            if (-not $remotePresent) {
                $refs = (& git ls-remote --heads "https://github.com/$Repository.git" | Out-String).Trim()
                Assert-Code 'Verificacao do historico remoto'
                if ($refs) {
                    throw "O repositorio $Repository ja existe com commits. Para proteger arquivos existentes, nao houve envio automatico."
                }
                & git remote add origin "https://github.com/$Repository.git"
                Assert-Code 'Configuracao do remote'
            }
            & git push -u origin main
            Assert-Code 'Envio ao GitHub'
        }
    }
    finally { Pop-Location }

    Write-Host ''
    Write-Host 'PUBLICACAO NO GITHUB CONCLUIDA:' -ForegroundColor Green
    Write-Host $RepositoryUrl
    Write-Host 'Confira a aba Actions para baixar o executavel apos a compilacao.'
    Start-Process $RepositoryUrl
}
catch {
    Write-Host ''
    Write-Host ('FALHA: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Nenhum historico remoto foi forçado ou apagado.'
    exit 1
}
