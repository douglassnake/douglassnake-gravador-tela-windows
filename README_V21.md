# GravadorTelaWin 2.1.2 RC — estabilidade de imagem e áudio (23/11/2026)

**Problema relatado:** captura do Chrome corrigida na v2.1.1, mas áudio e vídeo apresentam cortes em qualidade alta com codificação automática.

**Mudanças desta prévia:**

- O modo `Automático` continua testando se a GPU funciona, mas também codifica ~2 segundos de imagem sintética **em movimento**, na resolução da captura (limitada a 2560 × 1440) e FPS configurado. Uma GPU que não atingir uma margem de 1,15× do tempo real não será selecionada automaticamente. Esse teste é uma aproximação e não substitui a captura real do Chrome.
- O codificador por CPU passa do preset `veryfast` para `superfast` para reduzir a carga; isso pode aumentar o tamanho do arquivo, mesmo mantendo a qualidade CRF escolhida.
- Novo perfil `Estável (24 FPS)` (CRF 21), adequado para gravações com texto e apresentação de telas.
- Indicador de advertência quando a velocidade de codificação fica abaixo de 0,85× por três medições consecutivas após 10 segundos.
- Salva `Gravacao_..._desempenho.csv` junto ao MP4 com informações técnicas do codificador, FPS e velocidade para diagnóstico. Não inclui nomes de janela, imagens nem caminhos particulares.
- Mantém o recorte por região usado na correção do Chrome e os recursos de captura e recuperação da v2.1.1.

**Teste no Windows:** grave 1 minuto de Chrome em `Estável (24 FPS)` e `Automático` e depois 1 minuto com `CPU (compatível)`. Compare a fluidez e, se houver cortes, envie apenas o CSV correspondente (revise antes de compartilhar). Também verifique no Gerenciador de Tarefas se CPU, GPU e disco ficam perto de 100% durante a gravação.

**Limitações:** o teste sintético de GPU não mede captura GDI nem a sobrecarga do Chrome. Não há garantia de eliminação dos cortes em todo computador; esta versão precisa de teste real. Nenhum vídeo é enviado à nuvem. A v1.3 permanece intocada na branch `main`.

---

# GravadorTelaWin 2.1.1 RC — correção de captura do Chrome

## Correção da captura de janela (Chrome e aplicativos acelerados)

Na v2.1, a seleção de uma janela enviava o identificador da janela (`hwnd`) ao `gdigrab` do FFmpeg. Em aplicações que usam GPU, como o Chrome, esse modo pode resultar em vídeo preto ou sem imagem. A v2.1.1 usa **a mesma captura de região do desktop que já funcionava**, calculando o recorte automaticamente pela posição da janela.

**Como testar:** selecione uma janela normal do Chrome na lista, clique em Gravar, use o Chrome durante 15–30 segundos e finalize com `Ctrl+Shift+R`. O gravador minimiza automaticamente para não cobrir o navegador. Ao salvar, o gravador reaparece.

**Limitações transparentes:** este é um modo compatível de captura de **pixels visíveis**. Deixe o Chrome aberto, dentro do monitor, não o cubra com outra janela e evite movê-lo ou redimensioná-lo durante a gravação. Ele não captura conteúdo de uma janela minimizada ou oculta. Para capturar independentemente dessas limitações, será necessária uma integração posterior com `Windows.Graphics.Capture`. A gravação de conteúdo protegido por DRM pode continuar indisponível.

A seleção por área, os monitores, o áudio e a codificação por GPU não foram alterados. Validar o comportamento no Windows com o Chrome é obrigatório antes de integrar à branch principal.

---

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
