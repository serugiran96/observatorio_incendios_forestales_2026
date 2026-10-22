"""Valida el registro de fuentes, evidencias y vacíos de información.

Uso:
    uv run python scripts/validar_registro.py

Termina con código 1 si hay errores, para poder usarlo antes de cada commit.
"""

from __future__ import annotations

import sys

from observatorio import evidencias as ev


def main() -> int:
    fuentes = ev.cargar_fuentes()
    registros = ev.cargar_evidencias()
    vacios = ev.cargar_vacios()

    resultados = {
        "fuentes.csv": ev.validar_fuentes(fuentes),
        "evidencias.csv": ev.validar_evidencias(registros, fuentes),
        "vacios_informacion.csv": ev.validar_vacios(vacios),
    }
    print(f"Fuentes: {len(fuentes)} | Evidencias: {len(registros)} | Vacíos: {len(vacios)}\n")
    for nombre, resultado in resultados.items():
        print(f"[{nombre}] {resultado.resumen()}\n")
    return 0 if all(r.es_valido for r in resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
