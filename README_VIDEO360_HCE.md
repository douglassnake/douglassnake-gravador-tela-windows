# Video360 AI — Etapa 02 / Hardware Capability Engine 0.1

**Status:** prévia de diagnóstico, aguardando homologação nos dois PCs. A gravação e os módulos v2.6 não foram alterados.

## Execução

- Pacote Windows: extraia e execute `DIAGNOSTICAR_HARDWARE.bat` na mesma pasta de `video360_hce.exe` (artefato do GitHub Actions). O JSON será criado localmente.
- Via Python: `python video360_hce.py --output inventario.json`. Usa somente a biblioteca padrão; opcionalmente encontra FFmpeg instalado ou do pacote imageio-ffmpeg.
- Sem `--output`, o diagnóstico é apresentado no terminal e não é gravado.
- Nome de arquivo já existente: recusa sobrescrita; use outro nome.

## Inventário

- CPU: fabricante, nome, núcleos e threads conforme Windows CIM.
- RAM: total e disponível, sem expor conteúdo da memória.
- GPU: todas as instâncias reportadas por `Win32_VideoController`, nomes, drivers e identificadores PCI. `AdapterRAM` é uma informação **não confiável** de VRAM por limite do Windows CIM.
- NVIDIA: consulta local `nvidia-smi` se houver, sem alterar drivers.
- FFmpeg: executa somente codificação de 3 quadros sintéticos pretos em H.264 (NVENC, QSV, AMF e CPU), e lista os métodos de aceleração anunciados. Falhas não alteram o seletor de codecs da v2.6.
- DX11/DX12/DirectML/OpenCL: apenas presença de DLL; **não é teste de execução**, portanto sempre `untested` quando encontrada.
- Vulkan, CUDA, Tensor Cores, AVX2, decodificação e IA: `untested` até as sondagens dedicadas/benchmarks futuros.

O JSON inclui só o nome do executável FFmpeg (sem caminho de usuário), mas contém modelo/ID PCI e número da versão do driver; revise esses campos antes de compartilhar. Não são coletados vídeos, prints, senhas, chaves, conteúdo do navegador ou gravações. Não há chamadas de rede ou instalações automáticas.

## Significado dos estados

- `supported`: a sondagem **deste recurso** funcionou no ambiente testado.
- `unsupported`: recurso não incluído no FFmpeg em uso ou a codificação sintética falhou.
- `unavailable`: não foi possível realizar a sondagem (ex.: executável não encontrado ou timeout).
- `untested`: a funcionalidade ainda não passou por teste funcional; **não interpretar como incompatível**.

## Como homologar

Execute nos dois computadores: notebook Intel HD 4600 + NVIDIA Quadro K3100M e desktop Intel UHD 730. Envie os dois JSONs ou as seções CPU/RAM/GPU/FFmpeg. Verifique se ambas as GPUs aparecem no notebook e se o HCE não reporta CUDA, Tensor Cores, DirectML ou codecs como funcionais apenas pela presença de um driver/DLL.

**Fora do escopo:** benchmarks FPS/latência, instalação/atualização de drivers, processamento real de quadros, inferência IA, mudanças no pipeline e atualização automática da v2.6. Reverter: simplesmente não executar ou remover o diretório da prévia. Branch de segurança da v2.6: `backup/gravador-v2-6-homologada-20261125`.