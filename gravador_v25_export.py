# -*- coding: utf-8 -*-
"""Exportação offline das anotações em PNG transparente e JSON editável.

Não captura pixels do desktop nem acessa a rede. Somente objetos fornecidos
pelo usuário (linhas, retângulos, setas, texto) entram no arquivo.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SCHEMA_VERSION = 1
MAX_DIMENSION = 8192
MAX_ITEMS = 5000
MAX_COORDINATES = 20000


def validate_records(items: list[dict], width: int, height: int) -> list[dict]:
    if not (64 <= width <= MAX_DIMENSION and 64 <= height <= MAX_DIMENSION):
        raise ValueError('Dimensões fora do limite de exportação (64 a 8192 px).')
    if len(items) > MAX_ITEMS:
        raise ValueError('Limite de 5000 anotações excedido.')
    valid = []
    for item in items:
        kind = item.get('tipo')
        if kind not in ('Caneta', 'Seta', 'Retângulo', 'Texto'):
            raise ValueError('Tipo de anotação inválido.')
        coords = item.get('pontos')
        if not isinstance(coords, (tuple, list)) or not 2 <= len(coords) <= MAX_COORDINATES or len(coords) % 2:
            raise ValueError('Coordenadas inválidas.')
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in coords):
            raise ValueError('Coordenadas não finitas.')
        color = item.get('cor', '')
        if not isinstance(color, str) or len(color) != 7 or color[0] != '#' or any(c not in '0123456789abcdefABCDEF' for c in color[1:]):
            raise ValueError('Cor de anotação inválida.')
        thickness = int(item.get('espessura', 4))
        if not 1 <= thickness <= 40:
            raise ValueError('Espessura inválida.')
        label = item.get('texto', '')
        if not isinstance(label, str) or len(label) > 240:
            raise ValueError('Texto inválido (máximo 240 caracteres).')
        font_size = int(item.get('fonte_px', 22))
        if not 8 <= font_size <= 96:
            raise ValueError('Tamanho de fonte inválido.')
        valid.append({'tipo': kind, 'pontos': list(coords), 'cor': color.lower(),
                      'espessura': thickness, 'texto': label, 'fonte_px': font_size})
    return valid


def _font(size: int):
    for file in ('C:/Windows/Fonts/segoeuib.ttf', 'C:/Windows/Fonts/arialbd.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(file, size)
        except OSError:
            pass
    return ImageFont.load_default()


def render_png(items: list[dict], width: int, height: int) -> Image.Image:
    records = validate_records(items, width, height)
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for item in records:
        kind = item['tipo']; pts = item['pontos']; color = item['cor']; weight = item['espessura']
        xy = list(zip(pts[::2], pts[1::2]))
        if kind in ('Caneta', 'Seta'):
            if len(xy) == 1:
                x, y = xy[0]; draw.ellipse((x-weight/2, y-weight/2, x+weight/2, y+weight/2), fill=color)
            else:
                draw.line(xy, fill=color, width=weight, joint='curve')
            if kind == 'Seta' and len(xy) >= 2:
                x0,y0 = xy[-2]; x1,y1 = xy[-1]
                angle = math.atan2(y1-y0, x1-x0)
                length = 11 + weight * 3
                wing = length * .55
                left = (x1-length*math.cos(angle)+wing*math.sin(angle), y1-length*math.sin(angle)-wing*math.cos(angle))
                right = (x1-length*math.cos(angle)-wing*math.sin(angle), y1-length*math.sin(angle)+wing*math.cos(angle))
                draw.polygon(((x1,y1), left, right), fill=color)
        elif kind == 'Retângulo':
            if len(xy) >= 2:
                x0,y0=xy[0];x1,y1=xy[-1]
                draw.rectangle((min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1)), outline=color, width=weight)
        else:
            if item['texto']:
                draw.text(xy[0], item['texto'], fill=color, font=_font(item['fonte_px']), stroke_width=0)
    return img


def export_annotations(destination: Path | str, items: list[dict], width: int, height: int) -> tuple[Path, Path]:
    """Escreve PNG RGBA e JSON lado a lado, com arquivos temporários locais."""
    png = Path(destination)
    if png.suffix.lower() != '.png':
        png = png.with_suffix('.png')
    js = png.with_suffix('.json')
    records = validate_records(items, width, height)
    picture = render_png(records, width, height)
    metadata = {'versao': SCHEMA_VERSION, 'largura': width, 'altura': height,
                'sistema_coordenadas': 'local da area capturada', 'anotacoes': records}
    png.parent.mkdir(parents=True, exist_ok=True)
    tmp_png = png.with_name(png.name + '.tmp')
    tmp_json = js.with_name(js.name + '.tmp')
    try:
        with tmp_png.open('wb') as f:
            picture.save(f, format='PNG')
        tmp_json.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp_png, png)
        os.replace(tmp_json, js)
    finally:
        tmp_png.unlink(missing_ok=True)
        tmp_json.unlink(missing_ok=True)
    return png, js
