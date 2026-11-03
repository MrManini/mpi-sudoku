"""Tarea 3: IDs repartidos entre grupos de procesos, ramas repartidas dentro de cada grupo.

Proceso 0 = coordinador; los procesos 1..N-1 son trabajadores y se dividen en G
grupos de tamaño parecido a `--tam-grupo`. Cada grupo trabaja en *un* tablero a
la vez:

  * entre grupos -> reparto de IDs (cuando un grupo termina, toma el siguiente ID);
  * dentro de un grupo -> reparto de ramas del tablero (como en `mpi_por_ramas`),
    con aviso de parada para sus miembros cuando se encuentra la solución.

Casos límite: un solo grupo con todos los trabajadores equivale a "por ramas";
grupos de un solo proceso equivalen a "por tableros".
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

TAM_GRUPO_POR_DEFECTO = 2


def dividir_en_grupos(trabajadores, tam_grupo):
    """Reparte los rangos 1..trabajadores en grupos de tamaño lo más parejo posible."""
    cantidad = max(1, trabajadores // max(1, tam_grupo))
    base, sobrante = divmod(trabajadores, cantidad)
    grupos, siguiente = [], 1
    for i in range(cantidad):
        tam = base + (1 if i < sobrante else 0)
        grupos.append(list(range(siguiente, siguiente + tam)))
        siguiente += tam
    return grupos


class Grupo:
    """Estado del tablero que está resolviendo un grupo de trabajadores."""

    def __init__(self, indice, rangos):
        self.indice = indice
        self.rangos = rangos
        self.activo = False

    def iniciar(self, comunicador, epoca, nombre, original, ramas_por_proceso):
        self.activo = True
        self.nombre = nombre
        self.original = original
        self.epoca = epoca
        self.solucion = None
        self.ocupados = set()
        self.inicio = time.perf_counter()
        # Un grupo de un solo proceso explora el tablero completo como una única rama.
        minimo = 1 if len(self.rangos) == 1 else ramas_por_proceso * len(self.rangos)
        self.ramas = deque(generar_ramas(original, minimo))
        for rango in self.rangos:
            self.enviar_siguiente(comunicador, rango)

    def enviar_siguiente(self, comunicador, rango):
        if self.solucion is None and self.ramas:
            comunicador.send((self.epoca, self.ramas.popleft()), dest=rango, tag=TAG_TAREA)
            self.ocupados.add(rango)

    def recibir(self, comunicador, rango, resultado, rama):
        self.ocupados.discard(rango)
        if resultado == RESUELTO and self.solucion is None:
            self.solucion = rama
            self.ramas.clear()
            for otro in self.ocupados:                 # parar al resto del grupo
                comunicador.send(self.epoca, dest=otro, tag=TAG_PARAR)
        self.enviar_siguiente(comunicador, rango)

    @property
    def terminado(self):
        return not self.ocupados


def coordinador(comunicador, configuracion):
    tableros = deque(configuracion["seleccionados"])
    un_solo_id = configuracion["un_solo_id"]
    trabajadores = comunicador.size - 1
    ramas_por_proceso = configuracion["ramas_por_proceso"]
    cantidad_tableros = len(tableros)
    terminados = 0

    def cerrar(grupo):
        segundos = time.perf_counter() - grupo.inicio
        if grupo.solucion is not None and not es_solucion_valida(grupo.solucion, grupo.original):
            raise RuntimeError(f"Solución inválida para el ID {grupo.nombre}")
        mostrar_resultado(grupo.nombre, grupo.solucion is not None, segundos, un_solo_id)
        if trabajadores:
            print(f"Grupo {grupo.indice} (procesos {grupo.rangos[0]}-{grupo.rangos[-1]})", flush=True)

    inicio_total = time.perf_counter()
    if trabajadores == 0:
        # Con un solo proceso no hay con quién repartir: búsqueda serial.
        for nombre, original in tableros:
            inicio = time.perf_counter()
            tablero = copiar(original)
            resuelto = bool(resolver_rama(tablero, lambda: False))
            mostrar_resultado(nombre, resuelto, time.perf_counter() - inicio, un_solo_id)
        terminados = cantidad_tableros
    else:
        grupos = [Grupo(i, r) for i, r in enumerate(
            dividir_en_grupos(trabajadores, configuracion["tam_grupo"]))]
        grupo_de = {rango: g for g in grupos for rango in g.rangos}
        if not un_solo_id:
            tamanos = ", ".join(str(len(g.rangos)) for g in grupos)
            print(f"Procesos: {comunicador.size} = 1 coordinador + {trabajadores} trabajadores "
                  f"en {len(grupos)} grupo(s) de tamaño {tamanos}", flush=True)

        epoca = 0

        def asignar(grupo):
            """Da al grupo el siguiente ID; cierra los que no tengan ramas que explorar."""
            nonlocal epoca, terminados
            while tableros:
                nombre, original = tableros.popleft()
                grupo.iniciar(comunicador, epoca, nombre, original, ramas_por_proceso)
                epoca += 1
                if not grupo.terminado:
                    return
                cerrar(grupo)               # tablero sin ramas válidas: sin solución
                terminados += 1
            grupo.activo = False

        for grupo in grupos:
            asignar(grupo)

        estado = MPI.Status()
        while any(g.activo for g in grupos):
            _, resultado, rama = recibir_resultado(comunicador, estado)
            rango = estado.Get_source()
            grupo = grupo_de[rango]
            grupo.recibir(comunicador, rango, resultado, rama)
            if grupo.terminado:
                cerrar(grupo)
                terminados += 1
                asignar(grupo)

        for rango in range(1, trabajadores + 1):
            comunicador.send(None, dest=rango, tag=TAG_TAREA)
    total = time.perf_counter() - inicio_total   # tiempo real, no suma de los procesos

    if terminados != cantidad_tableros:
        raise RuntimeError("No se procesaron todos los IDs")
    if not un_solo_id:
        print(f"\nIDs procesados: {terminados} de {cantidad_tableros}")
        print("(Los tiempos parciales se solapan entre grupos; no se pueden sumar.)")
        print(f"\nTiempo total: {total:.6f} segundos")


def agregar_argumentos(parser):
    parser.add_argument("--tam-grupo", type=int, default=TAM_GRUPO_POR_DEFECTO,
                        help="tamaño deseado de cada grupo de trabajadores "
                             f"(por defecto: {TAM_GRUPO_POR_DEFECTO})")
    parser.add_argument("--ramas-por-proceso", type=int, default=RAMAS_POR_PROCESO,
                        help="ramas que se generan, como mínimo, por cada miembro del grupo "
                             f"(por defecto: {RAMAS_POR_PROCESO})")


def main():
    comunicador = MPI.COMM_WORLD
    configuracion = leer_configuracion(
        comunicador, "Sudoku con MPI híbrido: IDs entre grupos, ramas dentro de cada grupo.",
        agregar_argumentos)
    if comunicador.rank == 0:
        coordinador(comunicador, configuracion)
    else:
        bucle_trabajador_ramas(comunicador)


if __name__ == "__main__":
    main()
