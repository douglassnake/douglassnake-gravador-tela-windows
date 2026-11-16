# -*- coding: utf-8 -*-
"""Autoteste de compatibilidade. Funciona com Python sem bibliotecas externas."""
import importlib.util
import struct
import sys

falhas = []
if tuple(sys.version_info[:2]) not in ((3, 11), (3, 12), (3, 13)):
    falhas.append("versao fora de 3.11-3.13")
if struct.calcsize("P") * 8 != 64:
    falhas.append("Python nao e 64 bits")
try:
    import tkinter  # noqa: F401
    import venv  # noqa: F401
except Exception as exc:
    falhas.append("tkinter/venv ausente: " + str(exc))
if (importlib.util.find_spec("pip") is None and
        importlib.util.find_spec("ensurepip") is None):
    falhas.append("pip e ensurepip ausentes")

print("GRAVADOR_OK" if not falhas else "GRAVADOR_INCOMPATIVEL")
print("CAMINHO=" + sys.executable)
print("VERSAO=" + sys.version.split()[0] + "; BITS=" + str(struct.calcsize("P") * 8))
if falhas:
    print("MOTIVOS=" + "; ".join(falhas))
sys.exit(0 if not falhas else 1)
