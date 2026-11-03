"""Mide la versión secuencial y las tres MPI (mediana de varias repeticiones).

Ejecútalo DENTRO del contenedor, igual que el calibrador, con el mismo N elegido:

  docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 \
      python /app/medir_informe.py --n 8

Imprime las tablas en formato Markdown listas para copiar a INFORME.md.
"""

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PATRON = re.compile(r"Tiempo total:\s*([0-9]+(?:\.[0-9]+)?)\s*segundos")
MPIEXEC = ["mpiexec", "--allow-run-as-root", "--use-hwthread-cpus", "--oversubscribe"]


def ejecutar(comando, nombre, numero):
    print(f"  {nombre}, repetición {numero}...", flush=True)
    salida = subprocess.run(comando, capture_output=True, text=True)
    if salida.returncode != 0:
        print(salida.stdout[-2000:], salida.stderr[-2000:])
        sys.exit(f"Falló: {' '.join(comando)}")
    encontrado = PATRON.findall(salida.stdout)
    if not encontrado:
        sys.exit(f"No se encontró 'Tiempo total' en la salida de {nombre}")
    segundos = float(encontrado[-1])
    print(f"    tiempo total: {segundos:.3f} s", flush=True)
    return segundos


def formato(valor):
    return f"{valor:.2f}".replace(".", ",")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, required=True, help="valor común de N (calibrador)")
    parser.add_argument("--repeticiones", type=int, default=3)
    parser.add_argument("--tam-grupo", type=int, default=None,
                        help="tamaño de grupo del híbrido (por defecto el del programa)")
    args = parser.parse_args()

    py = sys.executable
    extra_hibrido = ["--tam-grupo", str(args.tam_grupo)] if args.tam_grupo else []
    casos = [
        ("Secuencial", 1, [py, str(RAIZ / "baseline_secuencial.py"), "--all"]),
        ("MPI por tableros", args.n, MPIEXEC + ["-n", str(args.n), py,
         str(RAIZ / "mpi_por_tableros" / "mpi_tableros.py"), "--all"]),
        ("MPI por ramas", args.n, MPIEXEC + ["-n", str(args.n), py,
         str(RAIZ / "mpi_por_ramas" / "mpi_ramas.py"), "--all"]),
        ("MPI híbrido", args.n, MPIEXEC + ["-n", str(args.n), py,
         str(RAIZ / "mpi_hibrido" / "mpi_hibrido.py"), "--all"] + extra_hibrido),
    ]

    medianas, crudos = {}, {}
    for nombre, _, comando in casos:
        print(f"{nombre}:", flush=True)
        tiempos = [ejecutar(comando, nombre, i) for i in range(1, args.repeticiones + 1)]
        crudos[nombre] = tiempos
        medianas[nombre] = statistics.median(tiempos)

    base = medianas["Secuencial"]
    print("\n| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |")
    print("| --- | --- | ---: | ---: | ---: |")
    descripcion = {"Secuencial": "Todos los IDs",
                   "MPI por tableros": "Todos los IDs",
                   "MPI por ramas": "Todos los IDs, uno después de otro",
                   "MPI híbrido": "Todos los IDs"}
    for nombre, procesos, _ in casos:
        print(f"| {nombre} | {descripcion[nombre]} | {procesos} | {formato(medianas[nombre])} "
              f"| {formato(base / medianas[nombre])} |")

    print("\nMediciones individuales (s):")
    for nombre, tiempos in crudos.items():
        print(f"- {nombre}: " + ", ".join(f"{t:.2f}" for t in tiempos))


if __name__ == "__main__":
    main()
