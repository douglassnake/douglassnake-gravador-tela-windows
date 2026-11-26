# GravadorTelaWin v2.7 RC2 — Correção de travamentos na captura dupla

Prévia para Windows 10/11 x64, **aguardando homologação física**. A `main` permanece na v2.6 e o HCE fica isolado. **Não houve alteração no motor de captura única**.

## Sintoma identificado na RC1

As duas áreas eram gravadas em arquivos individuais, mas o desempenho de vídeo apresentava engasgos. A RC1 avaliava o codificador através de uma fonte de vídeo, apesar de exigir dois encoders, e configurava filas de 256 pacotes nos dois capturadores. Em 1080p/32-bit, cada quadro bruto possui aproximadamente 8 MB; uma fila potencialmente cheia poderia consumir até cerca de 2 GB por entrada. Isso não prova que a fila tenha ficado cheia no computador; é um risco real que a RC2 limita. Sem os arquivos originais, não é possível distinguir com certeza frames perdidos, duplicados ou gargalo do player.

## O que a RC2 modifica

1. **Perfil `Fluidez (720p / até 24 FPS)` — padrão para captura dupla**: duas áreas independentes, ambas codificadas para no máximo 1280×720, mantendo proporção e sem upscale; a taxa máxima fica em 24 FPS. O recorte é feito nas coordenadas originais; a redução de resolução ocorre na etapa de codificação, não reduz a quantidade de pixels lidos pela captura GDI. A captura única continua sem mudanças.
2. **Perfil `Resolução original (maior carga)`**: mantém os pixels originais das duas áreas e o FPS solicitado. Recomendado após o perfil Fluidez ser validado no equipamento.
3. **Filas limitadas**: 16 quadros por entrada no perfil Fluidez e 32 no Original, contra 256 na RC1; webcam com fila limitada e menor buffer de entrada.
4. **Seleção automática de codificador mais criteriosa**: além do teste de um vídeo já existente, um teste novo codifica duas fontes sintéticas na mesma execução. Se o hardware for incompatível ou tiver desempenho pior que CPU, o modo Automático poderá preferir CPU. O teste é estimativo; NÃO mede a captura real do Windows e não garante FPS constante.
5. **Codificação CPU leve**: preset x264 ultrafast e zerolatency somente no modo dupla captura Fluidez; produz arquivos potencialmente maiores. O modo simples continua com o encoder já homologado.
6. **Timestamps VFR**: `-fps_mode:v:0 vfr` e `-fps_mode:v:1 vfr` evitam duplicação artificial de quadros pelo sincronizador do FFmpeg. FPS efetivo depende da capacidade do computador.
7. **Relatório de desempenho local**: junto dos MP4 gera `Gravacao_..._captura_dupla_diagnostico.json` com FPS configurado, dimensões, codec, benchmark sintético, velocidade média/mínima e amostras abaixo de 1,0×. Não inclui nomes de janelas nem caminhos pessoais. Continua salvando o CSV anterior.
8. **Alertas de sobrecarga**: se a velocidade cair abaixo de 0,97× em duas amostras após oito segundos, informa que a gravação dupla está sobrecarregada. Não altera o FPS durante a sessão nem encerra o vídeo automaticamente por esse motivo.

## Teste sugerido

1. Feche todas as instâncias anteriores do aplicativo.
2. Abra a v2.7 **RC2**, ative `Gravar duas áreas simultaneamente`.
3. Em `Desempenho da captura dupla`, mantenha `Fluidez (720p / até 24 FPS)`; selecione **24 FPS**, webcam desativada, qualidade Equilibrada, codificador Automático.
4. Selecione as duas áreas. Grave cerca de **30 segundos**, com movimentos visíveis nas duas; pause e retome uma vez.
5. Reproduza `*_AreaA.mp4` e `*_AreaB.mp4` em um segundo reprodutor (por exemplo, VLC) para diferenciar stutter do vídeo e da reprodução. Confirme se os congelamentos também aparecem no outro player.
6. Compartilhe o `*_captura_dupla_diagnostico.json` para avaliarmos FPS e perfil; compare com o CSV `_AreaA_desempenho.csv` se necessário.
7. Se estiver estável, repita com `Resolução original (maior carga)` para conhecer o limite do equipamento.
8. Teste o modo simples e os atalhos de desenho, verificando regressões.

## Critérios de homologação

- As duas saídas MP4 contêm vídeo e áudio esperado, sem travamentos perceptíveis e sem deslocamento crescente entre os arquivos;
- Entrada, pausa, retomada e encerramento funcionam;
- A gravação única permanece igual à v2.6;
- Verificar ambos os computadores, quando disponível, por perfil;
- A estabilidade precisa ser comprovada fisicamente; testes sintéticos **não representam** a carga de `gdigrab` com duas telas reais;
- Se as áreas forem muito grandes, pode continuar havendo travamentos de captura mesmo com o perfil Fluidez: para esse caso será necessário um backend mais eficiente (como Desktop Duplication), sujeito a compatibilidade e testes separados.

## Voltar à versão estável

Use a v2.6 da `main`, ou a RC1 anterior da `feature/gravador-v2-7-captura-dupla`. Nenhum vídeo pré-existente é alterado.
