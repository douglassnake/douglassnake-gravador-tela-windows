# GravadorTelaWin 2.0 — prévia de validação (RC1)

Gravador local de tela para Windows 10/11 de 64 bits, com interface em português. Esta é uma versão de testes: **mantenha instalada a v1.3** enquanto valida a v2.0.

## Novidades da versão 2.0

- **Pré-visualização periódica da área visível** (aproximadamente uma atualização a cada 1,2 segundos, enquanto estiver parado ou pausado). Quando outra janela cobre a área, a prévia também pode mostrá-la; ela não é um espelho perfeito do motor FFmpeg.
- **Gravação de uma janela específica**: clique em **Atualizar lista de janelas** e selecione `Janela • Nome [0x...]`. O FFmpeg usa o identificador (HWND) da janela, sem depender de nomes exclusivos. A janela não deve estar minimizada.
- **Medidores de áudio em dBFS** para microfone e áudio do sistema enquanto a gravação está acontecendo. `—` significa fonte não selecionada ou nível ainda não recebido.
- **Segmentos temporários MKV**, mais resistentes a interrupções do que um MP4 incompleto. O vídeo normal continua sendo finalizado como MP4 (H.264).
- **Recuperar vídeo**: detecta sessões interrompidas em `Vídeos/GravadorTela/gravador_tela_*` e oferece uma recuperação manual; os MKVs originais permanecem intactos após a operação.
- **Gravação final atômica**: utiliza extensão `.partial.mp4` até que o MP4 esteja completo; só então troca para o nome definitivo.
- **Checagem de espaço disponível** antes de iniciar (mínimo de 400 MB).

## Atenção à recuperação

A recuperação de uma gravação interrompida reconstrói **somente o vídeo**. Áudio WAV pode ficar incompleto se o Windows encerrar inesperadamente. A recuperação não garante todos os quadros nem o trecho final danificado e não substitui backup. Caso uma sessão seja recuperada, verifique o vídeo produzido antes de excluir a pasta de origem.

Sessões geradas pela v1.3 (`video_###.mp4`) podem não ser recuperáveis por este procedimento, que trabalha com os novos MKVs.

## Instalação e execução

1. Para testar o executável independente, abra **Actions → Testar e compilar GravadorTelaWin 2.0 → Artifacts** e baixe `GravadorTelaWin-v2-PREVIA-Windows-x64`. Extraia e execute `GravadorTelaWin_v2_PREVIA.exe`.
2. Alternativamente, baixe os arquivos do ramo `feature/gravador-v2`, extraia no Windows e execute `INICIAR.bat`. Isso prepara Python e as dependências no seu perfil de usuário.
3. Escolha o monitor, região ou janela; selecione a qualidade e as fontes de áudio; clique em **INICIAR GRAVAÇÃO**.
4. Para encerrar, clique em **ENCERRAR E SALVAR**. O arquivo MP4 será salvo na pasta escolhida.

A compilação automatizada não equivale a um teste de captura real no Windows. **Os recursos de janela e dispositivos de áudio precisam de validação em computadores reais antes de promover a versão.**

## Testes automatizados

No repositório, com as dependências instaladas:

```powershell
python -m unittest discover -s tests -p test_v2.py -v
```

Os testes cobrem manifesto da sessão, identificação de sessões interrompidas, comando `gdigrab` por monitor/HWND, recuperação de MKVs, finalização de múltiplos trechos e sincronização básica do MP4 com áudio sintético.

## Limitações

- Não inclui ainda aceleração por GPU ou editor de vídeo; isso pertence às versões seguintes.
- Algumas aplicações protegidas, conteúdo DRM, jogos com renderização especial e janelas minimizadas não podem ser capturados normalmente via GDI.
- A prévia usa uma captura da tela visível, enquanto a gravação de janela usa o identificador do processo: poderão mostrar conteúdos diferentes se a janela estiver parcialmente coberta.
- A captura de áudio de sistema depende do dispositivo de reprodução e do loopback WASAPI.
- O `.exe` de prévia não é assinado digitalmente. Não ignore avisos de segurança sem verificar a origem e integridade do artefato.

## Licença

MIT, conforme [LICENSE](LICENSE); dependências e FFmpeg têm licenças específicas.
