"""Ordenamiento por doble clic de encabezados, con tipos numéricos reales.

No modifica la BD. El orden se restaura al volver a cargar una tabla.
"""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

NUMBER_PATTERN = re.compile(r"[^0-9.+-]")


def sort_value(value, numeric=False):
    text = str(value or "").strip()
    if numeric:
        cleaned = NUMBER_PATTERN.sub("", text)
        try:
            return (0, float(cleaned))
        except ValueError:
            return (1, text.casefold())
    return text.casefold()


class SortableItem(QTableWidgetItem):
    """Compara importes, cantidades y días por su valor, no por sus dígitos."""

    def __init__(self, value, numeric=False):
        super().__init__(str(value))
        self.numeric_sort = numeric

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            return sort_value(self.text(), self.numeric_sort) < sort_value(
                other.text(), self.numeric_sort
            )
        return super().__lt__(other)


def next_sort(table, column):
    """Alterna ascendente / descendente; columna nueva comienza ascendente."""
    previous = getattr(table, "_heading_sort", None)
    ascending = not (previous is not None and previous == (column, True))
    table._heading_sort = (column, ascending)
    order = (Qt.SortOrder.AscendingOrder if ascending
             else Qt.SortOrder.DescendingOrder)
    header = table.horizontalHeader() if hasattr(table, "horizontalHeader") else table.header()
    header.setSortIndicatorShown(True)
    header.setSortIndicator(column, order)
    return order


def install_table_sort(table):
    """Ordena filas enteras únicamente ante doble clic, no uno sencillo."""
    table.setSortingEnabled(False)
    table.horizontalHeader().sectionDoubleClicked.connect(
        lambda column: (next_sort(table, column), restore_table_sort(table))
    )


def restore_table_sort(table):
    state = getattr(table, "_heading_sort", None)
    if state is not None:
        column, ascending = state
        table.sortItems(
            column, Qt.SortOrder.AscendingOrder if ascending
            else Qt.SortOrder.DescendingOrder
        )


def sort_records(records, column, ascending, getters):
    """Ordena modelos subyacentes sin desvincular filas de sus registros."""
    selector, numeric = getters[column]
    records.sort(
        key=lambda record: sort_value(selector(record), numeric),
        reverse=not ascending,
    )
