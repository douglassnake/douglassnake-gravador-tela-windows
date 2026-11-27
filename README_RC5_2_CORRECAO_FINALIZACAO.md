# GravadorTelaWin 2.7 RC5.2 — finalização/recuperação da câmera Android

**Situação:** prévia para homologação, sem merge na `main` (v2.6).

## Falha observada
No Windows, ao encerrar a sessão com Galaxy A12 via scrcpy USB, a RC5.1 exibiu
`Câmera B não foi finalizada corretamente; os arquivos temporários foram preservados`.
Isso ocorre quando não é confirmado o fechamento limpo do processo scrcpy ou não há MKV
acima do mínimo de tamanho. O log real ainda não foi recebido, portanto não é possível
afirmar se a causa foi uma janela inacessível, um encerramento prematuro ou erro do gravador.

## Correções defensivas
- Na finalização, enumerar também janelas ocultas/minimizadas pertencentes **ao PID
  do processo scrcpy iniciado pelo GravadorTelaWin**, priorizando a janela pelo título
  `GravadorTelaWin - Camera Android B`; não enviar WM_CLOSE a outros processos.
- Permitir uma pequena espera por saída natural quando não houver janela.
- Após uma falha de fechamento, verificar a legibilidade do MKV através de FFmpeg com
  `-c:v copy -f null -`, sem alterar o original. Se legível, prosseguir com a
  exportação normal, registrando alerta de possível perda dos quadros finais.
- Quando não recuperável, incluir no erro código de saída, tamanho do MKV, trecho do log
  scrcpy e pasta onde os originais foram preservados. Sem exclusão dos dados.
- Incluir `RECUPERAR_GRAVACAO_ANDROID.ps1`: mostra logs localmente e permite remux
  para novos MP4 de todo `android_camera_*.mkv` e `video_*.mkv` encontrado.
  Não modifica, sobrescreve ou apaga MKV, WAV ou logs originais.
- Versão RC5.2 nos scripts/artefato Windows; correção anterior do instalador mantida.

## Recuperar o vídeo da falha anterior
Feche o GravadorTelaWin e qualquer scrcpy ainda gravando. Execute:
```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\RECUPERAR_GRAVACAO_ANDROID.ps1" -Pasta "C:\Users\Guarda-Mor\Videos\GravadorTela\gravador_tela_XXXX"
```
Substitua a pasta pelo caminho exibido no erro. Sem `-Pasta`, o script escolhe
a pasta temporária mais recente em `Vídeos\GravadorTela`.

Arquivos de saída: `RECUPERADOS_gravador_tela_*/..._RECUPERADO.mp4`.
O vídeo `video_*.mkv` da Área A é recuperado **sem áudio** por esse utilitário;
os WAV originais permanecem guardados para uma recuperação de áudio posterior.

Se o FFmpeg não conseguir abrir os dados, nenhum arquivo original é alterado.
Conferir as últimas linhas de `scrcpy_001.log`; o log pode conter identificadores
do celular e não deve ser compartilhado publicamente sem revisão.

## Homologação
1. Iniciar Área A e Android USB na Área B.
2. Gravar 30 s, pausar, retomar, gravar mais 10 s e encerrar.
3. Conferir dois MP4 completos, sem travamentos ou quadros finais perdidos.
4. Se não funcionar, enviar o log `scrcpy_001.log` com identificadores ocultados
   e a nova mensagem detalhada.

## Segurança
Não instalar drivers, não alterar ADB/Android, não enviar vídeos pela rede,
não mudar módulos de processamento de vídeo ou áudio. A v2.6 permanece na `main`.
O sistema preserva temporários em qualquer falha de exportação.
