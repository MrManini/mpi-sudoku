"""Prueba distintos tamaños de grupo del híbrido y propone el más rápido.

Es la evidencia para explicar cómo se eligió el tamaño de los grupos. Ejecútalo
dentro del contenedor con el mismo N del informe:

  docker run --rm -v "$(pwd):/app" augustosalazar/slim-mpi:2 \
      python /app/mpi_hibrido/barrido_tam_grupo.py --n 8
"""

import argparse
import re
import statistics
import subprocess
import sys
from pathlib import Path

PROGRAMA = Path(__file__).resolve().parent / "mpi_hibrido.py"
PATRON = re.compile(r"Tiempo total:\s*([0-9]+(?:\.[0-9]+)?)\s*segundos")
MPIEXEC = ["mpiexec", "--allow-run-as-root", "--use-hwthread-cpus", "--oversubscribe"]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, required=True, help="valor común de N")
    parser.add_argument("--repeticiones", type=int, default=3)
    args = parser.parse_args()

    trabajadores = args.n - 1
    if trabajadores < 1:
        sys.exit("Se necesita N >= 2 (1 coordinador + al menos 1 trabajador).")

    # Un tamaño por cada cantidad distinta de grupos posible.
    candidatos, vistos = [], set()
    for tam in range(1, trabajadores + 1):
        cantidad = max(1, trabajadores // tam)
        if cantidad not in vistos:
            vistos.add(cantidad)
            candidatos.append(tam)

    resultados = []
    for tam in candidatos:
        tiempos = []
        for i in range(1, args.repeticiones + 1):
            comando = MPIEXEC + ["-n", str(args.n), sys.executable, str(PROGRAMA),
                                 "--all", "--tam-grupo", str(tam)]
            print(f"tam-grupo={tam}, repetición {i}...", flush=True)
            salida = subprocess.run(comando, capture_output=True, text=True)
            if salida.returncode != 0:
                print(salida.stdout[-2000:], salida.stderr[-2000:])
                sys.exit("Falló la ejecución.")
            tiempos.append(float(PATRON.findall(salida.stdout)[-1]))
            print(f"  {tiempos[-1]:.3f} s", flush=True)
        resultados.append((statistics.median(tiempos), tam, max(1, trabajadores // tam)))

    print("\n| Tamaño pedido | Grupos | Mediana (s) |")
    print("| ---: | ---: | ---: |")
    for mediana, tam, cantidad in resultados:
        print(f"| {tam} | {cantidad} | {mediana:.2f} |".replace(".", ","))
    mejor = min(resultados)
    print(f"\nMejor: --tam-grupo {mejor[1]} ({mejor[2]} grupo(s)), mediana {mejor[0]:.2f} s".replace(".", ","))


if __name__ == "__main__":
    main()
