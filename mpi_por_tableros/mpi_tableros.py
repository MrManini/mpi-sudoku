"""Tarea 1: cada ID es una tarea que se asigna a un proceso trabajador.

Proceso 0 = coordinador (reparte IDs y reúne estados); procesos 1..N-1 =
trabajadores que resuelven tableros completos con `resolver_con_tiempo` de
`sudoku.py`. El reparto es dinámico: cada trabajador pide el siguiente ID en
cuanto termina, de modo que los tableros lentos no dejan a otros sin trabajo.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mpi4py import MPI  # noqa: E402

from mpi_comun import (TAG_RESULTADO, TAG_TAREA, es_solucion_valida,  # noqa: E402
                       leer_configuracion, mostrar_resultado, recibir_resultado)
from sudoku import resolver_con_tiempo  # noqa: E402


def trabajador(comunicador):
    while True:
        tarea = comunicador.recv(source=0, tag=TAG_TAREA)
        if tarea is None:
            return
        nombre, tablero = tarea
        resuelto, segundos = resolver_con_tiempo(tablero)   # modifica `tablero`
        comunicador.send((nombre, resuelto, segundos, tablero if resuelto else None),
                         dest=0, tag=TAG_RESULTADO)


def coordinador(comunicador, configuracion):
    tareas = list(configuracion["seleccionados"])
    originales = dict(tareas)
    un_solo_id = configuracion["un_solo_id"]
    trabajadores = comunicador.size - 1
    resultados = {}

    inicio = time.perf_counter()
    if trabajadores == 0:
        # Con un solo proceso no hay a quién repartir: se resuelve en serie.
        for nombre, tablero in tareas:
            resuelto, segundos = resolver_con_tiempo([f[:] for f in tablero])
            resultados[nombre] = (resuelto, segundos, 0)
            mostrar_resultado(nombre, resuelto, segundos, un_solo_id)
    else:
        siguiente = 0
        en_curso = 0
        for rango in range(1, trabajadores + 1):
            if siguiente < len(tareas):
                comunicador.send(tareas[siguiente], dest=rango, tag=TAG_TAREA)
                siguiente += 1
                en_curso += 1
        estado = MPI.Status()
        while en_curso:
            nombre, resuelto, segundos, solucion = recibir_resultado(comunicador, estado)
            rango = estado.Get_source()
            if resuelto and not es_solucion_valida(solucion, originales[nombre]):
                raise RuntimeError(f"El proceso {rango} devolvió una solución inválida para el ID {nombre}")
            resultados[nombre] = (resuelto, segundos, rango)
            mostrar_resultado(nombre, resuelto, segundos, un_solo_id)
            print(f"Resuelto por el proceso {rango}", flush=True)
            if siguiente < len(tareas):
                comunicador.send(tareas[siguiente], dest=rango, tag=TAG_TAREA)
                siguiente += 1
            else:
                en_curso -= 1
        for rango in range(1, trabajadores + 1):
            comunicador.send(None, dest=rango, tag=TAG_TAREA)
    total = time.perf_counter() - inicio   # tiempo real, no suma de los procesos

    if not un_solo_id:
        resueltos = sum(1 for r in resultados.values() if r[0])
        print(f"\nIDs procesados: {len(resultados)} de {len(tareas)} "
              f"({resueltos} resueltos)")
        suma = sum(r[1] for r in resultados.values())
        print(f"Suma de tiempos de búsqueda (solo informativa): {suma:.6f} segundos")
        print(f"\nTiempo total: {total:.6f} segundos")
    if len(resultados) != len(tareas):
        raise RuntimeError("No se procesaron todos los IDs")


def main():
    comunicador = MPI.COMM_WORLD
    configuracion = leer_configuracion(
        comunicador, "Sudoku con MPI: se reparten los tableros entre procesos.")
    if comunicador.rank == 0:
        coordinador(comunicador, configuracion)
    else:
        trabajador(comunicador)


if __name__ == "__main__":
    main()
