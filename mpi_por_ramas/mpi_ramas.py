"""Tarea 2: los tableros se resuelven uno tras otro; las ramas de cada uno, en paralelo.

Proceso 0 = coordinador; procesos 1..N-1 = trabajadores.

Para cada tablero el coordinador:
  1. genera ramas expandiendo las primeras casillas vacías (solo valores válidos),
  2. las reparte dinámicamente (cada trabajador recibe otra al terminar la suya),
  3. cuando alguien encuentra la solución avisa a los demás para que abandonen la
     búsqueda, espera sus respuestas y solo entonces pasa al siguiente tablero.
"""

import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mpi4py import MPI  # noqa: E402

from mpi_comun import (RAMAS_POR_PROCESO, RESUELTO, TAG_PARAR, TAG_TAREA,  # noqa: E402
                       bucle_trabajador_ramas, copiar, es_solucion_valida,
                       generar_ramas, leer_configuracion, mostrar_resultado,
                       recibir_resultado, resolver_rama)


def resolver_tablero(comunicador, epoca, tablero, trabajadores, ramas_por_proceso):
    """Resuelve un tablero repartiendo sus ramas. Devuelve la solución o None."""
    ramas = deque(generar_ramas(tablero, ramas_por_proceso * trabajadores))
    solucion = None
    ocupados = set()
    estado = MPI.Status()

    for rango in range(1, trabajadores + 1):
        if ramas:
            comunicador.send((epoca, ramas.popleft()), dest=rango, tag=TAG_TAREA)
            ocupados.add(rango)

    while ocupados:
        _, resultado, rama_resuelta = recibir_resultado(comunicador, estado)
        rango = estado.Get_source()
        ocupados.discard(rango)
        if resultado == RESUELTO and solucion is None:
            solucion = rama_resuelta
            ramas.clear()
            for otro in ocupados:                      # los demás dejan de buscar
                comunicador.send(epoca, dest=otro, tag=TAG_PARAR)
        if solucion is None and ramas:
            comunicador.send((epoca, ramas.popleft()), dest=rango, tag=TAG_TAREA)
            ocupados.add(rango)
    return solucion


def coordinador(comunicador, configuracion):
    tableros = configuracion["seleccionados"]
    un_solo_id = configuracion["un_solo_id"]
    trabajadores = comunicador.size - 1
    ramas_por_proceso = configuracion["ramas_por_proceso"]

    inicio_total = time.perf_counter()
    for epoca, (nombre, original) in enumerate(tableros):
        inicio = time.perf_counter()
        if trabajadores == 0:
            # Con un solo proceso no hay con quién repartir: búsqueda serial.
            solucion = copiar(original)
            solucion = solucion if resolver_rama(solucion, lambda: False) else None
        else:
            solucion = resolver_tablero(comunicador, epoca, original,
                                        trabajadores, ramas_por_proceso)
        segundos = time.perf_counter() - inicio
        if solucion is not None and not es_solucion_valida(solucion, original):
            raise RuntimeError(f"Solución inválida para el ID {nombre}")
        mostrar_resultado(nombre, solucion is not None, segundos, un_solo_id)
    total = time.perf_counter() - inicio_total   # tiempo real de todo el trabajo

    for rango in range(1, trabajadores + 1):
        comunicador.send(None, dest=rango, tag=TAG_TAREA)
    if not un_solo_id:
        print(f"\nTiempo total: {total:.6f} segundos")


def agregar_argumentos(parser):
    parser.add_argument("--ramas-por-proceso", type=int, default=RAMAS_POR_PROCESO,
                        help="ramas que se generan, como mínimo, por cada trabajador "
                             f"(por defecto: {RAMAS_POR_PROCESO})")


def main():
    comunicador = MPI.COMM_WORLD
    configuracion = leer_configuracion(
        comunicador, "Sudoku con MPI: tableros en orden, ramas de cada tablero en paralelo.",
        agregar_argumentos)
    if comunicador.rank == 0:
        coordinador(comunicador, configuracion)
    else:
        bucle_trabajador_ramas(comunicador)


if __name__ == "__main__":
    main()
