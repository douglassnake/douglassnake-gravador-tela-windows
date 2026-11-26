# GravadorTelaWin 1.3 - bootstrap local robusto (Windows PowerShell 5.1+)
# Evita executar fontes em UNC, identifica Python 3.11-3.13 instalado e recupera .venv.
[CmdletBinding()]
param(
    [ValidateSet('Iniciar','Diagnostico','GerarEXE')]
    [string]$Acao = 'Iniciar'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Versao = '2.7.0-rc1'
$PastaOrigem = $PSScriptRoot
$PastaLocal = Join-Path $env:LOCALAPPDATA 'GravadorTelaWin'
$PastaPython = Join-Path $PastaLocal 'Runtime\Python312'
$PythonPrivativo = Join-Path $PastaPython 'python.exe'
$Verificador = Join-Path $PastaLocal 'verificar_python.py'
$script:Python = ''
$PastaDownload = Join-Path $PastaLocal 'downloads'
$InstaladorPython = Join-Path $PastaDownload 'python-3.12.10-amd64.exe'
$LogBootstrap = Join-Path $PastaLocal 'instalacao_bootstrap.log'
$LogPython = Join-Path $PastaLocal 'diagnostico_instalacao.log'
$LogApp = Join-Path $PastaLocal 'gravador_erros.log'
$LogCompleto = Join-Path $PastaLocal 'diagnostico_completo.txt'
$LogInstalador = Join-Path $PastaLocal 'python_instalador.log'
$PythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'
$PythonMD5 = '5EDDB0B6F12C852725DE071AE681DDE4' # Validacao adicional: Authenticode PSF.

function Registrar([string]$Mensagem) {
    $linha = ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Mensagem)
    Write-Host $Mensagem
    Add-Content -LiteralPath $LogBootstrap -Value $linha -Encoding UTF8
}

function Copiar-Programa() {
    Registrar "Origem: $PastaOrigem"
    Registrar "Destino local: $PastaLocal"
    foreach ($nome in @('gravador_tela.py','gravador_v2_utils.py','gravador_v21_perf.py','gravador_v22_studio.py','gravador_v23_overlay.py','gravador_v24_history.py','gravador_v25_export.py','gravador_v26_project.py','gravador_v27_dual.py','gravador_v27_perf.py','preparar_ambiente.py','requirements.txt','verificar_python.py')) {
        $origem = Join-Path $PastaOrigem $nome
        $destino = Join-Path $PastaLocal $nome
        if (-not (Test-Path -LiteralPath $origem -PathType Leaf)) {
            throw "Arquivo necessario ausente na origem: $origem"
        }
        if (-not ([string]::Equals($origem, $destino, [StringComparison]::OrdinalIgnoreCase))) {
            Copy-Item -LiteralPath $origem -Destination $destino -Force
        }
    }
    Registrar 'Fontes preparados no disco local; o Python nao executara diretamente pela rede.'
}

function Adicionar-Candidato([System.Collections.Generic.List[string]]$Lista, [string]$Caminho) {
    if ([string]::IsNullOrWhiteSpace($Caminho)) { return }
    $Caminho = [Environment]::ExpandEnvironmentVariables($Caminho.Trim().Trim('"'))
    if (Test-Path -LiteralPath $Caminho -PathType Container) {
        $Caminho = Join-Path $Caminho 'python.exe'
    }
    if (-not $Caminho.EndsWith('.exe', [StringComparison]::OrdinalIgnoreCase)) {
        $Caminho = Join-Path $Caminho 'python.exe'
    }
    if ((Test-Path -LiteralPath $Caminho -PathType Leaf) -and (-not $Lista.Contains($Caminho))) {
        $Lista.Add($Caminho)
    }
}

function Obter-CandidatosPython() {
    $lista = New-Object 'System.Collections.Generic.List[string]'
    # 1. Local do aplicativo e destino padrao do instalador oficial por usuario.
    Adicionar-Candidato $lista $PythonPrivativo
    foreach ($versaoLocal in @('Python312','Python311','Python313')) {
        Adicionar-Candidato $lista (Join-Path $env:LOCALAPPDATA "Programs\Python\$versaoLocal\python.exe")
    }
    # 2. Registry (PEP 514): importante quando um Python existente ignora TargetDir.
    foreach ($raiz in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        foreach ($versao in @('3.12','3.11','3.13')) {
            $chave = "$raiz\$versao\InstallPath"
            try {
                if (Test-Path -LiteralPath $chave) {
                    $registro = Get-Item -LiteralPath $chave -ErrorAction Stop
                    Adicionar-Candidato $lista ([string]$registro.GetValue('ExecutablePath'))
                    Adicionar-Candidato $lista ([string]$registro.GetValue(''))
                }
            } catch { }
        }
    }
    # 3. Instalacoes classicas para todos os usuarios.
    foreach ($base in @($env:ProgramFiles, $env:ProgramW6432)) {
        if (-not [string]::IsNullOrWhiteSpace($base)) {
            foreach ($versaoLocal in @('Python312','Python311','Python313')) {
                Adicionar-Candidato $lista (Join-Path $base "$versaoLocal\python.exe")
            }
        }
    }
    # 4. Launcher "py" - descobre a instalacao verdadeira mesmo sem PATH.
    try {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($null -ne $launcher) {
            foreach ($versao in @('3.12','3.11','3.13')) {
                $result = & $launcher.Source "-$versao" $Verificador 2>$null
                if ($LASTEXITCODE -eq 0) {
                    foreach ($linha in @($result)) {
                        if ([string]$linha -match '^CAMINHO=(.+)$') {
                            Adicionar-Candidato $lista ([string]$Matches[1])
                        }
                    }
                }
            }
        }
    } catch { }
    # 5. Outros "python.exe" reais; nunca executar o alias da Microsoft Store.
    try {
        $comandos = @(Get-Command python.exe -All -ErrorAction SilentlyContinue)
        foreach ($comando in $comandos) {
            $caminho = [string]$comando.Source
            if ($caminho -and $caminho -notmatch '\\Microsoft\\WindowsApps\\') {
                Adicionar-Candidato $lista $caminho
            }
        }
    } catch { }
    return $lista.ToArray()
}

function Testar-CandidatoPython([string]$Caminho, [bool]$Detalhes = $false) {
    if (-not (Test-Path -LiteralPath $Caminho -PathType Leaf)) { return $false }
    try {
        # Executa arquivo .py separado: evita corrupcao de aspas no -c no Windows PowerShell 5.1.
        $saida = (& $Caminho $Verificador 2>&1 | Out-String)
        $saidaCodigo = $LASTEXITCODE
        $valido = ($saidaCodigo -eq 0) -and ($saida -match 'GRAVADOR_OK')
        if ($Detalhes) {
            Registrar ("Teste Python: {0} | valido={1} | saida={2}" -f $Caminho, $valido, ($saida.Trim() -replace '[\r\n]+',' '))
        }
        return $valido
    }
    catch {
        if ($Detalhes) { Registrar ("Falha no teste de Python {0}: {1}" -f $Caminho, $_.Exception.Message) }
        return $false
    }
}

function Localizar-Python([bool]$Detalhes = $false) {
    foreach ($candidato in @(Obter-CandidatosPython)) {
        if (Testar-CandidatoPython $candidato $Detalhes) {
            $script:Python = $candidato
            return $true
        }
    }
    return $false
}

function Verificar-Instalador([string]$Caminho) {
    if (-not (Test-Path -LiteralPath $Caminho -PathType Leaf)) { return $false }
    $hash = (Get-FileHash -LiteralPath $Caminho -Algorithm MD5).Hash.ToUpperInvariant()
    if ($hash -ne $PythonMD5) {
        Registrar "Hash inesperado do instalador baixado: $hash"
        return $false
    }
    $assinatura = Get-AuthenticodeSignature -LiteralPath $Caminho
    if ($assinatura.Status -ne 'Valid' -or $null -eq $assinatura.SignerCertificate) {
        Registrar "Assinatura Authenticode nao valida: $($assinatura.Status)"
        return $false
    }
    $emissor = [string]$assinatura.SignerCertificate.Subject
    if ($emissor -notlike '*Python Software Foundation*') {
        Registrar "Publicador inesperado: $emissor"
        return $false
    }
    Registrar 'Instalador oficial verificado por hash e assinatura digital.'
    return $true
}

function Preparar-Python() {
    if (Localizar-Python) {
        Registrar "Python compativel detectado: $script:Python"
        return
    }
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'E necessario Windows 10/11 de 64 bits.'
    }
    New-Item -ItemType Directory -Path $PastaDownload -Force | Out-Null
    Registrar 'Nenhum Python compativel encontrado. Preparando Python 3.12.10 somente para este usuario.'
    if (-not (Verificar-Instalador $InstaladorPython)) {
        if (Test-Path -LiteralPath $InstaladorPython) {
            Remove-Item -LiteralPath $InstaladorPython -Force
        }
        Registrar "Baixando instalador oficial: $PythonUrl"
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $PythonUrl -OutFile $InstaladorPython -UseBasicParsing -TimeoutSec 240
        if (-not (Verificar-Instalador $InstaladorPython)) {
            Remove-Item -LiteralPath $InstaladorPython -Force -ErrorAction SilentlyContinue
            throw 'Verificacao da assinatura do instalador falhou.'
        }
    }
    Registrar 'Executando instalador oficial do Python...'
    $argumentos = @(
        '/quiet',
        'InstallAllUsers=0',
        ('TargetDir="{0}"' -f $PastaPython),
        'Include_pip=1', 'Include_tcltk=1', 'Include_exe=1', 'Include_lib=1',
        'Include_dev=1', 'Include_launcher=0', 'InstallLauncherAllUsers=0',
        'AssociateFiles=0', 'Include_test=0', 'Include_doc=0',
        'PrependPath=0', 'Shortcuts=0'
    )
    $processo = Start-Process -FilePath $InstaladorPython -ArgumentList $argumentos -Wait -PassThru
    Registrar "Instalador oficial terminou com codigo $($processo.ExitCode)"
    # Instalacoes existentes podem ignorar TargetDir e permanecer no local original.
    # Por isso, redescobrir Python via registry, launcher e pasta padrao apos instalar.
    if (-not (Localizar-Python -Detalhes $true)) {
        Registrar 'Nenhum Python compativel foi encontrado mesmo apos a instalacao.'
        throw ('O instalador terminou com codigo {0}, mas nao foi localizado Python utilizavel. Execute DIAGNOSTICO.bat para detalhar as instalacoes detectadas.' -f $processo.ExitCode)
    }
    Registrar "Python localizado e validado apos instalacao: $script:Python"
}

function Registrar-Diagnostico() {
    Registrar ('Windows 64-bit: ' + [Environment]::Is64BitOperatingSystem)
    Registrar ('PowerShell: ' + $PSVersionTable.PSVersion.ToString())
    Registrar ('Origem UNC: ' + $PastaOrigem.StartsWith('\\'))
    $candidatos = @(Obter-CandidatosPython)
    Registrar ('Candidatos Python detectados: ' + $candidatos.Count)
    foreach ($candidato in $candidatos) {
        [void](Testar-CandidatoPython $candidato $true)
    }
    Registrar ('Python compativel: ' + (Localizar-Python))
    if ($script:Python) { Registrar ('Executavel Python selecionado: ' + $script:Python) }
    Registrar ('Ambiente .venv existe: ' + (Test-Path -LiteralPath (Join-Path $PastaLocal '.venv\Scripts\python.exe')))
    Registrar ('Disco local: ' + $PastaLocal)
    $diag = New-Object System.Collections.Generic.List[string]
    $diag.Add('GRAVADOR DE TELA WINDOWS - DIAGNOSTICO V1.3')
    $diag.Add(('Data: ' + (Get-Date -Format 's')))
    $diag.Add(('Origem: ' + $PastaOrigem))
    $diag.Add(('Local: ' + $PastaLocal))
    foreach ($arquivo in @($LogBootstrap,$LogPython,$LogApp,$LogInstalador)) {
        $diag.Add('')
        $diag.Add(('========== ' + [IO.Path]::GetFileName($arquivo) + ' =========='))
        if (Test-Path -LiteralPath $arquivo) {
            # Proteger tamanho do diagnostico; preservar eventos mais recentes.
            $linhas = @(Get-Content -LiteralPath $arquivo -Tail 400 -ErrorAction SilentlyContinue)
            $diag.Add([string]::Join([Environment]::NewLine, $linhas))
        }
        else { $diag.Add('(nao existe)') }
    }
    [IO.File]::WriteAllLines($LogCompleto, $diag.ToArray(), [System.Text.Encoding]::UTF8)
    Registrar "Diagnostico completo salvo em: $LogCompleto"
}

try {
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA nao esta definido no Windows.' }
    New-Item -ItemType Directory -Path $PastaLocal -Force | Out-Null
    Registrar ('====== GravadorTelaWin ' + $Versao + ' | ' + $Acao + ' ======')
    Copiar-Programa
    if ($Acao -eq 'Diagnostico') {
        Registrar-Diagnostico
        exit 0
    }
    Preparar-Python
    $env:GRAVADOR_PYTHON_EXE = $script:Python
    $comando = if ($Acao -eq 'GerarEXE') { 'build' } else { 'install' }
    Registrar "Preparando bibliotecas e iniciando: $comando"
    & $script:Python (Join-Path $PastaLocal 'preparar_ambiente.py') $comando
    $retorno = $LASTEXITCODE
    if ($retorno -ne 0) {
        throw "Preparacao falhou com codigo $retorno. Consulte o diagnostico."
    }
    if ($Acao -eq 'GerarEXE') {
        Registrar "Executavel criado em: $(Join-Path $PastaLocal 'dist\GravadorTelaWin_v2_5_ESTUDIO_RC2.exe')"
    }
    else { Registrar 'Aplicativo iniciado a partir do disco local.' }
    Registrar 'RESULTADO: OK'
    exit 0
}
catch {
    try {
        Registrar ('ERRO: ' + $_.Exception.Message)
        Registrar ('RESULTADO: FALHA; execute DIAGNOSTICO.bat e envie diagnostico_completo.txt')
    }
    catch { Write-Host ('ERRO: ' + $_.Exception.Message) }
    exit 1
}
