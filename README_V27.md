# GravadorTelaWin 2.7 RC1 — captura simultânea de duas telas ou regiões

**Prévia Windows 10/11 x64 para homologação.** A v2.6 mantém-se intacta na `main`. A implementação da captura dupla fica numa branch própria. O Hardware Capability Engine (HCE) não foi integrado nem alterado.

## O que mudou

- **Área A**: continua com todas as opções de captura existentes — tela, janela visível, região, webcam e anotações.
- **Área B (nova)**: escolha outro monitor, uma janela visível, ou faça um segundo recorte personalizado com o mouse.
- **Gravação simultânea**: uma execução do FFmpeg captura ambas as áreas, com dois fluxos de vídeo H.264 no MKV temporário e áudio WASAPI capturado apenas uma vez por segmento.
- **Dois MP4 independentes**: `Gravacao_YYYYMMDD_HHMMSS_AreaA.mp4` e `..._AreaB.mp4`. O áudio selecionado é incluído nos dois arquivos; opção de trilhas de áudio separadas é preservada.
- **Um controle para iniciar, pausar, retomar e finalizar**. As áreas podem ter dimensões e posições diferentes, inclusive no mesmo monitor.
- **Webcam, desenho e efeitos**: continuam disponíveis na Área A; a Área B não recebe webcam nem possui um editor de desenho independente nesta prévia. Regiões parcialmente sobrepostas podem registrar elementos visuais de A também em B.
- **Modo simples**: continua desativada a opção de segunda área por padrão e o caminho de gravação da v2.6 não é substituído.

## Como testar

1. Extraia o ZIP em pasta nova e inicie com `INICIAR.bat`, ou execute o artefato Windows construído pelo GitHub Actions.
2. Escolha o monitor ou a região da **Área A** como antes.
3. Marque **Gravar duas áreas simultaneamente (2 MP4)**.
4. Na **Área B**, escolha `Monitor 2`, outra janela visível ou **Selecionar região B**. É possível usar duas áreas recortadas do mesmo monitor.
5. Selecione **24 FPS / Perfil Estável** no primeiro teste e deixe a webcam desligada. Ative som caso deseje áudio em ambos os MP4.
6. Grave aproximadamente 30 segundos, pause e retome uma vez, mova conteúdo distinto nas duas regiões, finalize e confira os dois MP4. Compare o mesmo evento visual nas duas gravações e confira sincronia do som.
7. Repita o teste com a webcam ou desenho em A, verificando se a captura B permanece correta.
8. Desmarque a opção e confirme que a gravação simples da v2.6 continua funcionando.

## Limitações e cuidados

- A captura usa a **área visível do desktop**; ao gravar janelas, não minimize, cubra ou mova o alvo durante a sessão. Duas janelas que se encobrem não podem ser capturadas simultaneamente sem a sobreposição aparecer no vídeo.
- O aplicativo permite áreas distintas parcialmente sobrepostas, mas rejeita áreas idênticas.
- FFmpeg inicia duas capturas na mesma execução, mas não garante quadros com timestamps rigorosamente idênticos: a simultaneidade visual deverá ser validada nos MP4 físicos. O tempo de início de cada stream pode diferir em alguns frames.
- Dois codificadores ativos aumentam demanda por CPU/GPU e consumo de disco. Se houver quedas ou travamentos, tente **24 ou 15 FPS** e codificador CPU compatível.
- Em caso de falha de exportação, os MKV temporários ficam preservados para análise. Não remova as pastas `gravador_tela_*` antes de verificar os arquivos.
- Arquivos de vídeo e áudio **permanecem locais**. Não há nuvem, drivers novos ou instalação de IA.
- A recuperação automática antiga foi escrita originalmente para MKV de uma única faixa; a recuperação após interrupção da captura dupla exige procedimento específico até que seja homologada.
- **Esta RC1 não gera vídeo lado a lado.** O objetivo é entregar duas fontes independentes em resolução própria. A composição lado a lado poderá ser acrescentada após validar os dois MP4.

## Validação automatizada

```bash
python -m unittest discover -s tests -p 'test_v27*.py' -v
```

O teste sintético usa FFmpeg com duas entradas de teste, pausa simulada em dois segmentos e exportação independente. O teste gráfico usa `xvfb-run -a python tests/smoke_v27_gui.py` em Linux; os controles Win32/GDI precisam de validação manual no Windows.

## Reverter

Use o executável homologado da v2.6, obtido na branch `main`. Os arquivos originais não são alterados pela prévia. Não faça merge em `main` antes da homologação física.


**Correção de fluidez:** veja [v2.7 RC2](README_V27_RC2.md).
