# GravadorTelaWin 2.4 RC1 — Anotações avançadas

**Prévia para Windows 10/11.** Baseada na v2.3 RC2, já homologada no Windows. O motor de captura do Chrome, FFmpeg, codecs e áudio não foram modificados; novos controles de desenho ficam desativados até entrar no modo desenho.

## Como utilizar

1. Inicie o GravadorTelaWin e selecione **janela do Chrome**, monitor ou área personalizada.
2. Escolha **Caneta**, **Seta** ou **Retângulo** no painel inicial e inicie a gravação.
3. Pressione **Ctrl+Alt+D**. Uma barra flutuante escura aparece no canto superior da área capturada. Uma camada de entrada recebe os movimentos do mouse, sem enviá-los ao Chrome.
4. Escolha a ferramenta, **cor** e **espessura** na barra e arraste o mouse para anotar. Arraste pelo título `DESENHO` para mover a barra dentro da área de gravação.
5. Clique em **↶** para desfazer o último desenho (ou a última limpeza) e **↷** para refazer. **Limpar** apaga as anotações, mas essa limpeza pode ser desfeita.
6. Clique em **Sair** ou pressione **Ctrl+Alt+D** para voltar a controlar o Chrome. Os desenhos ficam sobre o vídeo até apagá-los, mesmo depois de sair do modo desenho.

### Ferramentas

- **3 ferramentas:** Caneta livre, Seta e Retângulo.
- **5 cores:** amarelo, vermelho, verde, azul e branco.
- **3 espessuras:** 2, 4 ou 7 pixels.
- **Histórico de até 250 ações reversíveis:** novo desenho depois de desfazer descarta o ramo de refazer; traços antigos mantêm cor/espessura; limpeza funciona como uma ação reversível.
- **Barra flutuante e arrastável:** visível só durante o desenho, no canto superior da área de captura.
- **Sem webcam ou áudio novos:** a captura GDI/FFmpeg e os padrões de desempenho continuam como a versão aprovada.

### Atalhos globais

| Atalho | Função |
|---|---|
| Ctrl+Shift+R | Iniciar / encerrar a gravação |
| Ctrl+Shift+P | Pausar / retomar |
| Ctrl+Alt+D | Entrar / sair do modo desenho |
| Ctrl+Alt+U | Desfazer |
| Ctrl+Alt+Y | Refazer |
| Ctrl+Alt+E | Limpar desenhos (desfazível) |
| Ctrl+Alt+H | Halo do cursor |
| Ctrl+Alt+C | Destacar cliques |
| Ctrl+Alt+Z | Lupa 2× |

> Se outro software usar o mesmo atalho global, o registro poderá falhar. A barra oferece os comandos sem atalhos.

## Compatibilidade e cuidados

- Os recursos permanecem opcionais: sem entrar no modo desenho, não há barra nem camada de entrada.
- Com desenho ativo, os cliques são usados para anotar, não para operar o Chrome. Ao pausar, encerrar ou sair do modo desenho, a camada de entrada é removida.
- A janela do Chrome deve continuar visível e no mesmo lugar: sua captura utiliza a área do desktop, conforme correção v2.1.1.
- A camada de entrada mantém uma opacidade mínima (~5%); pode haver leve alteração temporária de luminosidade durante o desenho.
- Em alguns drivers Windows, sobreposições transparentes podem aparecer na tela, mas não no vídeo. Confirme o MP4 final.
- O histórico de anotações é local e vale apenas para a gravação corrente; não é um editor de MP4 depois da captura.
- Captura e gravação são locais, sem upload automático para nuvem.

## Verificação técnica

- 35 testes automatizados locais (incluindo regressões de webcam, áudio, desenho, e histórico de undo/redo).
- Smoke gráfico de abertura da barra flutuante sob servidor X virtual.
- A compilação Windows é executada pelo GitHub Actions, e os efeitos precisam de homologação no Windows real antes de serem integrados à `main`.
