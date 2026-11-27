# GravadorTelaWin v2.7 RC5 — hotfix do instalador

A RC5 inclui gravador_v27_ui.py, mas o bootstrap PowerShell original não copiava esse módulo para %LOCALAPPDATA%\GravadorTelaWin. Como gravador_tela.py o importa no início, isso causava falha de inicialização com código 1 (ModuleNotFoundError esperado).

**Correção:** o instalador copia também gravador_v27_ui.py. Foi acrescentado um teste estático de integridade que percorre os imports Python locais do programa e exige que todos os módulos estejam na lista Copiar-Programa.

## Instalação / recuperação

1. Feche o GravadorTelaWin. Mantenha as gravações MP4 e a pasta de dados intactas.
2. Extraia o novo ZIP em uma pasta separada da RC5 anterior.
3. Execute INICIAR.bat na pasta extraída. O instalador substitui os arquivos-fonte locais, inclusive o novo módulo; reutiliza o Python/.venv existentes.
4. Se a janela não abrir, execute DIAGNOSTICO.bat e examine %LOCALAPPDATA%\GravadorTelaWin\gravador_erros.log.

Para confirmar a cópia sem reinstalar, abra PowerShell e execute:

Test-Path "$env:LOCALAPPDATA\GravadorTelaWin\gravador_v27_ui.py"

Deve responder True após a instalação corrigida.

**Escopo:** apenas instalador, documentação e testes. Nenhuma alteração em gravador_tela.py ou nos módulos de captura/scrcpy. main da v2.6 preservada; homologação da v2.7 permanece pendente.
