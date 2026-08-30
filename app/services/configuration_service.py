from app.database.connection import Database


class ConfigurationService:
    """Consulta y actualiza la configuración general del POS."""

    DEFAULTS = {
        "nombre_negocio": "Echando Chal",
        "comision_mercado_libre": "4.00",
        "moneda": "MXN",
    }

    def __init__(self, database: Database) -> None:
        self.database = database

    def get_setting(self, key: str) -> str:
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT valor FROM configuracion WHERE clave = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return self.DEFAULTS.get(key, "")
        return str(row["valor"])

    def get_settings(self) -> dict:
        commission_text = self.get_setting("comision_mercado_libre")
        try:
            commission = float(commission_text)
        except (TypeError, ValueError):
            commission = 4.0

        return {
            "nombre_negocio": self.get_setting("nombre_negocio"),
            "comision_mercado_libre": commission,
            "moneda": self.get_setting("moneda") or "MXN",
        }

    def get_business_name(self) -> str:
        return self.get_setting("nombre_negocio") or "Echando Chal"

    def update_settings(
        self,
        business_name: str,
        marketplace_commission: float,
    ) -> dict:
        business_name = business_name.strip()
        commission = float(marketplace_commission)

        if not business_name:
            raise ValueError("El nombre del negocio es obligatorio.")
        if len(business_name) > 100:
            raise ValueError(
                "El nombre del negocio no puede superar 100 caracteres."
            )
        if commission < 0 or commission > 100:
            raise ValueError(
                "La comisión debe estar entre 0 y 100 por ciento."
            )

        cursor = self.database.cursor()
        try:
            cursor.executemany(
                """
                INSERT INTO configuracion (clave, valor)
                VALUES (?, ?)
                ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
                """,
                (
                    ("nombre_negocio", business_name),
                    ("comision_mercado_libre", f"{commission:.2f}"),
                ),
            )
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise

        return self.get_settings()
