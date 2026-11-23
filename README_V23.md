# GravadorTelaWin 2.3 RC1 — Cursor, lupa e anotações

Esta **prévia** acrescenta efeitos de apresentação **opcionais**, preservando o motor de gravação e os padrões homologados da v2.2.

## Recursos novos

- **Halo do cursor:** contorno azul acompanha o mouse dentro da área capturada.
- **Destaque de cliques:** anel amarelo ao pressionar o botão esquerdo.
- **Lupa 2×:** pequeno quadro flutuante ampliando a região ao redor do ponteiro; cerca de 3 imagens/s, limitado à área selecionada. Não altera a resolução ou o enquadramento do MP4 inteiro.
- **Anotações:** caneta livre, seta ou retângulo amarelo sobre a tela; ativação por atalho. Enquanto desenha, os cliques deixam de chegar à janela do Chrome. Desative o desenho para voltar a interagir normalmente.
- **Chrome:** usa o mesmo recorte de desktop da v2.1.2 que funcionou no Windows, sem `gdigrab(hwnd=...)`.

Todas as opções começam desativadas. Sem recursos ativos, o caminho de gravação de imagem/áudio permanece sem alterações.

## Atalhos globais

| Atalho | Ação |
| --- | --- |
| `Ctrl+Shift+R` | Iniciar / encerrar e salvar |
| `Ctrl+Shift+P` | Pausar / retomar |
| `Ctrl+Alt+H` | Ligar / desligar halo do cursor |
| `Ctrl+Alt+C` | Ligar / desligar destaque de cliques |
| `Ctrl+Alt+Z` | Ligar / desligar lupa 2× |
| `Ctrl+Alt+D` | Entrar / sair do modo desenho |
| `Ctrl+Alt+E` | Apagar desenhos feitos nesta gravação |

Antes de gravar, escolha **Caneta**, **Seta** ou **Retângulo** no painel de efeitos. Use `Ctrl+Alt+D` durante a gravação para desenhar na área de captura; pressione novamente para voltar a clicar normalmente em outras aplicações. Os desenhos permanecem na tela até serem apagados ou encerrada a gravação.

## Procedimento de teste

1. Extraia o ZIP em uma pasta própria e inicie pelo `INICIAR.bat` (ou utilize o artefato Windows do GitHub Actions).
2. Faça um teste de 30 segundos no Chrome **com todos os efeitos desativados**. Verifique que áudio e vídeo seguem estáveis.
3. Ative **Halo do cursor** e **Destacar cliques**, grave 30 segundos e confira os círculos no MP4.
4. Ative a **Lupa 2×** com `Ctrl+Alt+Z`, mova o mouse e verifique a área ampliada no vídeo.
5. Escolha **Caneta** antes de gravar. Durante a gravação, pressione `Ctrl+Alt+D`, desenhe uma linha e desligue o modo desenho pelo mesmo atalho. Repita com **Seta** e **Retângulo**.
6. Teste a pausa e a retomada e confira a sincronização do áudio.

## Limitações conhecidas

- A sobreposição depende da transparência do Windows e de sua inclusão na captura GDI. Algumas configurações de GPU/Windows podem não mostrá-la no MP4, embora apareça na tela. O teste real é necessário.
- Se a opção de desenho estiver ativa, a janela selecionada **não recebe cliques** até você desativar o modo de desenho. Use o atalho para alternar.
- A lupa tem tamanho fixo aproximado de 256 × 183 px, não aparece em áreas menores que 320 × 240 px e pode consumir recursos adicionais; desligue-a se notar engasgos.
- O Chrome continua sendo capturado pela **área visível**: não cubra nem mova a janela selecionada.
- Conteúdo protegido e aplicações que bloqueiam captura podem não aparecer no vídeo.
- Os atalhos globais dependem de estarem livres no Windows; se outro aplicativo os registrar primeiro, a função correspondente poderá não responder.
- Os efeitos usam somente o Windows local. Não há upload de vídeo, câmera, áudio ou dados para servidores.

## Status

**Candidato a homologação.** Testes automatizados e captura sintética não substituem a confirmação dos efeitos na gravação de tela real do Windows. A v2.2 já aprovada permanece disponível na branch `main`.
