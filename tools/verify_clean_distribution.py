"""Comprueba que una distribución no incluya información operativa."""

from pathlib import Path
import sys


DATABASE_ENDINGS = (".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3")


def find_forbidden_entries(distribution: str | Path) -> list[Path]:
    root = Path(distribution)
    forbidden = []

    for directory_name in ("data", "backups"):
        candidate = root / directory_name
        if candidate.exists():
            forbidden.append(candidate)

    if root.exists():
        for candidate in root.rglob("*"):
            if candidate.is_file() and candidate.name.lower().endswith(
                DATABASE_ENDINGS
            ):
                forbidden.append(candidate)

    return forbidden


def verify_distribution(distribution: str | Path) -> None:
    root = Path(distribution)
    executable = root / "EchandoChalPOS.exe"
    if not executable.is_file():
        raise ValueError(f"No se encontró el ejecutable esperado: {executable}")

    forbidden = find_forbidden_entries(root)
    if forbidden:
        details = "\n".join(f"- {path}" for path in forbidden)
        raise ValueError(
            "La distribución contiene datos que no deben publicarse:\n"
            f"{details}"
        )


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: verify_clean_distribution.py <carpeta-distribucion>")
        return 2

    try:
        verify_distribution(sys.argv[1])
    except ValueError as error:
        print(error)
        return 1

    print("Distribución validada: no contiene bases de datos ni respaldos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
