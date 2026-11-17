"""Servicios con precio, utilidad y venta sin movimientos de inventario."""

import os
import sqlite3
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from app.database.schema import create_database
from app.services.product_service import ProductService
from app.services.sale_service import SaleService
from app.services.sale_history_service import SaleHistoryService
from app.services.purchase_service import PurchaseService
from app.services.quick_stock_service import QuickStockService
from app.services.dashboard_service import DashboardService
from app.ui.product_dialog import ProductDialog
from app.ui.sale_window import SaleWindow


class MemoryDB:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
    def cursor(self):
        return self.connection.cursor()
    def commit(self):
        self.connection.commit()
    def rollback(self):
        self.connection.rollback()
    def close(self):
        self.connection.close()


class ServiceCatalogAndSaleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = MemoryDB()
        create_database(self.db)
        self.catalog = ProductService(self.db)
        self.category = self.catalog.get_categories()[0]["id"]
        self.product_id = self.catalog.create_product({
            "nombre": "Lana para proyecto", "marca": "Echando",
            "categoria_id": self.category, "unidad": "pieza", "costo": 30,
            "precio": 80, "existencia": 4, "stock_minimo": 2,
        })
        self.service_id = self.catalog.create_product({
            "nombre": "Clase de crochet", "tipo": "SERVICIO",
            "subtipo_servicio": "Clases", "unidad": "pieza",
            "precio": 200, "costo": 50, "existencia": 999999,
            "stock_minimo": 100,
        })
        self.service = self.catalog.get_product(self.service_id)

    def tearDown(self):
        self.db.close()
        self.app.processEvents()

    def test_services_have_no_stock_even_if_supplied_externally(self):
        self.assertEqual(self.service["tipo"], "SERVICIO")
        self.assertEqual(self.service["subtipo_servicio"], "Clases")
        self.assertEqual(self.service["existencia"], 0)
        self.assertEqual(self.service["stock_minimo"], 0)
        listed = next(p for p in self.catalog.list_products() if p["id"] == self.service_id)
        self.assertEqual(listed["categoria"], "Clases")
        self.assertEqual(self.catalog.product_status(listed), "SERVICIO")

    def test_inventory_value_and_shortages_exclude_service(self):
        self.assertEqual(DashboardService(self.db).get_inventory_value(), 120)
        self.assertEqual(self.catalog.get_inventory_report()["valor_total_costo"], 120)
        self.assertEqual(self.catalog.get_inventory_report()["valor_total_venta"], 320)
        self.assertEqual(self.catalog.get_inventory_report()["total_productos"], 1)
        self.assertNotIn(self.service_id, [
            row["id"] for row in self.catalog.list_low_stock_products()
        ])
        self.assertEqual(DashboardService(self.db).get_low_stock_count(), 0)

    def test_mixed_sale_multiple_classes_and_physical_units(self):
        sale = SaleService(self.db).create_sale(
            [{"producto_id": self.service_id, "cantidad": 3, "precio_unitario": 200},
             {"producto_id": self.product_id, "cantidad": 2, "precio_unitario": 80}],
            payment_method="Efectivo",
        )
        self.assertEqual(sale["total"], 760)
        self.assertAlmostEqual(
            DashboardService(self.db).get_profit_for_period(sale["fecha"]),
            550.0,
        )
        summary = DashboardService(self.db).get_analytics_annual(
            int(sale["fecha"][:4])
        )
        self.assertEqual(summary["producto_mas_rentable"]["categoria"], "Clases")
        product = self.catalog.get_product(self.product_id)
        service = self.catalog.get_product(self.service_id)
        self.assertEqual(product["existencia"], 2)
        self.assertEqual(service["existencia"], 0)
        sales = self.db.cursor().execute(
            """SELECT producto_id, cantidad, costo_unitario FROM detalle_venta
               WHERE venta_id = ? ORDER BY id""", (sale["id"],)
        ).fetchall()
        self.assertEqual([(x["producto_id"], x["cantidad"], x["costo_unitario"])
                          for x in sales], [(self.service_id, 3, 50), (self.product_id, 2, 30)])
        movements = self.db.cursor().execute(
            "SELECT producto_id, tipo FROM movimientos_inventario ORDER BY id"
        ).fetchall()
        self.assertEqual([(x["producto_id"], x["tipo"]) for x in movements],
                         [(self.product_id, "VENTA")])

    def test_repeat_service_sales_with_zero_stock(self):
        sale_service = SaleService(self.db)
        for _ in range(2):
            sale_service.create_sale(
                [{"producto_id": self.service_id, "cantidad": 4,
                  "precio_unitario": 200}],
                payment_method="Efectivo",
            )
        self.assertEqual(self.catalog.get_product(self.service_id)["existencia"], 0)
        self.assertEqual(self.db.cursor().execute(
            "SELECT COUNT(*) FROM movimientos_inventario").fetchone()[0], 0)

    def test_cannot_receive_service_as_purchase_or_quick_stock(self):
        self.db.cursor().execute("INSERT INTO proveedores (nombre) VALUES ('P1')")
        self.db.commit()
        supplier_id = self.db.cursor().execute(
            "SELECT id FROM proveedores WHERE nombre = 'P1'").fetchone()[0]
        purchase = PurchaseService(self.db)
        self.assertFalse(any(p["id"] == self.service_id for p in
                             purchase.search_products("Clase")))
        with self.assertRaisesRegex(ValueError, "servicio"):
            purchase.create_purchase(
                [{"producto_id": self.service_id, "cantidad": 1,
                  "costo_unitario": 50}], supplier_id=supplier_id
            )
        with self.assertRaises(ValueError):
            QuickStockService(self.db).add_scan(self.service["codigo"])
        self.assertEqual(self.catalog.get_product(self.service_id)["existencia"], 0)

    def test_convert_legacy_class_preserves_history_and_removes_fake_value(self):
        old_id = self.catalog.create_product({
            "nombre": "Clase antigua", "categoria_id": self.category,
            "unidad": "pieza", "costo": 120, "precio": 200,
            "existencia": 999999,
        })
        sale = SaleService(self.db).create_sale(
            [{"producto_id": old_id, "cantidad": 1, "precio_unitario": 200}],
            payment_method="Efectivo",
        )
        before = self.catalog.get_product(old_id)
        self.assertEqual(before["existencia"], 999998)
        self.assertGreater(DashboardService(self.db).get_inventory_value(), 1000000)

        self.catalog.update_product(old_id, {
            **before, "tipo": "SERVICIO", "subtipo_servicio": "Clases",
            "costo": 50, "precio": 200
        })
        after = self.catalog.get_product(old_id)
        self.assertEqual(after["id"], old_id)
        self.assertEqual(after["codigo"], before["codigo"])
        self.assertEqual(after["existencia"], 0)
        self.assertEqual(DashboardService(self.db).get_inventory_value(), 120)
        self.assertEqual(self.db.cursor().execute(
            "SELECT COUNT(*) FROM detalle_venta WHERE venta_id=?",
            (sale["id"],)
        ).fetchone()[0], 1)
        audit = self.db.cursor().execute(
            "SELECT tipo, existencia_anterior, existencia_nueva "
            "FROM movimientos_inventario WHERE producto_id = ? "
            "ORDER BY id DESC LIMIT 1", (old_id,)
        ).fetchone()
        self.assertEqual(tuple(audit),
                         ("RECLASIFICACION_SERVICIO", 999998, 0))
        SaleService(self.db).create_sale(
            [{"producto_id": old_id, "cantidad": 2, "precio_unitario": 200}],
            payment_method="Efectivo",
        )
        self.assertEqual(self.catalog.get_product(old_id)["existencia"], 0)

    def test_service_duplicate_rules_and_invalid_profit(self):
        with self.assertRaises(ValueError):
            self.catalog.create_product({
                "nombre": "Clase de crochet", "tipo": "SERVICIO",
                "subtipo_servicio": "Clases", "precio": 210, "costo": 20,
                "unidad": "pieza",
            })
        other = self.catalog.create_product({
            "nombre": "Clase de crochet", "tipo": "SERVICIO",
            "subtipo_servicio": "Talleres", "precio": 200, "costo": 50,
            "unidad": "pieza",
        })
        self.assertNotEqual(other, self.service_id)
        with self.assertRaisesRegex(ValueError, "utilidad"):
            self.catalog.create_product({
                "nombre": "Servicio inválido", "tipo": "SERVICIO",
                "subtipo_servicio": "Costura", "precio": 90, "costo": 120,
            })

    def test_product_form_service_fields_and_profit_are_editable(self):
        dialog = ProductDialog(self.catalog)
        dialog.show()
        self.app.processEvents()
        try:
            dialog.tipo.setCurrentIndex(dialog.tipo.findData("SERVICIO"))
            dialog.subtipo_servicio.setCurrentText("Costura")
            self.assertFalse(dialog.existencia.isVisible())
            self.assertFalse(dialog.stock_minimo.isVisible())
            self.assertTrue(dialog.utilidad_servicio.isVisible())
            dialog.nombre.setText("Ajuste de costura")
            dialog.precio.setValue(250)
            dialog.utilidad_servicio.setValue(180)
            dialog._save()
            self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
            entry = max(self.catalog.list_products(), key=lambda p: p["id"])
            self.assertEqual(entry["tipo"], "SERVICIO")
            self.assertEqual(entry["subtipo_servicio"], "Costura")
            self.assertEqual(entry["costo"], 70)
            self.assertEqual(entry["precio"], 250)
            self.assertEqual(entry["existencia"], 0)
        finally:
            dialog.close()

    def test_sale_window_adds_service_without_stock_warning(self):
        window = SaleWindow(self.db)
        window.show()
        self.app.processEvents()
        try:
            source = window.service.find_product(self.service["codigo"])
            self.assertEqual(source["tipo"], "SERVICIO")
            with patch.object(QMessageBox, "warning") as warn:
                window._agregar_producto(source)
                window._agregar_producto(source)
                warn.assert_not_called()
            self.assertEqual(len(window.items), 2)
            self.assertTrue(window._establecer_cantidad(0, 300))
            self.assertEqual(window.items[0]["cantidad"], 300)
        finally:
            window.close()

    def test_cancel_mixed_sale_restores_only_physical_items(self):
        sale = SaleService(self.db).create_sale(
            [{"producto_id": self.product_id, "cantidad": 1,
              "precio_unitario": 80},
             {"producto_id": self.service_id, "cantidad": 2,
              "precio_unitario": 200}],
            payment_method="Efectivo",
        )
        result = SaleHistoryService(self.db).cancel_sale(sale["id"])
        self.assertEqual(result["productos_devueltos"], 1)
        self.assertEqual(self.catalog.get_product(self.product_id)["existencia"], 4)
        self.assertEqual(self.catalog.get_product(self.service_id)["existencia"], 0)
        service_movements = self.db.cursor().execute(
            "SELECT COUNT(*) FROM movimientos_inventario WHERE producto_id=?",
            (self.service_id,),
        ).fetchone()[0]
        self.assertEqual(service_movements, 0)

    def test_editing_service_keeps_profit_when_field_is_focused(self):
        dialog = ProductDialog(self.catalog, self.catalog.get_product(self.service_id))
        dialog.show()
        self.app.processEvents()
        try:
            self.assertEqual(dialog.tipo.currentData(), "SERVICIO")
            self.assertEqual(dialog.precio.value(), 200)
            self.assertEqual(dialog.utilidad_servicio.value(), 150)
            dialog.utilidad_servicio.setFocus()
            self.app.processEvents()
            self.assertEqual(dialog.utilidad_servicio.value(), 150)
        finally:
            dialog.close()

    def test_new_service_does_not_save_unit_color_or_supplier(self):
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO proveedores (nombre) VALUES ('Proveedor externo')")
        supplier_id = cursor.lastrowid
        self.db.commit()
        new_id = self.catalog.create_product({
            "nombre": "Arreglo de costura", "tipo": "SERVICIO",
            "subtipo_servicio": "Costura", "marca": "Echando Chal",
            "unidad": "pieza", "color": "Azul", "proveedor_id": supplier_id,
            "costo": 20, "precio": 100,
        })
        saved = self.catalog.get_product(new_id)
        self.assertEqual(saved["tipo"], "SERVICIO")
        self.assertEqual(saved["unidad"], "")
        self.assertIsNone(saved["color"])
        self.assertIsNone(saved["proveedor_id"])
        self.assertEqual(saved["precio"] - saved["costo"], 80)

    def test_edit_service_clears_old_unit_color_and_supplier(self):
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO proveedores (nombre) VALUES ('Proveedor previo')")
        supplier_id = cursor.lastrowid
        cursor.execute(
            """UPDATE productos
               SET unidad = 'pieza', color = 'Rojo', proveedor_id = ?
               WHERE id = ?""",
            (supplier_id, self.service_id),
        )
        self.db.commit()
        original = self.catalog.get_product(self.service_id)
        self.assertEqual(original["unidad"], "pieza")
        self.catalog.update_product(self.service_id, {
            **original,
            "unidad": "hora",
            "color": "Negro",
            "proveedor_id": supplier_id,
        })
        refreshed = self.catalog.get_product(self.service_id)
        self.assertEqual(refreshed["unidad"], "")
        self.assertIsNone(refreshed["color"])
        self.assertIsNone(refreshed["proveedor_id"])
        self.assertEqual(refreshed["precio"], 200)

    def test_conversion_to_service_drops_unit_color_supplier(self):
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO proveedores (nombre) VALUES ('Tienda externa')")
        supplier_id = cursor.lastrowid
        self.db.commit()
        legacy_id = self.catalog.create_product({
            "nombre": "Clase con existencias", "categoria_id": self.category,
            "unidad": "pieza", "color": "Verde",
            "proveedor_id": supplier_id,
            "costo": 40, "precio": 120, "existencia": 999999,
        })
        legacy = self.catalog.get_product(legacy_id)
        self.catalog.update_product(legacy_id, {
            **legacy, "tipo": "SERVICIO", "subtipo_servicio": "Clases",
            "costo": 20, "precio": 120,
        })
        saved = self.catalog.get_product(legacy_id)
        self.assertEqual(saved["unidad"], "")
        self.assertIsNone(saved["color"])
        self.assertIsNone(saved["proveedor_id"])
        self.assertEqual(saved["existencia"], 0)
        self.assertEqual(saved["codigo"], legacy["codigo"])

    def test_service_duplicate_ignores_unit_color_and_supplier(self):
        with self.assertRaisesRegex(ValueError, "producto duplicado"):
            self.catalog.create_product({
                "nombre": "  clase de crochet  ", "marca": "",
                "tipo": "SERVICIO", "subtipo_servicio": "Clases",
                "unidad": "hora", "color": "Naranja",
                "proveedor_id": 9999, "precio": 200, "costo": 50,
            })

    def test_service_dialog_hides_nonapplicable_fields_and_saves_blank(self):
        dialog = ProductDialog(self.catalog)
        dialog.show()
        self.app.processEvents()
        try:
            self.assertTrue(dialog.color.isVisible())
            self.assertTrue(dialog.unit_container.isVisible())
            self.assertTrue(dialog.proveedor.isVisible())
            dialog.tipo.setCurrentIndex(dialog.tipo.findData("SERVICIO"))
            self.app.processEvents()
            for field in (
                dialog.color, dialog.unit_container, dialog.unidad,
                dialog.proveedor,
            ):
                with self.subTest(field=field):
                    self.assertFalse(field.isVisible())
            self.assertFalse(dialog.form.labelForField(dialog.color).isVisible())
            self.assertFalse(dialog.form.labelForField(dialog.unit_container).isVisible())
            self.assertFalse(dialog.form.labelForField(dialog.proveedor).isVisible())
            dialog.nombre.setText("Taller introductorio")
            dialog.subtipo_servicio.setCurrentText("Talleres")
            dialog.precio.setValue(180)
            dialog.utilidad_servicio.setValue(150)
            dialog._save()
            self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
            saved = next(
                p for p in self.catalog.list_products()
                if p["nombre"] == "Taller introductorio"
            )
            self.assertEqual(saved["unidad"], "")
            self.assertEqual(saved["color"], "")
            self.assertEqual(saved["proveedor"], "")
        finally:
            dialog.close()

    def test_service_type_stays_after_schema_second_start(self):
        create_database(self.db)
        self.assertEqual(self.catalog.get_product(self.service_id)["tipo"], "SERVICIO")
        self.assertEqual(self.catalog.get_product(self.service_id)["existencia"], 0)


if __name__ == "__main__":
    unittest.main()
