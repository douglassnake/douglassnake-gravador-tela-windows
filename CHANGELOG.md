# Histórico de versões

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
