# -*- coding: utf-8 -*-
"""Historico de anotacoes do Estudio 2.4, independente de Tk/Windows.

Cada gesto vira uma acao reversivel. A limpeza tambem pode ser desfeita.
Nao grava coordenadas de tela nem acessa recursos externos.
"""
from __future__ import annotations

from dataclasses import dataclass

ANNOTATION_COLORS = {
    'Amarelo': '#ffed65',
    'Vermelho': '#ff5b6e',
    'Verde': '#6bf6aa',
    'Azul': '#43d6ff',
    'Branco': '#ffffff',
}
STROKE_WIDTHS = (2, 4, 7)


@dataclass(frozen=True)
class HistoryChange:
    show: tuple[int, ...] = ()
    hide: tuple[int, ...] = ()
    delete: tuple[int, ...] = ()


@dataclass(frozen=True)
class _Action:
    kind: str
    items: tuple[int, ...]


class AnnotationHistory:
    """Modelo linear de undo/redo, sem reinserir objetos no Canvas.

    Canvas.delete e executado somente em itens pertencentes ao ramo de redo
    descartado, nunca sobre os itens ainda exibidos.
    """
    def __init__(self, max_actions: int = 250):
        if max_actions < 1:
            raise ValueError('O historico precisa armazenar ao menos uma acao')
        self.max_actions = max_actions
        self._actions: list[_Action] = []
        self._cursor = 0
        self._visible: set[int] = set()

    @property
    def visible(self) -> frozenset[int]:
        return frozenset(self._visible)

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._actions)

    def _branch(self) -> tuple[int, ...]:
        discarded = self._actions[self._cursor:]
        self._actions = self._actions[:self._cursor]
        orphaned = {item for action in discarded if action.kind == 'add'
                    for item in action.items}
        retained = {item for action in self._actions for item in action.items}
        return tuple(sorted(orphaned - retained - self._visible))

    def _append(self, action: _Action) -> tuple[int, ...]:
        garbage = self._branch()
        self._actions.append(action)
        self._cursor += 1
        if len(self._actions) > self.max_actions:
            overflow = len(self._actions) - self.max_actions
            del self._actions[:overflow]
            self._cursor -= overflow
        return garbage

    def record(self, item_id: int) -> HistoryChange:
        if item_id < 0:
            raise ValueError('ID de Canvas invalido')
        garbage = self._append(_Action('add', (item_id,)))
        self._visible.add(item_id)
        return HistoryChange(delete=garbage)

    def clear(self) -> HistoryChange:
        if not self._visible:
            return HistoryChange()
        items = tuple(sorted(self._visible))
        garbage = self._append(_Action('clear', items))
        self._visible.clear()
        return HistoryChange(hide=items, delete=garbage)

    def undo(self) -> HistoryChange:
        if not self.can_undo:
            return HistoryChange()
        self._cursor -= 1
        action = self._actions[self._cursor]
        if action.kind == 'add':
            self._visible.difference_update(action.items)
            return HistoryChange(hide=action.items)
        self._visible.update(action.items)
        return HistoryChange(show=action.items)

    def redo(self) -> HistoryChange:
        if not self.can_redo:
            return HistoryChange()
        action = self._actions[self._cursor]
        self._cursor += 1
        if action.kind == 'add':
            self._visible.update(action.items)
            return HistoryChange(show=action.items)
        self._visible.difference_update(action.items)
        return HistoryChange(hide=action.items)
