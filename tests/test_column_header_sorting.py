"""Ordenamiento: doble clic, alternancia, valores y asociaciones de filas."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget, QTreeWidget, QTreeWidgetItem

from app.ui.sale_history_window import SortableSaleItem
from app.ui.widgets.column_sort import (
    SortableItem, install_table_sort, restore_table_sort, next_sort,
    sort_records, sort_value,
)


class ColumnSortingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_numeric_money_and_quantities_are_sorted_as_numbers(self):
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Producto", "Costo"])
        install_table_sort(table)
        rows = [("P-10", "$ 1,200.00", 10), ("P-2", "$ 90.00", 2),
                ("P-3", "$ 8.50", 3)]
        for name, value, identity in rows:
            row = table.rowCount()
            table.insertRow(row)
            first = SortableItem(name)
            first.setData(Qt.ItemDataRole.UserRole, identity)
            table.setItem(row, 0, first)
            table.setItem(row, 1, SortableItem(value, numeric=True))

        def values():
            return [table.item(row, 1).text() for row in range(table.rowCount())]

        def ids():
            return [table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    for row in range(table.rowCount())]

        next_sort(table, 1)
        restore_table_sort(table)
        self.assertEqual(values(), ["$ 8.50", "$ 90.00", "$ 1,200.00"])
        self.assertEqual(ids(), [3, 2, 10])
        next_sort(table, 1)
        restore_table_sort(table)
        self.assertEqual(values(), ["$ 1,200.00", "$ 90.00", "$ 8.50"])
        self.assertEqual(ids(), [10, 2, 3])
        next_sort(table, 0)
        restore_table_sort(table)
        self.assertEqual(
            [table.item(row, 0).text() for row in range(table.rowCount())],
            ["P-10", "P-2", "P-3"],
        )
        table.close()

    def test_sorting_model_preserves_item_identity_for_editors(self):
        first = {"producto_id": 1, "nombre": "Azul", "cantidad": 12, "costo": 40}
        second = {"producto_id": 2, "nombre": "Rojo", "cantidad": 3, "costo": 150}
        third = {"producto_id": 3, "nombre": "Verde", "cantidad": 25, "costo": 20}
        products = [first, second, third]
        fields = (
            (lambda p: p["nombre"], False),
            (lambda p: p["cantidad"], True),
            (lambda p: p["cantidad"] * p["costo"], True),
        )
        sort_records(products, 1, True, fields)
        self.assertEqual([p["producto_id"] for p in products], [2, 1, 3])
        self.assertIs(products[0], second)
        sort_records(products, 2, False, fields)
        self.assertEqual([p["producto_id"] for p in products], [3, 1, 2])
        products[0]["cantidad"] = 20
        self.assertEqual(third["cantidad"], 20)
        self.assertEqual(second["cantidad"], 3)

    def test_sales_history_money_sort_and_group_integrity(self):
        tree = QTreeWidget()
        tree.setColumnCount(9)
        for folio, amount in (("A", 1200), ("B", 90), ("C", 8)):
            values = [folio, "2026-11-02", "", "", f"$ {amount:,.2f}",
                      "$ 0.00", f"$ {amount:,.2f}", "$ 0.00", "ACTIVA"]
            tree.addTopLevelItem(SortableSaleItem(values))
        tree._heading_sort = (6, True)
        tree.sortItems(6, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            [tree.topLevelItem(i).text(0) for i in range(3)],
            ["C", "B", "A"],
        )
        tree._heading_sort = (6, False)
        tree.sortItems(6, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            [tree.topLevelItem(i).text(0) for i in range(3)],
            ["A", "B", "C"],
        )
        tree.close()

    def test_grouped_sales_sort_only_within_month(self):
        tree = QTreeWidget()
        tree.setColumnCount(9)
        year = QTreeWidgetItem(["2026"])
        tree.addTopLevelItem(year)
        jan = QTreeWidgetItem(["Enero"])
        feb = QTreeWidgetItem(["Febrero"])
        year.addChild(jan)
        year.addChild(feb)
        for parent, folio, amount in (
            (jan, "JAN-A", 200), (jan, "JAN-B", 20),
            (feb, "FEB-A", 700), (feb, "FEB-B", 50),
        ):
            parent.addChild(SortableSaleItem([
                folio, "", "", "", f"$ {amount:.2f}",
                "$ 0.00", f"$ {amount:.2f}", "$ 0.00", "ACTIVA",
            ]))
        tree._heading_sort = (6, True)
        jan.sortChildren(6, Qt.SortOrder.AscendingOrder)
        feb.sortChildren(6, Qt.SortOrder.AscendingOrder)
        self.assertEqual(jan.child(0).text(0), "JAN-B")
        self.assertEqual(feb.child(0).text(0), "FEB-B")
        self.assertEqual(tree.topLevelItemCount(), 1)
        self.assertEqual(year.childCount(), 2)
        tree.close()

    def test_dates_and_zero_values(self):
        self.assertLess(sort_value("$ 9.00", True), sort_value("$ 100.00", True))
        self.assertLess(sort_value("2026-01-01"), sort_value("2026-11-01"))
        self.assertLess(sort_value("0", True), sort_value("1", True))

    def test_sort_indicator_alternates_and_resets_for_new_column(self):
        table = QTableWidget()
        install_table_sort(table)
        self.assertEqual(next_sort(table, 0), Qt.SortOrder.AscendingOrder)
        self.assertEqual(next_sort(table, 0), Qt.SortOrder.DescendingOrder)
        self.assertEqual(next_sort(table, 1), Qt.SortOrder.AscendingOrder)
        table.close()


if __name__ == "__main__":
    unittest.main()
