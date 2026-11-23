# GravadorTelaWin 2.1 RC1 — desempenho

Versão de prévia da evolução do GravadorTelaWin. **Não substitui a v1.3 que já funcionou no Windows.**

## Novidades

- **GPU H.264 (opcional):** escolha `Automático`, `CPU (compatível)`, `NVIDIA NVENC`, `Intel Quick Sync` ou `AMD AMF`.
- **Validação de hardware:** o aplicativo consulta os encoders presentes no FFmpeg e tenta codificar frames de teste na GPU. Apenas codecs que passam no teste são selecionados. O modo automático recorre ao libx264 quando não há GPU utilizável; a escolha explícita exibe erro em vez de trocar silenciosamente.
- **Perfis:** equilibrado (30 FPS), alta qualidade (30 FPS), arquivo menor (24 FPS), fluido (60 FPS), ou personalizado com controles existentes.
- **Painel em tempo real:** codificador escolhido, FPS informado pelo FFmpeg, velocidade de processamento (`1.00x` ≈ tempo real) e espaço disponível.
- **Proteção de disco:** compara espaço livre com reserva conservadora estimada para exportação do MP4 e tenta encerrar/salvar preventivamente.
- **Diagnóstico local:** a pasta temporária da sessão guarda registros `ffmpeg_###.progress`, `ffmpeg_###.log` e `desempenho.json`, atualizados enquanto se grava. O app não envia esses dados à nuvem.
- **Interface responsiva:** autotestes de hardware são executados fora da thread da interface.

## Como experimentar no Windows

1. Mantenha sua versão estável e extraia os arquivos da v2.1 em uma pasta separada.
2. Rode `INICIAR.bat` (depende da conexão na primeira instalação) ou baixe o `.exe` no [GitHub Actions](../../actions).
3. Selecione **CPU (compatível)** e grave 2 minutos em 30 FPS com e sem microfone; reproduza o MP4.
4. Selecione **Automático** e repita. Confira o codificador exibido e compare FPS, consumo da CPU e sincronização de áudio.
5. Se tiver GPU suportada, experimente selecioná-la explicitamente e veja se o teste de inicialização passa.
6. Faça um teste de gravação longa de 30–60 minutos com espaço suficiente no disco. Pause, retome e confirme exportação e possibilidade de recuperação.

## Interpretação das medidas

- FPS **informado pelo FFmpeg** não equivale necessariamente à quantidade de quadros visuais distintos nem à fluidez percebida; use inspeção do MP4 e testes comparativos.
- Uma velocidade abaixo de `1.00x` pode indicar dificuldade de codificação em tempo real, dependendo da configuração.
- Aceleração H.264 **não acelera necessariamente a captura `gdigrab`**; o ganho de CPU depende da placa, driver, resolução e cena.
- A estimativa de reserva em disco não é garantia. O encerramento preventivo pode falhar se o disco ficar cheio repentinamente. A recuperação de v2.0 preserva MKVs originais, com áudio não garantido.
- O build do GitHub Actions verifica compilação e exportação sintética, não substitui testes de captura/áudio reais em Windows.

## Dados e privacidade

O app funciona localmente. Verifique arquivos de sessão e logs antes de compartilhar: podem conter nomes de arquivos, caminhos e configurações da máquina.

## Próxima etapa sugerida

Homologar desempenho em Windows com NVIDIA/Intel/AMD, comparar uso de CPU e estabilidade; em seguida avançar para webcam, trilhas de áudio separadas e ferramentas de apresentação (v2.2).
