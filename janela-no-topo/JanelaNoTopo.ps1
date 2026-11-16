# Janela no Topo - Windows 10/11
# Aplicativo independente de Python e de modulos de terceiros.
# Executar com: powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File JanelaNoTopo.ps1

$ErrorActionPreference = 'Stop'

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()

    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class JNTNative {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", EntryPoint = "GetWindowLongW", SetLastError = true)]
    public static extern int GetWindowLong(IntPtr hWnd, int index);
}
'@ -ErrorAction Stop

    $script:SelfPid = [System.Diagnostics.Process]::GetCurrentProcess().Id
    $script:Pinned = @{}   # handles fixados nesta execucao
    $script:Countdown = 0
    $script:Capturing = $false
    $script:AllWindows = @()

    $script:Bg = [System.Drawing.Color]::FromArgb(17, 24, 39)
    $script:PanelBg = [System.Drawing.Color]::FromArgb(31, 41, 55)
    $script:FieldBg = [System.Drawing.Color]::FromArgb(24, 33, 47)
    $script:White = [System.Drawing.Color]::FromArgb(239, 244, 250)
    $script:Muted = [System.Drawing.Color]::FromArgb(169, 184, 202)
    $script:Blue = [System.Drawing.Color]::FromArgb(52, 124, 235)
    $script:Green = [System.Drawing.Color]::FromArgb(29, 163, 112)
    $script:Red = [System.Drawing.Color]::FromArgb(181, 74, 74)

    function New-JNTButton {
        param([string] $Text, [int] $X, [int] $Y, [int] $Width, [int] $Height, [System.Drawing.Color] $Color)
        $button = New-Object System.Windows.Forms.Button
        $button.Text = $Text
        $button.Location = New-Object System.Drawing.Point($X, $Y)
        $button.Size = New-Object System.Drawing.Size($Width, $Height)
        $button.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
        $button.FlatAppearance.BorderSize = 0
        $button.BackColor = $Color
        $button.ForeColor = $script:White
        $button.Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
        $button.Cursor = [System.Windows.Forms.Cursors]::Hand
        $button.UseVisualStyleBackColor = $false
        return $button
    }

    function Get-JNTWindows {
        $script:Enumerated = New-Object System.Collections.ArrayList
        $callback = [JNTNative+EnumWindowsProc] {
            param([IntPtr] $handle, [IntPtr] $param)
            try {
                if (-not [JNTNative]::IsWindowVisible($handle)) { return $true }
                $length = [JNTNative]::GetWindowTextLength($handle)
                if ($length -lt 1) { return $true }
                $text = New-Object System.Text.StringBuilder ($length + 1)
                [void] [JNTNative]::GetWindowText($handle, $text, $text.Capacity)
                $title = $text.ToString().Trim()
                if ([string]::IsNullOrWhiteSpace($title)) { return $true }

                [uint32] $procId = 0
                [void] [JNTNative]::GetWindowThreadProcessId($handle, [ref] $procId)
                if ($procId -eq 0 -or $procId -eq $script:SelfPid) { return $true }

                $processName = 'Desconhecido'
                try {
                    $processName = [System.Diagnostics.Process]::GetProcessById([int] $procId).ProcessName
                } catch { }

                [void] $script:Enumerated.Add([pscustomobject]@{
                    Handle = $handle.ToInt64()
                    Title = $title
                    Process = $processName
                    Pid = $procId
                })
            } catch { }
            return $true
        }
        [void] [JNTNative]::EnumWindows($callback, [IntPtr]::Zero)
        return @($script:Enumerated.ToArray() | Sort-Object Title)
    }

    function Test-JNTTopmost {
        param([long] $Handle)
        if (-not [JNTNative]::IsWindow([IntPtr] $Handle)) { return $false }
        $exStyle = [JNTNative]::GetWindowLong([IntPtr] $Handle, -20)
        return (($exStyle -band 0x00000008) -ne 0)
    }

    function Set-JNTStatus {
        param([string] $Text, [bool] $IsError = $false)
        $script:StatusLabel.Text = $Text
        $script:StatusLabel.ForeColor = if ($IsError) { [System.Drawing.Color]::FromArgb(251, 144, 144) } else { $script:Muted }
    }

    function Get-JNTSelectedHandle {
        if ($script:WindowList.SelectedItems.Count -eq 0) { return [long] 0 }
        return [long] $script:WindowList.SelectedItems[0].Tag
    }

    function Update-JNTCount {
        $dead = @()
        foreach ($key in @($script:Pinned.Keys)) {
            if (-not [JNTNative]::IsWindow([IntPtr] ([long]$key))) { $dead += $key }
        }
        foreach ($key in $dead) { $script:Pinned.Remove($key) }
        $script:CountLabel.Text = ('Janelas fixadas nesta sessao: {0}' -f $script:Pinned.Count)
    }

    function Update-JNTList {
        $selected = Get-JNTSelectedHandle
        $needle = $script:SearchBox.Text.Trim()
        $script:WindowList.BeginUpdate()
        try {
            $script:WindowList.Items.Clear()
            $script:AllWindows = @(Get-JNTWindows)
            foreach ($win in $script:AllWindows) {
                if ($needle.Length -gt 0 -and
                    $win.Title.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -lt 0 -and
                    $win.Process.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
                    continue
                }
                $item = New-Object System.Windows.Forms.ListViewItem($win.Title)
                [void] $item.SubItems.Add($win.Process)
                [void] $item.SubItems.Add(([string] $win.Pid))
                [void] $item.SubItems.Add($(if (Test-JNTTopmost -Handle $win.Handle) { 'SIM' } else { 'Nao' }))
                $item.Tag = [long] $win.Handle
                if (Test-JNTTopmost -Handle $win.Handle) { $item.ForeColor = [System.Drawing.Color]::FromArgb(106, 221, 178) }
                [void] $script:WindowList.Items.Add($item)
                if ([long] $win.Handle -eq $selected) { $item.Selected = $true }
            }
        } finally {
            $script:WindowList.EndUpdate()
        }
        Update-JNTCount
    }

    function Set-JNTWindow {
        param([long] $Handle, [bool] $On)
        if ($Handle -eq 0) {
            Set-JNTStatus -Text 'Selecione uma janela na lista primeiro.' -IsError $true
            return $false
        }
        $hwnd = [IntPtr] $Handle
        if (-not [JNTNative]::IsWindow($hwnd)) {
            Set-JNTStatus -Text 'A janela foi fechada. Clique em Atualizar.' -IsError $true
            return $false
        }
        [uint32] $flags = 0x0001 -bor 0x0002 -bor 0x0010 # NOMOVE, NOSIZE, NOACTIVATE
        $zOrder = if ($On) { [IntPtr] (-1) } else { [IntPtr] (-2) } # TOPMOST e NOTOPMOST
        $ok = [JNTNative]::SetWindowPos($hwnd, $zOrder, 0, 0, 0, 0, $flags)
        if (-not $ok) {
            $winError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            Set-JNTStatus -Text ("O Windows bloqueou a alteracao (erro {0}). Tente executar como administrador se a janela for elevada." -f $winError) -IsError $true
            return $false
        }
        if ($On) {
            $script:Pinned[$Handle] = $true
            Set-JNTStatus -Text 'Janela fixada. Clique em outros programas para testar.'
        } else {
            if ($script:Pinned.ContainsKey($Handle)) { $script:Pinned.Remove($Handle) }
            Set-JNTStatus -Text 'Janela desafixada. Ela voltou ao comportamento normal.'
        }
        Update-JNTCount
        return $true
    }

    $script:Form = New-Object System.Windows.Forms.Form
    $script:Form.Text = 'Janela no Topo - Windows'
    $script:Form.ClientSize = New-Object System.Drawing.Size(932, 598)
    $script:Form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $script:Form.BackColor = $script:Bg
    $script:Form.ForeColor = $script:White
    $script:Form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $script:Form.MinimumSize = New-Object System.Drawing.Size(948, 637)
    $script:Form.MaximizeBox = $false
    $script:Form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedSingle

    $header = New-Object System.Windows.Forms.Panel
    $header.BackColor = $script:PanelBg
    $header.Location = New-Object System.Drawing.Point(0,0)
    $header.Size = New-Object System.Drawing.Size(932,88)
    $script:Form.Controls.Add($header)

    $titleLabel = New-Object System.Windows.Forms.Label
    $titleLabel.Text = 'JANELA NO TOPO'
    $titleLabel.Font = New-Object System.Drawing.Font('Segoe UI', 18, [System.Drawing.FontStyle]::Bold)
    $titleLabel.ForeColor = $script:White
    $titleLabel.Location = New-Object System.Drawing.Point(22,13)
    $titleLabel.Size = New-Object System.Drawing.Size(500,35)
    $header.Controls.Add($titleLabel)

    $subtitle = New-Object System.Windows.Forms.Label
    $subtitle.Text = 'Escolha uma janela para mantê-la visível acima das demais.'
    $subtitle.ForeColor = $script:Muted
    $subtitle.Location = New-Object System.Drawing.Point(24,54)
    $subtitle.Size = New-Object System.Drawing.Size(700,24)
    $header.Controls.Add($subtitle)

    $version = New-Object System.Windows.Forms.Label
    $version.Text = 'v1.0  |  Sem instalacao'
    $version.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
    $version.ForeColor = $script:Muted
    $version.Location = New-Object System.Drawing.Point(726,27)
    $version.Size = New-Object System.Drawing.Size(175,25)
    $header.Controls.Add($version)

    $searchLabel = New-Object System.Windows.Forms.Label
    $searchLabel.Text = 'BUSCAR JANELA'
    $searchLabel.ForeColor = $script:Muted
    $searchLabel.Location = New-Object System.Drawing.Point(24,104)
    $searchLabel.Size = New-Object System.Drawing.Size(180,22)
    $script:Form.Controls.Add($searchLabel)

    $script:SearchBox = New-Object System.Windows.Forms.TextBox
    $script:SearchBox.Location = New-Object System.Drawing.Point(24,128)
    $script:SearchBox.Size = New-Object System.Drawing.Size(882,30)
    $script:SearchBox.BackColor = $script:FieldBg
    $script:SearchBox.ForeColor = $script:White
    $script:SearchBox.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    $script:Form.Controls.Add($script:SearchBox)

    $script:WindowList = New-Object System.Windows.Forms.ListView
    $script:WindowList.Location = New-Object System.Drawing.Point(24,172)
    $script:WindowList.Size = New-Object System.Drawing.Size(882,257)
    $script:WindowList.BackColor = $script:FieldBg
    $script:WindowList.ForeColor = $script:White
    $script:WindowList.View = [System.Windows.Forms.View]::Details
    $script:WindowList.FullRowSelect = $true
    $script:WindowList.MultiSelect = $false
    $script:WindowList.GridLines = $false
    $script:WindowList.HideSelection = $false
    [void] $script:WindowList.Columns.Add('Janela / titulo', 504)
    [void] $script:WindowList.Columns.Add('Programa', 196)
    [void] $script:WindowList.Columns.Add('PID', 79)
    [void] $script:WindowList.Columns.Add('No topo?', 87)
    $script:Form.Controls.Add($script:WindowList)

    $btnFix = New-JNTButton -Text 'FIXAR ACIMA' -X 24 -Y 446 -Width 280 -Height 42 -Color $script:Green
    $btnUnfix = New-JNTButton -Text 'DESAFIXAR JANELA' -X 316 -Y 446 -Width 280 -Height 42 -Color $script:Red
    $btnRefresh = New-JNTButton -Text 'ATUALIZAR LISTA' -X 608 -Y 446 -Width 298 -Height 42 -Color $script:PanelBg
    $script:Form.Controls.AddRange([System.Windows.Forms.Control[]] @($btnFix,$btnUnfix,$btnRefresh))

    $btnCapture = New-JNTButton -Text 'ESCOLHER CLICANDO NA JANELA (5 s)' -X 24 -Y 500 -Width 582 -Height 43 -Color $script:Blue
    $btnUnfixAll = New-JNTButton -Text 'DESAFIXAR TODAS' -X 618 -Y 500 -Width 288 -Height 43 -Color $script:PanelBg
    $script:Form.Controls.AddRange([System.Windows.Forms.Control[]] @($btnCapture,$btnUnfixAll))

    $script:StatusLabel = New-Object System.Windows.Forms.Label
    $script:StatusLabel.ForeColor = $script:Muted
    $script:StatusLabel.Location = New-Object System.Drawing.Point(24,556)
    $script:StatusLabel.Size = New-Object System.Drawing.Size(660,27)
    $script:StatusLabel.Text = 'Selecione uma janela na lista ou use o botao azul.'
    $script:Form.Controls.Add($script:StatusLabel)

    $script:CountLabel = New-Object System.Windows.Forms.Label
    $script:CountLabel.ForeColor = $script:Muted
    $script:CountLabel.Location = New-Object System.Drawing.Point(688,556)
    $script:CountLabel.Size = New-Object System.Drawing.Size(218,27)
    $script:CountLabel.TextAlign = [System.Drawing.ContentAlignment]::TopRight
    $script:Form.Controls.Add($script:CountLabel)

    $btnRefresh.Add_Click({ Update-JNTList; Set-JNTStatus -Text 'Lista de janelas atualizada.' })
    $script:SearchBox.Add_TextChanged({ Update-JNTList })
    $btnFix.Add_Click({
        $handle = Get-JNTSelectedHandle
        if (Set-JNTWindow -Handle $handle -On $true) { Update-JNTList }
    })
    $btnUnfix.Add_Click({
        $handle = Get-JNTSelectedHandle
        if (Set-JNTWindow -Handle $handle -On $false) { Update-JNTList }
    })
    $script:WindowList.Add_DoubleClick({
        $handle = Get-JNTSelectedHandle
        if (Set-JNTWindow -Handle $handle -On $true) { Update-JNTList }
    })
    $btnUnfixAll.Add_Click({
        $handles = @($script:Pinned.Keys)
        if ($handles.Count -eq 0) {
            Set-JNTStatus -Text 'Nao ha janelas fixadas por esta sessao.'
            return
        }
        $failed = 0
        foreach ($handle in $handles) {
            if ([JNTNative]::IsWindow([IntPtr] ([long]$handle))) {
                [uint32]$flags = 0x0001 -bor 0x0002 -bor 0x0010
                if (-not [JNTNative]::SetWindowPos([IntPtr] ([long]$handle), [IntPtr] (-2), 0, 0, 0, 0, $flags)) { $failed++ }
            }
            if ($script:Pinned.ContainsKey($handle)) { $script:Pinned.Remove($handle) }
        }
        Update-JNTList
        if ($failed -gt 0) { Set-JNTStatus -Text ("Nao foi possivel desafixar {0} janela(s)." -f $failed) -IsError $true }
        else { Set-JNTStatus -Text 'Todas as janelas fixadas nesta sessao foram liberadas.' }
    })

    $script:CaptureTimer = New-Object System.Windows.Forms.Timer
    $script:CaptureTimer.Interval = 1000
    $script:CaptureTimer.Add_Tick({
        if (-not $script:Capturing) { return }
        $script:Countdown--
        if ($script:Countdown -gt 0) {
            $btnCapture.Text = ("CLIQUE NA JANELA DESEJADA ({0} s)" -f $script:Countdown)
            Set-JNTStatus -Text ("Clique na janela que deseja fixar. Captura em {0} segundo(s)." -f $script:Countdown)
            return
        }
        $script:CaptureTimer.Stop()
        $script:Capturing = $false
        $btnCapture.Enabled = $true
        $btnCapture.Text = 'ESCOLHER CLICANDO NA JANELA (5 s)'
        $front = [JNTNative]::GetForegroundWindow()
        if ($front -eq [IntPtr]::Zero -or $front -eq $script:Form.Handle) {
            Set-JNTStatus -Text 'Nenhuma janela externa detectada. Tente novamente e clique no programa desejado.' -IsError $true
            return
        }
        [uint32]$frontProcId = 0
        [void][JNTNative]::GetWindowThreadProcessId($front, [ref]$frontProcId)
        if ($frontProcId -eq $script:SelfPid) {
            Set-JNTStatus -Text 'O aplicativo de selecao estava em primeiro plano. Clique na janela-alvo apos iniciar a contagem.' -IsError $true
            return
        }
        if (Set-JNTWindow -Handle $front.ToInt64() -On $true) { Update-JNTList }
    })

    $btnCapture.Add_Click({
        if ($script:Capturing) { return }
        $script:Countdown = 5
        $script:Capturing = $true
        $btnCapture.Enabled = $false
        $btnCapture.Text = 'CLIQUE NA JANELA DESEJADA (5 s)'
        Set-JNTStatus -Text 'Agora clique na janela que deseja deixar sempre por cima.'
        $script:CaptureTimer.Start()
    })

    $script:Form.Add_FormClosed({
        $script:CaptureTimer.Stop()
        $script:CaptureTimer.Dispose()
        # Nao retirar TOPMOST ao fechar: a janela fixada continua no topo.
    })

    Update-JNTList
    [void] $script:Form.ShowDialog()
} catch {
    $detail = $_ | Out-String
    try {
        $dir = Join-Path $env:LOCALAPPDATA 'JanelaNoTopo'
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Add-Content -Path (Join-Path $dir 'erro.log') -Value ("[{0}] {1}" -f (Get-Date -Format s), $detail)
    } catch { }
    try {
        [System.Windows.Forms.MessageBox]::Show(
            "Nao foi possivel iniciar Janela no Topo.`n`n$detail`n`nDetalhes: %LOCALAPPDATA%\JanelaNoTopo\erro.log",
            'Janela no Topo - Erro',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    } catch {
        Write-Host $detail
    }
    exit 1
}
