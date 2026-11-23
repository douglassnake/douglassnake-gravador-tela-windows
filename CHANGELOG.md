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
