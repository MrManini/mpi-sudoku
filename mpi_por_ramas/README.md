# Tarea 2: repartir ramas de cada tablero

Implementa una versión MPI en esta carpeta. Con `--all`, el proceso coordinador lee los 30 IDs de `seeds.txt` en orden. Para cada tablero, crea tareas a partir de opciones válidas de las primeras casillas vacías y reparte esas ramas entre procesos. Espera a que termine ese tablero antes de comenzar el siguiente: **los tableros se procesan secuencialmente y las ramas de cada tablero en paralelo**.

Cada proceso explora su rama con backtracking y comunica el resultado. Cuando se encuentra una solución, los demás deben dejar de buscar ese tablero. Muestra el estado y el tiempo parcial de cada ID al terminarlo, además del tiempo total de los 30. Conserva la opción `--id` para resolver un solo tablero.

## Implementación: `mpi_ramas.py`

- **Proceso 0 = coordinador**; procesos `1..N-1` = trabajadores.
- **Los tableros se procesan en orden** (IDs 1 a 30) y el siguiente no empieza hasta que terminó el anterior.
- **Generación de ramas.** Para cada tablero, el coordinador expande las primeras casillas vacías (en el mismo orden que el backtracking serial: primera casilla vacía, valores 1..9) conservando solo los valores válidos, hasta tener al menos `8 × (número de trabajadores)` ramas (`--ramas-por-proceso` cambia el 8). Cada rama es un tablero parcial.
- **Reparto dinámico.** Cada trabajador recibe una rama; al terminar pide otra. Así las ramas que mueren enseguida no dejan procesos ociosos, y las ramas se entregan en el orden en que las visitaría el algoritmo serial.
- **Cada trabajador explora su rama con backtracking** (`resolver_rama` en `../mpi_comun.py`: el mismo algoritmo de `sudoku.py`, pero abortable).
- **Parada temprana.** Cuando un trabajador encuentra la solución, el coordinador envía un aviso de parada a los trabajadores que siguen ocupados. Estos consultan con `Iprobe` si llegó el aviso cada 2000 nodos de backtracking y abandonan la rama. El coordinador espera la respuesta de todos y solo entonces pasa al siguiente tablero. Cada tablero tiene un número de *época* y un aviso solo vale para su época, de modo que un aviso tardío no cancela el tablero siguiente.
- **Tiempos.** El tiempo parcial de cada ID es el tiempo real medido en el coordinador, desde que empieza a generar ramas hasta que todos los trabajadores respondieron. El tiempo total es el tiempo real de todo el trabajo (no una suma de tiempos de procesos).
- Se conserva `--id` para resolver un solo tablero. Con `N = 1` se resuelve en serie.

## Cómo ejecutar (con el contenedor)

Desde la carpeta raíz del taller (donde está `seeds.txt`). Reemplaza `N` por el valor
común elegido con `detectar_procesos_mpi.py`.

### macOS (Terminal)

Un tablero (ID 7):

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_ramas.py --id 7
```

Todos los tableros:

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_ramas.py --all
```

### Windows (PowerShell)

Un tablero (ID 7):

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_ramas.py --id 7
```

Todos los tableros:

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_por_ramas/mpi_ramas.py --all
```

Compara el `Tiempo total` de `--all` con el de `baseline_secuencial.py --all` y registra los resultados en `../INFORME.md`. Para medir las tres repeticiones y calcular medianas y aceleraciones automáticamente, usa `../medir_informe.py` (ver el README de la raíz del taller o su cabecera).

Código compartido (generación de ramas, backtracking abortable, bucle del trabajador): `../mpi_comun.py`.
