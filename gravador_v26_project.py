# -*- coding: utf-8 -*-
"""Projetos de anotação editáveis, locais e sem pixels da tela.

Formato .gtwproj: JSON com versão, dimensões e objetos de anotação.
O carregamento também reconhece o JSON gerado pela exportação v2.5.
Dados não confiáveis são validados antes de alterar a interface.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from gravador_v25_export import validate_records

PROJECT_FORMAT = 'gravador-tela-win/anotacoes'
PROJECT_VERSION = 1
MAX_PROJECT_BYTES = 8 * 1024 * 1024


def _dimensions(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 64 <= value <= 8192:
        raise ValueError(f'{label} inválida no projeto (64 a 8192 pixels).')
    return value


def project_document(items: list[dict], width: int, height: int) -> dict:
    w = _dimensions(width, 'Largura')
    h = _dimensions(height, 'Altura')
    return {
        'formato': PROJECT_FORMAT,
        'versao': PROJECT_VERSION,
        'largura': w,
        'altura': h,
        'coordenadas': 'relativas_a_area_gravada',
        'anotacoes': validate_records(items, w, h),
    }


def _parse_document(value: object, width: int, height: int) -> list[dict]:
    if not isinstance(value, dict):
        raise ValueError('O projeto deve conter um objeto JSON.')
    file_w = _dimensions(value.get('largura'), 'Largura')
    file_h = _dimensions(value.get('altura'), 'Altura')
    if (file_w, file_h) != (width, height):
        raise ValueError(
            f'Este projeto foi criado para {file_w} × {file_h} pixels. '
            f'A gravação atual usa {width} × {height}. '
            'Selecione uma área com as mesmas dimensões para evitar deslocamentos.'
        )
    version = value.get('versao')
    if type(version) is not int or version != PROJECT_VERSION:
        raise ValueError('Versão de projeto não suportada.')
    fmt = value.get('formato')
    legacy = fmt is None and value.get('sistema_coordenadas') == 'local da area capturada'
    if fmt != PROJECT_FORMAT and not legacy:
        raise ValueError('Formato de projeto não reconhecido.')
    rows = value.get('anotacoes')
    if not isinstance(rows, list):
        raise ValueError('A lista de anotações é inválida.')
    records = validate_records(rows, file_w, file_h)
    for item in records:
        n = len(item['pontos'])
        if item['tipo'] == 'Texto' and n != 2:
            raise ValueError('Um texto precisa ter duas coordenadas.')
        if item['tipo'] == 'Retângulo' and n != 4:
            raise ValueError('Retângulo precisa ter quatro coordenadas.')
        if item['tipo'] in ('Caneta', 'Seta') and n < 4:
            raise ValueError('Linha precisa ter pelo menos dois pontos.')
    return records


def save_project(destination: str | Path, items: list[dict], width: int, height: int) -> Path:
    path = Path(destination)
    if path.suffix.lower() != '.gtwproj':
        raise ValueError('O arquivo do projeto deve terminar em .gtwproj.')
    payload = json.dumps(project_document(items, width, height), ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    if len(payload) > MAX_PROJECT_BYTES:
        raise ValueError('Projeto excede o limite de 8 MB.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    try:
        with temporary.open('wb') as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_project(source: str | Path, width: int, height: int) -> list[dict]:
    """Retorna objetos validados, sem alterar o Canvas ou executar código do arquivo."""
    expected_w = _dimensions(width, 'Largura')
    expected_h = _dimensions(height, 'Altura')
    path = Path(source)
    if path.suffix.lower() not in ('.gtwproj', '.json'):
        raise ValueError('Selecione um projeto .gtwproj ou JSON da v2.5.')
    size = path.stat().st_size
    if size > MAX_PROJECT_BYTES:
        raise ValueError('Projeto excede o limite de 8 MB.')
    if size == 0:
        raise ValueError('Projeto vazio.')
    with path.open('rb') as file:
        contents = file.read(MAX_PROJECT_BYTES + 1)
    if len(contents) > MAX_PROJECT_BYTES:
        raise ValueError('Projeto excede o limite de 8 MB.')
    try:
        value = json.loads(contents.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Arquivo de projeto inválido ou corrompido.') from exc
    return _parse_document(value, expected_w, expected_h)
