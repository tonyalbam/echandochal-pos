"""Prueba de migración real desde el esquema de producción anterior (rama app)."""

import sqlite3
from pathlib import Path

from app.database.schema import create_database


class LegacyConnection:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


def test_schema_upgrade_preserves_original_products_sales_purchases(tmp_path):
    db_path = tmp_path / "echandochal.db"
    old_sql = Path("tests/fixtures/legacy_app_schema.sql").read_text(
        encoding="utf-8"
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(old_sql)
        conn.execute(
            "INSERT INTO categorias (id,nombre) VALUES (70,'Lana de prueba')"
        )
        conn.execute(
            "INSERT INTO proveedores (id,nombre) VALUES (30,'Proveedor anterior')"
        )
        conn.execute(
            """INSERT INTO productos
               (id,codigo,nombre,categoria_id,marca,color,unidad,costo,precio,
                existencia,stock_minimo,proveedor_id)
               VALUES (81,'ECH0000081','Hilo legado',70,'Marca A','Azul',
                       'pieza',15,30,11,3,30)"""
        )
        conn.execute(
            """INSERT INTO ventas
               (id,folio,fecha,hora,subtotal,descuento,total,metodo_pago)
               VALUES (20,'V-ANT-1','2026-10-01','12:00',60,0,60,'Efectivo')"""
        )
        conn.execute(
            """INSERT INTO detalle_venta
               (venta_id,producto_id,cantidad,precio_unitario,costo_unitario,subtotal,
                metodo_pago)
               VALUES (20,81,2,30,15,60,'Efectivo')"""
        )
        conn.execute(
            """INSERT INTO compras
               (id,folio,proveedor_id,fecha,subtotal,total)
               VALUES (15,'C-ANT-1',30,'2026-09-30',150,150)"""
        )
        conn.execute(
            """INSERT INTO detalle_compra
               (compra_id,producto_id,cantidad,costo_unitario,subtotal)
               VALUES (15,81,10,15,150)"""
        )
        conn.commit()

        before = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("productos", "ventas", "detalle_venta", "compras", "detalle_compra")
        }
        create_database(LegacyConnection(conn))
        # Segundo arranque no debe duplicar ni reemplazar registros.
        create_database(LegacyConnection(conn))
        after = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in before
        }
        assert before == after
        row = conn.execute(
            "SELECT codigo,nombre,existencia,precio FROM productos WHERE id=81"
        ).fetchone()
        assert tuple(row) == ("ECH0000081", "Hilo legado", 11, 30)
        sale = conn.execute(
            "SELECT folio,total FROM ventas WHERE id=20"
        ).fetchone()
        assert tuple(sale) == ("V-ANT-1", 60)
        purchase = conn.execute(
            "SELECT folio,total FROM compras WHERE id=15"
        ).fetchone()
        assert tuple(purchase) == ("C-ANT-1", 150)
        assert "eliminado" in {
            x["name"] for x in conn.execute("PRAGMA table_info(productos)")
        }
        for table in ("pagos_venta", "pagos_compra", "cierres_caja"):
            assert conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
