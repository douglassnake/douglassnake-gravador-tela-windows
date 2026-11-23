# GravadorTelaWin 2.5 RC1 — Borracha, textos e exportação de anotações

**Prévia para homologação em Windows 10/11 x64.** A v2.4 homologada continua na `main`.

## Ferramentas

Com uma gravação ativa, pressione **Ctrl+Alt+D** para abrir o desenho e sua barra flutuante.

1. **Borracha** — clique ou arraste sobre um traço, retângulo, seta ou texto para apagar **o objeto inteiro**. Um arrasto é uma ação reversível (Ctrl+Alt+U). Não apaga pixels da página nem partes do vídeo.
2. **Texto** — selecione **Texto**, escreva na caixa **Texto:** da barra e clique onde deseja posicionar a legenda. O texto segue a cor selecionada; as opções 2/4/7 px definem tamanhos de fonte de 18/24/32 px. Ao sair do desenho, o texto continua no overlay do vídeo.
3. **Salvar PNG + JSON** — na barra, clique em **Salvar PNG + JSON** e escolha um nome. O PNG contém somente anotações em fundo transparente (RGBA). O JSON guarda os elementos, coordenadas relativas à área gravada, cores e texto para futuro processamento. Não contém captura da tela.
4. **Exportação automática ao finalizar** — se houver alguma anotação visível ao encerrar e salvar o MP4, o aplicativo também gera `<nome-do-video>_anotacoes.png` e `<nome-do-video>_anotacoes.json` junto ao vídeo. Uma falha na exportação não invalida o MP4.

As ferramentas **Caneta, Seta e Retângulo**, cores, espessuras, desfazer/refazer, lupa, webcam, MP4, áudio independente e captura compatível do Chrome continuam disponíveis. Não foram feitas mudanças no motor FFmpeg nem nas opções padrão de vídeo.

## Atalhos

- `Ctrl+Alt+D`: entrar/sair do desenho.
- `Ctrl+Alt+U`: desfazer, inclusive a borracha.
- `Ctrl+Alt+Y`: refazer.
- `Ctrl+Alt+E`: apagar todas as anotações (reversível).
- `Ctrl+Shift+R`: iniciar/finalizar gravação.
- `Ctrl+Shift+P`: pausar/retomar.

## Validação sugerida

1. Confirme gravação do Chrome com a webcam/efeitos desligados por 30 segundos.
2. Ative desenho, crie uma seta e um retângulo, apague cada um com **Borracha**, e use desfazer/refazer.
3. Selecione **Texto**, escreva `Destaque do relatório`, clique na página, saia do desenho e navegue no Chrome.
4. Use **Salvar PNG + JSON**, abra o PNG em um visualizador e verifique a transparência.
5. Encerre a gravação e confira o MP4 com áudio e os dois arquivos `_anotacoes` ao seu lado.

## Observações

- A borracha remove **objetos completos**, não apenas o trecho da caneta atingido.
- O texto usa o overlay visual do Windows; a fonte exportada para PNG pode ter pequenas diferenças de renderização em relação à fonte do Tk.
- O JSON é um formato aberto de dados estruturados, **não é importação automática** de desenhos no aplicativo nesta versão.
- Só as anotações visíveis e não apagadas são exportadas; não há extração do conteúdo do Chrome.
- Arquivos PNG/JSON podem revelar textos escritos pelo usuário. Revise-os antes de compartilhar.
- Captura visível de janela do Chrome deve continuar com a janela à frente, sem alterar posição durante a gravação.
- **Teste real em Windows pendente.** A aprovação de testes locais e CI não certifica a captura do overlay em todas as GPUs.
