# GravadorTelaWin 2.7 RC5.1 — correção da inicialização da câmera B (scrcpy)

**Escopo:** alteração defensiva do monitor de inicialização do scrcpy. Não altera o codec, o comando de gravação da câmera, as gravações já feitas nem o modo simples da v2.6.

## Problema identificado na RC5
O código aguardava até 10 segundos e considerava falha se `android_camera_001.mkv` não passasse de 1000 bytes. Um arquivo ainda bufferizado podia causar falha falsa. Além disso, a janela era minimizada repetidamente durante a inicialização. Quando o scrcpy saía cedo, a mensagem ignorava o código de saída e o erro registrado no log.

## Correção
- Aguardar até 25 segundos; aceitar também a confirmação explícita `Recording started to ...` do log, sem depender de um limiar arbitrário de bytes.
- Só minimizar a janela scrcpy **depois** de confirmada a inicialização.
- Se o processo sair ou expirar, mostrar o código de saída e um trecho curto do log, e preservar `scrcpy_001.log` na pasta temporária (o log pode conter identificadores do celular).
- Corrigir o rótulo: autorização ADB não significa câmera já testada.
- O instalador RC5 inclui `gravador_v27_ui.py`; esta versão mantém a correção.

## Diagnóstico do teste anterior

No PowerShell do Windows, consulte o arquivo de log da pasta de temporários mostrada no erro:

```powershell
Get-ChildItem "$env:USERPROFILE\Videos\GravadorTela" -Directory -Filter "gravador_tela_*" |
  Sort-Object LastWriteTime -Descending | Select-Object -First 3 |
  ForEach-Object { Get-ChildItem $_.FullName -Filter "scrcpy_*.log" |
    ForEach-Object { Get-Content $_.FullName -Tail 60 } }
```

Se aparecer `Camera ... failed`, `encoder` ou `adb` nos logs, use as mensagens específicas antes de concluir que o problema é apenas o limite de tempo. Não reinstale drivers nem desative a segurança do Windows sem verificar primeiro.

## Homologação
- Conectar Galaxy A12 via USB, fechar instâncias manuais do scrcpy e selecionar o executável testado.
- Iniciar por 30 segundos, pausar, retomar e encerrar.
- Confirmar dois MP4 válidos e fluidez. Se falhar, enviar as últimas linhas do `scrcpy_001.log` revisadas para retirar serial/identificadores.
- O executável Windows é gerado por GitHub Actions; testes unitários não substituem o ensaio físico.

**Branch RC5.1:** `fix/v27-rc5-scrcpy-startup`; **base:** `fix/v27-rc5-installer-ui`; `main` (v2.6) preservada.
