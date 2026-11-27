"""RC5 startup regression: the installer must stage every local Python import."""
from __future__ import annotations

import ast
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def installed_sources() -> set[str]:
    text = (ROOT / 'INSTALAR.ps1').read_text(encoding='utf-8-sig')
    match = re.search(r'foreach\s*\(\$nome\s+in\s+@\((.*?)\)\s*\)', text, re.I | re.S)
    if not match:
        raise AssertionError('Lista de arquivos Copiar-Programa ausente ou alterada')
    return set(re.findall(r"'([^']+)'", match.group(1)))

def local_imports(filename: str) -> set[str]:
    source = (ROOT / filename).read_text(encoding='utf-8')
    tree = ast.parse(source, filename=filename)
    result = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [n.name for n in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            module = name.split('.', 1)[0]
            candidate = module + '.py'
            if (ROOT / candidate).is_file():
                result.add(candidate)
    return result

class RC5InstallerTests(unittest.TestCase):
    def test_ui_module_is_staged(self):
        self.assertIn('gravador_v27_ui.py', installed_sources())

    def test_all_local_imports_are_staged(self):
        staged = installed_sources()
        pending = ['gravador_tela.py']
        visited = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(local_imports(current) - visited)
        self.assertFalse(visited - staged, f'Módulos importados mas não copiados: {sorted(visited - staged)}')

    def test_all_staged_files_exist(self):
        missing = sorted(name for name in installed_sources() if not (ROOT / name).is_file())
        self.assertEqual(missing, [])

if __name__ == '__main__':
    unittest.main()
