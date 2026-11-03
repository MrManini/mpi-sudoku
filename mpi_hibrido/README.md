# Tarea 3: combinar tableros y ramas

Implementa una versión MPI en esta carpeta. Reparte los IDs entre grupos de procesos y permite que los procesos de cada grupo exploren ramas distintas del tablero asignado.

Registra el tiempo total de los 30 IDs y explica cómo elegiste el tamaño de los grupos.

## Implementación: `mpi_hibrido.py`

- **Proceso 0 = coordinador**; los `W = N-1` procesos restantes son trabajadores y se dividen en grupos de tamaño parecido a `--tam-grupo` (cantidad de grupos `G = máx(1, W // tam_grupo)`; si no divide exacto, los primeros grupos tienen un proceso más).
- **Entre grupos: reparto de IDs.** Cada grupo trabaja en un tablero a la vez. Cuando un grupo termina el suyo, el coordinador le asigna el siguiente ID pendiente (reparto dinámico), así que `G` tableros avanzan simultáneamente.
- **Dentro de un grupo: reparto de ramas.** Para su tablero, el coordinador genera ramas (al menos `8 × tamaño del grupo`) y las entrega solo a los miembros de ese grupo, que las exploran con el mismo backtracking abortable de `mpi_por_ramas`. Al encontrarse la solución, se avisa a los demás miembros del grupo para que paren (con la misma lógica de épocas).
- **Casos límite que sirven de comprobación:** un solo grupo con todos los trabajadores = "por ramas"; grupos de un proceso = "por tableros" (cada tablero se explora entero como una única rama).
- **Tiempos.** Los tiempos parciales de distintos grupos se solapan, así que no se suman. El `Tiempo total` es el tiempo real de todo el trabajo medido en el coordinador.
- Con `N = 1` se resuelve en serie.

## Cómo ejecutar (con el contenedor)

Desde la carpeta raíz del taller (donde está `seeds.txt`). Reemplaza `N` por el valor
común elegido con `detectar_procesos_mpi.py`.

### macOS (Terminal)

Un tablero (ID 7):

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/mpi_hibrido.py --id 7 --tam-grupo 2
```

Todos los tableros:

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/mpi_hibrido.py --all --tam-grupo 2
```

### Windows (PowerShell)

Un tablero (ID 7):

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/mpi_hibrido.py --id 7 --tam-grupo 2
```

Todos los tableros:

```
docker run --rm -v "${PWD}:/app" augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root --use-hwthread-cpus --oversubscribe -n N python /app/mpi_hibrido/mpi_hibrido.py --all --tam-grupo 2
```

## Cómo elegir el tamaño de los grupos

El tamaño de grupo reparte los trabajadores entre dos fuentes de paralelismo con costos distintos:

- **Más grupos pequeños (más paralelismo entre tableros):** casi no hay trabajo repetido, porque cada tablero se explora con pocas ramas en paralelo. Su debilidad es que los tableros duran entre ~2 y ~10 s y, al final, quedan grupos esperando al tablero más lento.
- **Menos grupos grandes (más paralelismo dentro del tablero):** cada tablero termina antes, pero algunas ramas se exploran de más (especulativamente) antes de que llegue el aviso de parada, y hay más mensajes por tablero.

No hay un tamaño que sea mejor en teoría para todas las máquinas, así que se elige midiendo. `barrido_tam_grupo.py` ejecuta `--all` con todos los números distintos de grupos posibles para el mismo `N` del informe, repite cada medición y propone el de menor mediana:

```
docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 python /app/mpi_hibrido/barrido_tam_grupo.py --n N
```

(En PowerShell, usa `"${PWD}:/app"`.) **Pega aquí la tabla que imprime y escribe el tamaño elegido con su justificación:**

| Tamaño pedido | Grupos | Mediana (s) |
| ---: | ---: | ---: |
|  |  |  |

Tamaño elegido: _(completa con tus mediciones)_

Código compartido: `../mpi_comun.py`.
