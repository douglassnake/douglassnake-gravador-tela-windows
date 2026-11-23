# GravadorTelaWin 2.2 RC1 — Estúdio (prévia)

Esta versão acrescenta **webcam opcional no canto inferior direito** e **áudio em trilhas independentes** no mesmo MP4, preservando por padrão a captura compatível da v2.1.2 para Chrome.

## Novidades

- **Webcam (opcional):** clique em **Buscar webcams** e selecione uma câmera DirectShow. O FFmpeg inclui uma sobreposição de vídeo no canto inferior direito. A câmera utiliza até 26% da largura capturada, limitado a 480 px, e 15 FPS. Ela deve estar conectada e permitir acesso pelo Windows.
- **Trilhas de áudio independentes (opcional):** além do áudio Mix reproduzido normalmente, o MP4 inclui trilhas Microfone e/ou Sistema, de acordo com as fontes marcadas. Em editores que suportam seleção de trilhas, elas podem ser trabalhadas separadamente.
- **Compatibilidade:** sem webcam e sem trilhas separadas, o comando de captura e a exportação permanecem equivalentes ao funcionamento homologado na v2.1.2.
- **Pausa e retomada:** todos os segmentos com áudio separado mantêm a mesma ordem de trilhas. Se uma fonte de áudio falhar durante um segmento, sua trilha é preenchida com silêncio, para evitar perda da estrutura na concatenação.

## Testar

1. Extraia o pacote em uma pasta nova, execute `INICIAR.bat` ou o executável da branch de prévia (quando disponível).
2. Primeiro, deixe **Nenhuma webcam** e trilhas separadas desmarcadas. Grave o Chrome durante 30 s para confirmar que não houve regressão.
3. Clique em **Buscar webcams**, selecione uma webcam, e faça uma gravação curta de 30 s com Chrome visível, qualidade Equilibrada, perfil Estável (24 FPS), codificação Automática.
4. Marque **Áudio do microfone**, **Áudio do computador** e **Guardar mix + trilhas de áudio separadas**. Grave 30 s, pause e retome. Abra o MP4 num editor que permita verificar as faixas: primeira Mix, segunda Microfone, terceira Sistema.
5. Confira que a imagem não engasga e que o áudio permanece sincronizado. Se houver queda de FPS com a webcam ativada, teste CPU (compatível) ou mantenha a câmera desativada.

## Limitações

- **Versão candidata:** os testes automáticos conseguem simular webcam e áudio, mas a câmera DirectShow real e as interfaces físicas **ainda exigem homologação no Windows**.
- A sobreposição utiliza FFmpeg com DirectShow. Algumas câmeras/drivers podem rejeitar 15 FPS ou estar ocupadas; nesse caso, desmarque a webcam e tente novamente.
- A webcam adiciona carga de processamento; ela não utiliza a câmera para gravar seu microfone. O áudio continua vindo das fontes marcadas.
- O Chrome ainda é gravado pela **região visível**: não cubra nem mova a janela selecionada.
- Nem todos os reprodutores permitem trocar ou editar múltiplas trilhas MP4. A primeira trilha **Mix** é a padrão.
- Conteúdo protegido ou aplicativos que bloqueiam captura podem não aparecer na gravação.

## Segurança e privacidade

Tudo é processado localmente; não há envio de câmera, áudio ou vídeos para servidores. O programa solicita acesso apenas aos dispositivos que você selecionar. Os registros de desempenho podem conter caminhos e nomes de janelas; revise antes de compartilhar.

## Desenvolvimento

O código permanece em branch de prévia. O foco seguinte será a **v2.2 RC2**, com testes reais em diferentes webcams e destaque visual do mouse opcional.
