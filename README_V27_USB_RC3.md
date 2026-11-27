# GravadorTelaWin 2.7 RC3 — Câmera do celular por USB como Área B

Prévia de desenvolvimento para **Windows 10/11 x64**. Esta versão se baseia na v2.7 RC2; não altera a v2.6 homologada na branch `main`. O HCE permanece separado.

## O que funciona nesta prévia

- Área A: tela, janela visível ou região do Windows, com as ferramentas existentes.
- Área B: **um dispositivo de vídeo DirectShow** selecionado, destinado à câmera de celular em **modo webcam USB (UVC)**.
- Detecção de câmeras de vídeo por FFmpeg, sem instalar drivers, ADB ou aplicativos no celular.
- Captura conjunta em um único processo FFmpeg: apenas **uma entrada `gdigrab`** para Área A e **uma `dshow`** para a câmera B. Isso evita a segunda captura da tela por GDI.
- Exportação independente `*_AreaA.mp4` e `*_AreaB.mp4`, com os controles existentes de iniciar, pausar, retomar e finalizar e áudio de PC, quando configurado.
- Perfis **Fluidez** e **Resolução original**, testes de codificação e relatório JSON da v2.7 RC2 preservados.
- Não permite selecionar a mesma webcam em B e na sobreposição A simultaneamente.

## Pré-requisito essencial

A câmera **precisa aparecer no Windows como dispositivo de vídeo/câmera DirectShow**. Isso é diferente de o computador apenas detectar um telefone conectado como armazenamento ou MTP.

Alguns dispositivos Android compatíveis (por exemplo, com Android 14 QPR1+ e implementação UVC do fabricante) oferecem **USB > Webcam** nas opções de conexão. A disponibilidade depende do modelo. O aplicativo **não consegue ativar esse recurso no celular por conta própria**.

Em celulares sem webcam USB/UVC, esta RC3 **não captura a câmera do aparelho**. Suporte a `scrcpy --video-source=camera` (Android 12+ com depuração USB autorizada) é uma alternativa de arquitetura futura, mas **não foi integrado** neste pacote. No iPhone, a câmera também precisa aparecer como uma fonte de vídeo compatível no Windows; USB comum não basta.

## Passo a passo no Windows

1. **Feche as versões anteriores** do GravadorTelaWin.
2. Conecte o celular ao computador com um **cabo USB de dados**; no celular, habilite **Webcam / Webcam USB**, se disponível.
3. Abra a **v2.7 RC3**. Escolha a origem desejada na Área A (tela, janela ou região).
4. Marque **Gravar duas áreas simultaneamente (2 MP4)**.
5. Em fonte B, escolha **Câmera do celular via USB (UVC)**.
6. Clique em **Detectar câmera USB**. Selecione o nome correto do dispositivo, por exemplo `Android Webcam`. O menu pode listar também a câmera integrada do notebook, outras webcams e placas de captura: o nome não prova que seja um celular.
7. Na **configuração Estúdio**, deixe a mesma câmera desativada para sobreposição em A.
8. Escolha **Fluidez (720p / até 24 FPS)**, 24 FPS e codificação **Automático**. Faça um vídeo curto, com movimento visível na Área A e na câmera B.
9. Finalize, abra os dois MP4 e confira imagem, áudio, duração e fluidez. Se puder, envie o relatório `*_captura_dupla_diagnostico.json` e `*_AreaA_desempenho.csv`.
10. Repita pausando/retomando uma vez. Por fim, desmarque a captura dupla e confirme o modo simples.

## Limites e observações técnicas

- Captura DirectShow não é ADB nem espelhamento de tela; a mídia fica local, e **não há transmissão para nuvem**.
- Não há detecção física confiável de "isto é um celular" a partir apenas do nome DirectShow. O usuário seleciona explicitamente o dispositivo de vídeo.
- O formato, resolução e FPS nativos são negociados com o driver USB; a configuração **Fluidez** limita a **saída** a até 720p e 24 FPS, mas **não acelera a câmera nem cria quadros reais**.
- O áudio gravado continua sendo o microfone/áudio do computador, não o microfone do celular.
- As fontes são iniciadas sequencialmente pelo FFmpeg, mas ficam na mesma sessão. A sincronização exata quadro a quadro ainda depende da validação física.
- Dispositivos que não aparecem no menu de câmeras DirectShow não funcionam neste caminho.
- A detecção não acessa conteúdo do celular, não habilita depuração USB, não instala dependências nem atualiza drivers.
- A qualidade de captura depende de câmera, cabo, porta USB, driver, CPU/GPU e perfil.
- **A v2.7 RC2 não foi homologada quanto à fluidez**. Esta versão busca reduzir o custo GDI por retirar a segunda fonte de desktop, mas ainda exige testes reais.

## Para desenvolvedores

Módulo novo: `gravador_v27_usb_camera.py`. A tela A permanece no motor existente; o motor duplo despacha para `usb_camera_capture_command` quando há `Settings.usb_camera_b`.

Valide com:

```powershell
python -m unittest discover -s tests -p 'test_v27*.py' -v
```

O GitHub Actions constrói `GravadorTelaWin_v2_7_USB_RC3.exe`. As verificações automatizadas não substituem uma webcam UVC física conectada ao Windows.

## Rollback

Feche a RC3 e execute o GravadorTelaWin v2.6 homologado da `main`, sem desinstalar drivers (esta versão não instala nenhum). O código está em branch exclusiva, não alterou a `main` nem os PRs v2.7 anteriores.

## Referências verificadas

- Android webcam USB: https://source.android.com/docs/core/camera/webcam
- FFmpeg DirectShow: https://ffmpeg.org/ffmpeg-devices.html#dshow
- Scrcpy câmera Android (alternativa não integrada): https://github.com/Genymobile/scrcpy/blob/master/doc/camera.md
