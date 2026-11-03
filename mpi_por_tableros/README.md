# Tarea 1: repartir tableros

Implementa una versión MPI en esta carpeta. Al ejecutar todos los tableros, cada ID debe ser una tarea que pueda asignarse a un proceso. Reutiliza el resolvedor de `../sudoku.py` y reúne los estados en el proceso coordinador.

Registra el tiempo total de ejecución y confirma que se procesaron los 30 IDs.

## Implementación: `mpi_tableros.py`

- **Proceso 0 = coordinador**; procesos `1..N-1` = trabajadores. El coordinador no resuelve tableros: reparte IDs y reúne estados.
- **Reparto dinámico (maestro-trabajador).** Cada trabajador recibe un ID; al terminar, devuelve el resultado y el coordinador le asigna el siguiente ID pendiente. Como los tableros tardan entre ~2 y ~10 s, un reparto estático en bloques dejaría procesos esperando a los más lentos.
- Cada trabajador usa `resolver_con_tiempo` de `../sudoku.py` sobre su propio tablero completo, así que el algoritmo es el mismo de la versión secuencial.
- El coordinador comprueba que cada solución recibida sea válida (filas, columnas, bloques y pistas originales) y, al final, que se procesaron todos los IDs: imprime `IDs procesados: 30 de 30`.
- **Tiempo total** = tiempo real medido en el coordinador (`time.perf_counter()`) desde que se envía la primera tarea hasta que llega el último resultado. La "suma de tiempos de búsqueda" que también se imprime es solo informativa: no es el tiempo total.
- El coordinador espera con `Iprobe` + `sleep` de 0,5 ms en vez de un `recv` bloqueante, para no ocupar al 100 % un hilo de hardware que necesitan los trabajadores.
- Con `N = 1` no hay trabajadores y el coordinador resuelve en serie.

## Cómo ejecutar (con el contenedor)

Desde la carpeta raíz del taller (donde está `seeds.txt`). Reemplaza `N` por el valor
común elegido con `detectar_procesos_mpi.py`.

### macOS (Terminal)

Un tablero (ID 7):

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_tableros.py --id 7
```

Todos los tableros:

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_tableros.py --all
```

### Windows (PowerShell)

Un tablero (ID 7):

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_tableros.py --id 7
```

Todos los tableros:

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_tableros/mpi_tableros.py --all
```

La salida muestra, conforme termina cada ID, su estado, el tiempo de búsqueda en el trabajador y qué proceso lo resolvió; al final, `IDs procesados` y `Tiempo total`.

Código compartido (lectura de seeds, verificación, espera sin CPU): `../mpi_comun.py`.
