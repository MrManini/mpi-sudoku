"""Utilidades compartidas por las tres implementaciones MPI del taller.

Contiene:
  * lectura de argumentos/seeds en el proceso 0 y difusión al resto,
  * generación de ramas (primeras casillas vacías) de un tablero,
  * un resolvedor por backtracking que puede cancelarse a mitad de búsqueda,
  * el bucle del proceso trabajador usado por `mpi_por_ramas` y `mpi_hibrido`,
  * verificación de soluciones y una espera que no consume CPU.

El backtracking es el mismo de `sudoku.py` (primera casilla vacía, valores 1..9,
`puede_colocar`); solo se añade la posibilidad de abortar la búsqueda.
"""

import argparse
import sys
import time
from pathlib import Path

from mpi4py import MPI

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from baseline_secuencial import leer_seeds  # noqa: E402
from sudoku import puede_colocar  # noqa: E402

# Etiquetas de mensajes MPI.
TAG_TAREA = 1       # coordinador -> trabajador: (época, tablero) o None para terminar
TAG_RESULTADO = 2   # trabajador -> coordinador: (época, estado, solución)
TAG_PARAR = 3       # coordinador -> trabajador: época cuyo trabajo debe abortarse

# Estados que puede devolver un trabajador al explorar una rama.
RESUELTO = "resuelto"
SIN_SOLUCION = "sin"
ABORTADO = "abortado"

# Cada cuántos nodos de backtracking se consulta si hay que parar.
NODOS_ENTRE_CONSULTAS = 2000

# Ramas que se intentan generar por cada proceso que las va a explorar.
RAMAS_POR_PROCESO = 8


# --------------------------------------------------------------------------
# Argumentos y seeds
# --------------------------------------------------------------------------
def leer_configuracion(comunicador, descripcion, agregar_argumentos=None):
    """El proceso 0 interpreta los argumentos y lee las seeds; luego las difunde.

    Devuelve un diccionario con:
      seleccionados -> lista [(id, tablero)] en el orden del archivo,
      un_solo_id    -> True si se usó --id,
      más los argumentos extra definidos por `agregar_argumentos(parser)`.
    Si hay un error (o se pidió --help) todos los procesos terminan juntos.
    """
    configuracion = None
    if comunicador.rank == 0:
        try:
            configuracion = _preparar(descripcion, agregar_argumentos)
        except SystemExit:
            configuracion = None
    configuracion = comunicador.bcast(configuracion, root=0)
    if configuracion is None:
        sys.exit(2)
    return configuracion


def _preparar(descripcion, agregar_argumentos):
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument("--archivo", type=Path, default=RAIZ / "seeds.txt",
                        help="archivo de seeds (por defecto: seeds.txt de la carpeta del taller)")
    seleccion = parser.add_mutually_exclusive_group()
    seleccion.add_argument("--id", "--seed", dest="id", help="resolver solo la seed con este ID")
    seleccion.add_argument("--all", action="store_true", help="resolver todas las seeds")
    if agregar_argumentos:
        agregar_argumentos(parser)
    args = parser.parse_args()

    try:
        seeds = leer_seeds(args.archivo)
    except OSError as error:
        parser.error(f"no se pudo leer {args.archivo}: {error}")
    if not seeds:
        parser.error(f"no se encontraron seeds en {args.archivo}")

    if args.id:
        if args.id not in seeds:
            parser.error(f"ID '{args.id}' no existe. Disponibles: {', '.join(seeds)}")
        seleccionados = [(args.id, seeds[args.id])]
    else:
        # Sin --id se resuelven todos, igual que con --all.
        seleccionados = list(seeds.items())

    configuracion = vars(args)
    configuracion["seleccionados"] = seleccionados
    configuracion["un_solo_id"] = bool(args.id)
    return configuracion


# --------------------------------------------------------------------------
# Tableros: copia, ramas, verificación
# --------------------------------------------------------------------------
def copiar(tablero):
    return [fila[:] for fila in tablero]


def primera_vacia(tablero):
    for fila in range(9):
        for columna in range(9):
            if tablero[fila][columna] == 0:
                return fila, columna
    return None


def generar_ramas(tablero, minimo):
    """Expande las primeras casillas vacías hasta tener al menos `minimo` ramas.

    Cada rama es un tablero parcial con una combinación válida de valores en esas
    casillas. Se conserva el orden en que las visitaría el backtracking serial,
    así que repartir las ramas en ese orden no explora de más sin necesidad.
    Una lista vacía significa que el tablero no tiene solución.
    """
    frontera = [copiar(tablero)]
    while len(frontera) < minimo:
        siguiente = []
        expandio = False
        for parcial in frontera:
            posicion = primera_vacia(parcial)
            if posicion is None:          # ya está completo
                siguiente.append(parcial)
                continue
            expandio = True
            fila, columna = posicion
            for valor in range(1, 10):
                if puede_colocar(parcial, fila, columna, valor):
                    hija = copiar(parcial)
                    hija[fila][columna] = valor
                    siguiente.append(hija)
        frontera = siguiente
        if not expandio or not frontera:
            break
    return frontera


def es_solucion_valida(solucion, original):
    """Comprueba filas, columnas, bloques 3x3 y que se respeten las pistas."""
    if solucion is None:
        return False
    esperado = set(range(1, 10))
    for i in range(9):
        if set(solucion[i]) != esperado:
            return False
        if {solucion[f][i] for f in range(9)} != esperado:
            return False
    for bf in range(0, 9, 3):
        for bc in range(0, 9, 3):
            if {solucion[f][c] for f in range(bf, bf + 3)
                for c in range(bc, bc + 3)} != esperado:
                return False
    return all(original[f][c] in (0, solucion[f][c])
               for f in range(9) for c in range(9))


# --------------------------------------------------------------------------
# Backtracking cancelable
# --------------------------------------------------------------------------
class _Cancelado(Exception):
    pass


def resolver_rama(tablero, debe_parar, nodos_entre_consultas=NODOS_ENTRE_CONSULTAS):
    """Backtracking idéntico a `sudoku.resolver`, pero abortable.

    Modifica `tablero` in situ. Devuelve True (resuelto), False (sin solución en
    esta rama) o None (abortado porque `debe_parar()` devolvió True).
    """
    restantes = nodos_entre_consultas

    def buscar():
        nonlocal restantes
        restantes -= 1
        if restantes == 0:
            restantes = nodos_entre_consultas
            if debe_parar():
                raise _Cancelado
        for fila in range(9):
            for columna in range(9):
                if tablero[fila][columna] != 0:
                    continue
                for valor in range(1, 10):
                    if puede_colocar(tablero, fila, columna, valor):
                        tablero[fila][columna] = valor
                        if buscar():
                            return True
                        tablero[fila][columna] = 0  # retroceso
                return False
        return True  # no quedan casillas vacías

    try:
        return buscar()
    except _Cancelado:
        return None


# --------------------------------------------------------------------------
# Trabajador de ramas (lo usan mpi_por_ramas y mpi_hibrido)
# --------------------------------------------------------------------------
def bucle_trabajador_ramas(comunicador, coordinador=0):
    """Recibe ramas, las explora y responde. Termina al recibir `None`.

    Cada tarea lleva una *época* (número único por tablero). Un aviso de parada
    solo cuenta si su época coincide con la de la tarea en curso; así un aviso
    que llega tarde, cuando el trabajador ya terminó, no afecta al tablero
    siguiente.
    """
    epoca_actual = None

    def debe_parar():
        while comunicador.Iprobe(source=coordinador, tag=TAG_PARAR):
            if comunicador.recv(source=coordinador, tag=TAG_PARAR) == epoca_actual:
                return True
        return False

    while True:
        tarea = comunicador.recv(source=coordinador, tag=TAG_TAREA)
        if tarea is None:
            break
        epoca_actual, rama = tarea
        resultado = resolver_rama(rama, debe_parar)
        if resultado is None:
            respuesta = (epoca_actual, ABORTADO, None)
        elif resultado:
            respuesta = (epoca_actual, RESUELTO, rama)
        else:
            respuesta = (epoca_actual, SIN_SOLUCION, None)
        comunicador.send(respuesta, dest=coordinador, tag=TAG_RESULTADO)

    while comunicador.Iprobe(source=coordinador, tag=TAG_PARAR):  # avisos tardíos
        comunicador.recv(source=coordinador, tag=TAG_PARAR)


# --------------------------------------------------------------------------
# Espera sin ocupar la CPU
# --------------------------------------------------------------------------
def recibir_resultado(comunicador, estado, pausa=0.0005):
    """Espera un resultado de cualquier proceso sin hacer espera activa.

    `recv` bloqueante de MPI consume el 100 % de un hilo de hardware mientras
    espera, y ese hilo se necesita para los trabajadores. Aquí se consulta con
    `Iprobe` y se duerme entre consultas (la latencia añadida es de ~0,5 ms,
    despreciable frente a tareas de segundos).
    """
    while not comunicador.Iprobe(source=MPI.ANY_SOURCE, tag=TAG_RESULTADO, status=estado):
        time.sleep(pausa)
    return comunicador.recv(source=estado.Get_source(), tag=TAG_RESULTADO)


def mostrar_resultado(nombre, resuelto, segundos, un_solo_id, etiqueta_parcial="Tiempo parcial"):
    print(f"\nID: {nombre}")
    print("Resuelto" if resuelto else "Sin solución")
    etiqueta = "Tiempo" if un_solo_id else etiqueta_parcial
    print(f"{etiqueta}: {segundos:.6f} segundos", flush=True)
