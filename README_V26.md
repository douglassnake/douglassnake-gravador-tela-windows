# GravadorTelaWin 2.6 RC1 — projetos editáveis e edição de textos

**Prévia para Windows 10/11 x64.** A v2.5 RC2 homologada permanece na `main`. O motor de vídeo e áudio não foi alterado.

## Como utilizar

1. Selecione a janela do Chrome ou área e inicie a gravação.
2. Pressione **F8** (ou `Ctrl+Alt+D`) para abrir o desenho. Se os atalhos estiverem ocupados, utilize o botão **✎ DESENHAR**.
3. Clique em **Salvar projeto** para gravar um arquivo `.gtwproj` com as anotações editáveis.
4. Para reabrir, inicie gravação com uma área da **mesma largura e altura**, ative o desenho e escolha **Abrir projeto**. Também é aceito o JSON de anotações da v2.5.
5. Para editar um texto já inserido, escolha **Texto**, clique nele, altere o campo de texto e selecione **Atualizar texto**. Desfaça/refaça com `Ctrl+Alt+U` e `Ctrl+Alt+Y`.
6. Pressione F8 novamente para voltar a interagir com o Chrome.

## Segurança e limites

- Projetos contêm apenas tipos de anotação, texto, cores e coordenadas. Não são armazenadas imagens do Chrome, webcam ou áudio.
- O arquivo tem formato JSON versionado e limite de 8 MB.
- Projetos incompatíveis ou inválidos são recusados antes de remover o desenho atual.
- Ao abrir um projeto válido, as anotações anteriores são substituídas após confirmação; o histórico de desfazer começa novamente.
- Ao concluir uma gravação com anotações, o aplicativo tenta salvar `*_anotacoes.gtwproj` ao lado do MP4, além do PNG/JSON.
- Não altera os vídeos já exportados. Apenas objetos de anotação são editados.
- A captura do Chrome exige janela visível e parada. Perfil Estável (24 FPS) é recomendado para desempenho.
- F8, Ctrl+Alt+D e botão manual permanecem disponíveis; cores e espessuras continuam opcionais.

## Verificações

`python -m unittest discover -s tests -p 'test_v*.py' -v`

Teste gráfico simulado: `xvfb-run -a python tests/smoke_toolbar_v26.py`. O funcionamento real com mouse e teclado deve ser homologado no Windows antes do merge.
