# GravadorTelaWin v2.7 RC4 — câmera Android via scrcpy como Área B (USB)

**Prévia para homologação; não foi integrada à `main` (v2.6).** Derivada da v2.7 RC3 (DirectShow). A seleção de duas áreas Windows e de webcam UVC continua disponível, sem alterações no seu motor.

## Requisito confirmado pelo usuário

O Samsung Galaxy A12 (SM-A125M) já foi reconhecido por `scrcpy 5.0.1 --list-cameras` e realizou uma gravação da câmera com sucesso. Essa validação é externa ao GravadorTelaWin; o controle de dois processos ainda exige homologação no Windows.

## Arquitetura

- **Área A:** captura Windows por FFmpeg/gdigrab e áudio WASAPI, sem alteração do gravador de área simples.
- **Área B:** scrcpy recebe vídeo H.264 codificado no próprio Android por USB/ADB, e grava diretamente `android_camera_NNN.mkv`. **Não há uma segunda captura de janela GDI** nem recodificação de B no PC; na exportação a trilha B é remuxada com `-c copy` para MP4.
- O aplicativo exige exatamente um aparelho Android USB autorizado pelo ADB e executáveis `scrcpy.exe` e `adb.exe` da mesma pasta. Não instala drivers, aplicativos no celular nem altera ADB globalmente.
- `--video-source=camera --camera-facing=back|front --no-audio --video-codec=h264 --record=...` é executado apenas depois de pressionar Gravar. No perfil Fluidez, a fonte B pede no máximo 1280 pixels; a taxa de FPS do Android é **negociada pelo próprio aparelho**, não pela seleção de FPS da Área A.
- O scrcpy mantém uma janela de visualização minimizada. Ao pausar ou encerrar, o aplicativo envia `WM_CLOSE` apenas às janelas que pertencem ao processo scrcpy criado. É essencial permitir que ele finalize o MKV; se não conseguir, o arquivo temporário é preservado e a gravação **não** é marcada como homologada.
- Cada pausa/retomada reinicia os segmentos de A e B. A exportação gera dois MP4 e um JSON de diagnóstico, sem transmitir dados à internet.

## Limitações explícitas desta versão

1. O início de A e B **não é perfeitamente simultâneo**: scrcpy tem tempo de inicialização próprio. O relatório registra a diferença aproximada entre o início do FFmpeg e o início do processo scrcpy, **não** o horário exato do primeiro quadro.
2. **Áudio somente no MP4 da Área A.** Esta prévia não copia áudio para B, para evitar sincronização enganosa. Se desejado, uma etapa posterior poderá alinhar os áudios por timestamps confiáveis.
3. A câmera B é gerada na resolução/framerate fornecidos pelo Android, não nos 24 FPS solicitados ao FFmpeg da Área A.
4. Se o aparelho desconectar ou o scrcpy fechar, o sistema avisa e tenta salvar os arquivos íntegros. A gravação B só é publicada depois de validar cada segmento.
5. A opção precisa de **uma janela scrcpy normal**, minimizada automaticamente, para que o Windows possa solicitar encerramento limpo. Não utilize `--no-window` no GravadorTelaWin nesta versão.
6. Se o scrcpy não encerrar normalmente, há risco de arquivo MKV incompleto. O projeto preserva os arquivos temporários em vez de reportar um sucesso enganoso.

## Como testar

1. Deixe a pasta `scrcpy-win64-v5.0.1` onde ela está e mantenha a depuração USB autorizada no celular.
2. Abra o aplicativo v2.7 RC4; escolha a Área A do Windows.
3. Marque **Gravar duas áreas simultaneamente**, depois **Câmera Android via scrcpy (USB)**.
4. Clique **Selecionar scrcpy.exe** e escolha o executável já testado, por exemplo, na sua unidade `Y:`. A pasta deve conter `adb.exe`.
5. Clique **Verificar Android USB**. A mensagem precisa indicar autorização.
6. Selecione **Traseira**, perfil **Fluidez**, 24 FPS para a Área A e sem webcam sobreposta inicialmente.
7. Faça gravação de 20 a 30 segundos, pause, retome por 10 segundos e encerre.
8. Verifique `Gravacao_*_AreaA.mp4`, `Gravacao_*_AreaB.mp4` e `_android_diagnostico.json`. A Área B não contém áudio nesta versão.
9. Se der erro, preserve a pasta `gravador_tela_*` indicada na mensagem, inclusive `scrcpy_*.log`. Os logs podem conter número de série do celular; não os publique sem revisar.

## Segurança e rollback

O software não altera a v2.6, drivers, configuração do telefone ou demais versões. Volte à `main` ou execute o binário homologado da v2.6. Esta RC4 não deve ser mesclada antes da homologação de gravação/pausa/retomada/finalização no Windows.

## Testes

```powershell
python -m unittest discover -s tests -p 'test_v27*.py' -v
```

Testes com ADB/processos simulados e exportação sintética; nenhum teste físico no Android foi executado pelo desenvolvimento. O teste com captura física feito pelo usuário comprovou apenas a câmera no scrcpy isoladamente.
