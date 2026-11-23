## 2.3.0-rc1 — efeitos visuais opcionais (23/11/2026)

- Halo do cursor e indicador de clique esquerdo sobrepostos à área visível gravada.
- Lupa 2× em quadro flutuante, atualizada até 3,3 vezes por segundo.
- Anotações com caneta, seta e retângulo ativadas por atalho global; apagar desenhos sem reiniciar a gravação.
- Efeitos desativados por padrão para preservar a qualidade homologada do Chrome e do áudio.
- Novo módulo `gravador_v23_overlay.py` incluído no instalador local e no build Windows.
- Versão em branch de prévia, aguardando confirmação da captura dos efeitos no Windows.

## 2.1.2-rc — ajustes de estabilidade e diagnóstico (23/11/2026)

- Benchmark de aproximadamente 2 segundos de vídeo dinâmico para seleção automática de GPU, substituindo a aprovação apenas pelo teste pequeno de compatibilidade.
- Libx264 passou a usar `superfast` para reduzir esforço da CPU (arquivos podem ficar maiores).
- Perfil Estável (24 FPS) com qualidade CRF 21.
- Advertência de processamento lento após três amostras abaixo de 0,85x em gravação contínua.
- Relatório CSV de FPS e velocidade, salvo ao lado do MP4 sem informação do conteúdo capturado.
- Mantém a captura visível de janela do Chrome da v2.1.1.

## 2.1.1-rc — correção de janela Chrome (23/11/2026)

- Substituída captura GDI direta de janela por captura da área visível do desktop calculada automaticamente.
- Tratado recorte de janela parcialmente fora do desktop virtual e múltiplos monitores.
- O gravador minimiza ao iniciar/retomar captura de janela e reaparece ao salvar ou falhar.
- Aviso da limitação de janelas cobertas, minimizadas ou movidas.
- Testes de regressão para argumentos FFmpeg e recortes de janela.
- Correção limitada ao modo janela; modos monitor, região, áudio, perfis e recuperação preservados.

# Histórico de versões

## 2.1.0-rc1 — desempenho (prévia)

- Escolha de codificador H.264: automático, CPU (libx264), NVIDIA NVENC, Intel Quick Sync e AMD AMF.
- Teste real de codificação antes de selecionar a GPU; seleção automática usa CPU quando não há GPU funcional.
- Inicialização da gravação em thread para não travar a interface enquanto a GPU é testada.
- Quatro perfis de FPS/qualidade: equilibrado, alta qualidade, arquivo menor e fluido (60 FPS).
- Indicadores de FPS efetivos, velocidade do FFmpeg e espaço livre no disco.
- Registro periódico de `desempenho.json` na pasta temporária da sessão (dados técnicos locais).
- Reserva conservadora de espaço para exportação e encerramento preventivo se o espaço ficar insuficiente.
- Testes automatizados da seleção de encoder, fallback, leitura de telemetria e exportação de vídeo.

**Pendente:** homologação real em Windows 10/11 com GPUs NVIDIA, Intel e AMD; os testes locais não comprovam ganho de desempenho.


## 2.0.0-rc1 — prévia

- Captura de janela por HWND, seleção pela lista e atualização de janelas abertas.
- Pré-visualização periódica da área visível sem prévia durante a gravação para reduzir interferência.
- Indicadores de nível de áudio (dBFS) durante a gravação.
- Segmentos MKV temporários com possibilidade de recuperação de vídeo após falhas.
- Saída MP4 criada atomicamente via arquivo parcial.
- Detecção de sessões recuperáveis; recuperação manual preservando a pasta de origem.
- Verificação inicial de espaço livre (400 MB).
- Testes automatizados e workflow separado de compilação Windows de prévia.

**Validação pendente:** captura efetiva de janelas e áudio, performance e gravações longas em máquinas Windows.

## 1.3 — estável de referência

- Correção da detecção de instalações Python já existentes no Windows.
- Inicialização via instalador local e recuperação automática de pip.
- Captura por monitor ou região, áudio do sistema/microfone, pausa, retomada e exportação MP4.
