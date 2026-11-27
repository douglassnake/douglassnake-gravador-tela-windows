# -*- coding: utf-8 -*-
"""Instalador, recuperador e diagnostico do GravadorTelaWin (Windows).

Usa apenas a biblioteca padrao do Python, inclusive quando pip esta ausente.
A instalacao de bibliotecas acontece somente na pasta .venv deste app.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
EXE = VENV / 'Scripts' / 'python.exe' if os.name == 'nt' else VENV / 'bin' / 'python'
REQUIREMENTS = ROOT / 'requirements.txt'
MARKER = VENV / 'instalado-v2.0.json'
LOGFILE = ROOT / 'diagnostico_instalacao.log'
SOURCE = ROOT / 'gravador_tela.py'
RECOMMENDED = [(3, 12), (3, 11), (3, 13)]
LOG = None


class SetupError(Exception):
    pass


def report(message: str = '') -> None:
    print(message, flush=True)
    if LOG:
        LOG.write(message + '\n')
        LOG.flush()


def shell(command: list[str], description: str, *, timeout: int = 600, capture: bool = False):
    report('\n== ' + description + ' ==')
    report('Comando: ' + ' '.join('"'+p+'"' if ' ' in p else p for p in command))
    try:
        completed = subprocess.run(
            command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        output = completed.stdout or ''
        if not capture:
            report(output.rstrip()[-8000:])
        elif completed.returncode:
            report(output.rstrip()[-2500:])
        report('Codigo de retorno: ' + str(completed.returncode))
        return completed.returncode == 0, output
    except (OSError, subprocess.TimeoutExpired) as exc:
        report('Falha: ' + str(exc))
        return False, ''


def probe(command: list[str]):
    code = (
        'import json,sys,struct,importlib.util;'
        'print(json.dumps({"version":list(sys.version_info[:2]),'
        '"bits":struct.calcsize("P")*8,"executable":sys.executable,'
        '"has_pip":importlib.util.find_spec("pip") is not None,'
        '"has_ensurepip":importlib.util.find_spec("ensurepip") is not None,'
        '"is_venv":sys.prefix != sys.base_prefix}))'
    )
    try:
        r = subprocess.run(command + ['-c', code], cwd=str(ROOT), capture_output=True,
                           timeout=10, text=True, encoding='utf-8', errors='replace')
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def select_python():
    candidates = []
    # v1.2: o bootstrap escolhe um Python privativo, sem depender do PATH do Windows.
    private_exe = os.environ.get('GRAVADOR_PYTHON_EXE', '').strip()
    if private_exe and Path(private_exe).is_file():
        candidates.append([private_exe])
    # O launcher do Windows ajuda a selecionar uma versao compativel de forma precisa.
    if not private_exe and os.name == 'nt' and shutil.which('py'):
        for major, minor in RECOMMENDED:
            candidates.append(['py', f'-{major}.{minor}'])
    # Para instalacoes sem o launcher py.exe.
    if not private_exe and shutil.which('python'):
        candidates.append(['python'])
    if os.name != 'nt':
        candidates.append([sys.executable])
    found = []
    for order, command in enumerate(candidates):
        info = probe(command)
        if info and tuple(info['version']) in RECOMMENDED and info['bits'] == 64:
            found.append((bool(info['has_pip'] or info['has_ensurepip']), -order, command, info))
            report(f"Python detectado: {info['version'][0]}.{info['version'][1]} ({info['bits']}-bit) | "
                   f"pip={info['has_pip']} | ensurepip={info['has_ensurepip']} | {info['executable']}")
    if not found:
        raise SetupError(
            'Nao encontrei Python 3.11, 3.12 ou 3.13 de 64 bits.\n'
            'Instale o Python 3.12 de https://www.python.org/downloads/windows/\n'
            'Durante a instalacao, habilite pip e Add python.exe to PATH.\n'
            'Depois execute INICIAR.bat novamente.'
        )
    found.sort(reverse=True, key=lambda rec: (rec[0], rec[1]))
    _, _, command, info = found[0]
    if not info['has_pip'] and not info['has_ensurepip']:
        raise SetupError(
            'A instalacao do Python encontrada nao tem pip nem ensurepip.\n'
            'Execute o instalador oficial do Python 3.12, escolha Modify e habilite pip.\n'
            'Depois execute INICIAR.bat novamente.'
        )
    report(f"Python selecionado: {info['executable']}")
    return command, info


def check_pip():
    if not EXE.is_file():
        return False
    info = probe([str(EXE)])
    if not (info is not None and info['is_venv'] and info['has_pip']):
        return False
    try:
        result = subprocess.run([str(EXE), '-m', 'pip', '--version'],
                                cwd=str(ROOT), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def backup_existing_environment():
    if not VENV.exists():
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = ROOT / ('.venv_backup_' + stamp)
    number = 1
    while backup.exists():
        backup = ROOT / (f'.venv_backup_{stamp}_{number:02d}')
        number += 1
    report('Ambiente anterior sera preservado em: ' + str(backup))
    try:
        VENV.rename(backup)
    except OSError as exc:
        raise SetupError(
            f'Nao foi possivel renomear .venv: {exc}\n'
            'Feche todos os programas que estejam usando essa pasta e tente novamente.'
        )


def make_environment(base: list[str], info: dict):
    report('\nCriando ambiente virtual local...')
    ok, _ = shell(base + ['-m', 'venv', str(VENV)], 'Criar .venv', timeout=180)
    if not ok or not EXE.is_file():
        # Pode ocorrer quando a instalacao foi distribuida sem ensurepip.
        report('Tentando criar o ambiente sem pip para recuperar em seguida...')
        ok, _ = shell(base + ['-m', 'venv', '--without-pip', str(VENV)],
                      'Criar .venv sem pip', timeout=180)
        if not ok or not EXE.is_file():
            raise SetupError('Nao foi possivel criar o ambiente virtual.\n'
                             'Repare a instalacao do Python, incluindo os componentes pip e venv.')
    if not check_pip():
        repair_pip(base, info)
    if not check_pip():
        raise SetupError('Falha ao adicionar pip ao ambiente .venv.\n'
                         'Reinstale o Python 3.12 oficial com pip e venv habilitados.')


def repair_pip(base: list[str], info: dict):
    report('\nPip nao encontrado em .venv. Executando recuperacao automatica...')
    if EXE.is_file():
        shell([str(EXE), '-m', 'ensurepip', '--upgrade'], 'Reparar com ensurepip', timeout=180)
        if check_pip():
            report('Pip restaurado com ensurepip.')
            return True
    # A opcao --python do pip >=22.3 permite provisionar um venv sem pip.
    if info.get('has_pip'):
        shell(base + ['-m', 'pip', '--python', str(VENV), 'install', '--upgrade', 'pip'],
              'Reparar com pip do Python principal', timeout=300)
        if check_pip():
            report('Pip restaurado pelo Python principal.')
            return True
    return False


def prepare(base: list[str], info: dict, *, build: bool = False):
    if not EXE.is_file():
        if VENV.exists():
            backup_existing_environment()
        make_environment(base, info)
    elif not check_pip():
        if not repair_pip(base, info):
            report('Ambiente anterior nao foi recuperado. Criando um novo ambiente isolado...')
            backup_existing_environment()
            make_environment(base, info)

    info_venv = probe([str(EXE)])
    if not info_venv or not info_venv['is_venv'] or not info_venv['has_pip']:
        raise SetupError('O ambiente .venv nao esta pronto para instalar bibliotecas.')
    if tuple(info_venv['version']) != tuple(info['version']):
        report('Versao Python do .venv nao corresponde a versao selecionada. Recriando...')
        backup_existing_environment()
        make_environment(base, info)

    req_hash = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    signature = {'requirements_sha256': req_hash, 'python': info['version']}
    installed_ok = False
    if MARKER.exists() and not build:
        try:
            installed_ok = json.loads(MARKER.read_text(encoding='utf-8')) == signature
        except (ValueError, OSError):
            pass
        if installed_ok:
            checked, _ = shell([str(EXE), '-c',
                                'import imageio_ffmpeg, mss, numpy, PIL, soundcard'],
                               'Verificacao de bibliotecas', capture=True, timeout=30)
            installed_ok = checked
    if not installed_ok or build:
        command = [str(EXE), '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--timeout', '25', '--retries', '2', '-r', str(REQUIREMENTS)]
        if build:
            command += ['pyinstaller>=6.0,<7']
        ok, _ = shell(command, 'Instalacao das bibliotecas', timeout=900)
        if not ok:
            raise SetupError('Nao foi possivel instalar as bibliotecas.\n'
                             'Confira a conexao com a internet e o diagnostico_instalacao.log.')
        MARKER.write_text(json.dumps(signature, indent=2), encoding='utf-8')
    report('\nAmbiente pronto.')


def launch_app():
    error_log = ROOT / 'gravador_erros.log'
    with error_log.open('ab') as log:
        proc = subprocess.Popen(
            [str(EXE), str(SOURCE)], cwd=str(ROOT), stdin=subprocess.DEVNULL,
            stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        time.sleep(1.5)
        if proc.poll() is not None and proc.returncode != 0:
            raise SetupError('O aplicativo fechou ao iniciar (codigo: ' + str(proc.returncode) + ').\n'
                             'Consulte o arquivo gravador_erros.log para identificar a falha.')
    report('Aplicativo iniciado.')


def build_exe():
    args = [
        str(EXE), '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
        '--name', 'GravadorTelaWin_v2_7_SCRCPY_RC4', '--collect-all', 'imageio_ffmpeg',
        '--collect-all', 'soundcard', '--collect-all', 'comtypes',
        '--hidden-import', 'comtypes', '--hidden-import', 'comtypes.client',
        str(SOURCE),
    ]
    ok, _ = shell(args, 'Gerar .exe com PyInstaller', timeout=1800)
    result = ROOT / 'dist' / 'GravadorTelaWin_v2_7_SCRCPY_RC4.exe'
    if not ok or not result.exists():
        raise SetupError('Erro na compilacao do executavel. Consulte diagnostico_instalacao.log.')
    report('\nEXE criado em: ' + str(result))


def diagnose(base: list[str], info: dict):
    report('Python principal: ' + str(info['executable']))
    report('Ambiente .venv: ' + str(VENV))
    report('Python .venv presente: ' + str(EXE.is_file()))
    report('Pip em .venv: ' + str(check_pip()))
    if EXE.is_file():
        shell([str(EXE), '--version'], 'Versao do ambiente', capture=False, timeout=15)
        shell([str(EXE), '-m', 'pip', '--version'], 'Versao do pip', capture=False, timeout=15)
    report('Bibliotecas: ' + str(REQUIREMENTS.read_text(encoding='utf-8')))


def main() -> int:
    global LOG
    if len(sys.argv) != 2 or sys.argv[1] not in ('install', 'build', 'diagnose'):
        print('Uso: python preparar_ambiente.py install|build|diagnose')
        return 2
    action = sys.argv[1]
    try:
        LOG = LOGFILE.open('a', encoding='utf-8')
        report('\n' + '=' * 68)
        report('GravadorTelaWin 2.7-rc1 | ' + datetime.datetime.now().isoformat(timespec='seconds'))
        report('Acao: ' + action)
        report('Diretorio: ' + str(ROOT))
        base, info = select_python()
        if action == 'diagnose':
            diagnose(base, info)
        else:
            prepare(base, info, build=(action == 'build'))
            if action == 'install':
                launch_app()
            else:
                build_exe()
        report('RESULTADO: OK')
        return 0
    except SetupError as exc:
        report('\nERRO: ' + str(exc))
        report('Envie o arquivo diagnostico_instalacao.log para identificar a causa.')
        report('RESULTADO: FALHA')
        return 1
    except Exception as exc:
        report('\nERRO INESPERADO: ' + repr(exc))
        report('RESULTADO: FALHA')
        return 1
    finally:
        if LOG:
            LOG.close()


if __name__ == '__main__':
    sys.exit(main())
