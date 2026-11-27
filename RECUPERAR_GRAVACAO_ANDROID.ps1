param(
    [string]$Pasta = ''
)
$ErrorActionPreference = 'Stop'
Write-Host '===== GRAVADORTELAWIN - RECUPERACAO SEGURA RC5.2 ====='
$base = Join-Path $env:USERPROFILE 'Videos\GravadorTela'
if ([string]::IsNullOrWhiteSpace($Pasta)) {
    $recent = Get-ChildItem -LiteralPath $base -Directory -Filter 'gravador_tela_*' -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $recent) {
        throw "Nenhuma pasta gravador_tela_* encontrada em $base"
    }
    $Pasta = $recent.FullName
}
if (!(Test-Path -LiteralPath $Pasta -PathType Container)) {
    throw "Pasta de trabalho inexistente: $Pasta"
}
$work = (Resolve-Path -LiteralPath $Pasta).Path
Write-Host "Pasta de originais (sera preservada): $work"
Get-ChildItem -LiteralPath $work -File |
  Where-Object { $_.Extension -in @('.mkv','.wav','.log','.progress') } |
  Select-Object Name,Length,LastWriteTime | Format-Table -AutoSize
Get-ChildItem -LiteralPath $work -File -Filter 'scrcpy_*.log' |
  ForEach-Object {
      Write-Host "`n==== LOG $($_.Name) (ultimas 25 linhas) ===="
      Get-Content -LiteralPath $_.FullName -Tail 25
  }
$python = Join-Path $env:LOCALAPPDATA 'GravadorTelaWin\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) {
    Write-Host 'Nao foi encontrado o Python do ambiente de captura. Videos originais intactos.'
    exit 2
}
$ffmpeg = & $python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ffmpeg)) {
    Write-Host 'FFmpeg nao identificado. Videos originais intactos.'
    exit 3
}
$dest = Join-Path (Split-Path -Parent $work) ('RECUPERADOS_' + (Split-Path -Leaf $work))
New-Item -ItemType Directory -Path $dest -Force | Out-Null
$files = @(Get-ChildItem -LiteralPath $work -File -Filter 'android_camera_*.mkv') +
         @(Get-ChildItem -LiteralPath $work -File -Filter 'video_*.mkv')
if ($files.Count -eq 0) {
    Write-Host 'Nenhum MKV encontrado. Originais preservados.'
    exit 4
}
foreach ($source in $files) {
    $out = Join-Path $dest ($source.BaseName + '_RECUPERADO.mp4')
    Write-Host "`nVerificando/recuperando: $($source.Name)"
    & $ffmpeg -hide_banner -loglevel error -nostdin -n `
      -i $source.FullName -map '0:v:0' -an -c:v copy -movflags +faststart $out
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $out)) {
        Write-Host "VIDEO OK (sem recodificacao): $out"
    } else {
        Write-Host "Nao foi possivel recuperar $($source.Name). MKV original intacto."
    }
}
Write-Host "`nFIM. Os arquivos MKV, WAV e logs originais nao foram alterados."
