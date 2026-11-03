# Informe de resultados

## Entorno

- Equipo: AMD Ryzen 4600H, 16GB RAM, Win11
- Versión del contenedor: `augustosalazar/slim-mpi:2`
- Cantidad de repeticiones por medición: 3
- Valor común de `N` elegido: 11 (1 proceso coordinador + 10 trabajadores), obtenido con `detectar_procesos_mpi.py`

## Comparación final con el mismo `N`

| Implementación | Caso | Procesos | Mediana del tiempo total (s) | Aceleración frente a secuencial |
| --- | --- | ---: | ---: | ---: |
| Secuencial | Todos los IDs | 1 | 115.26 | 1.00 |
| MPI por tableros | Todos los IDs | 11 | 23.51 | 4.90 |
| MPI por ramas | Todos los IDs, uno después de otro | 11 | 24.92 | 4.63 |
| MPI híbrido | Todos los IDs | 11 | 24.05 | 4.79 |

Mediciones individuales (s):

- Secuencial: 115.33, 113.35, 115.26
- MPI por tableros: 23.20, 23.71, 23.51
- MPI por ramas: 24.83, 24.92, 26.61
- MPI híbrido: 23.81, 24.05, 24.18

Aceleración = tiempo secuencial / tiempo MPI. El tiempo MPI se mide en el proceso coordinador, desde que empieza el reparto hasta que llegan todos los resultados.

### Tamaño de los grupos del híbrido

Con N = 11 hay 10 trabajadores. Se probó cada cantidad distinta de grupos posible (3 repeticiones, mediana):

| Tamaño pedido | Grupos | Mediana (s) |
| ---: | ---: | ---: |
| 1 | 10 | 24.14 |
| 2 | 5 | 23.48 |
| 3 | 3 | 24.98 |
| 4 | 2 | 25.09 |
| 6 | 1 | 26.00 |

El tamaño pedido no siempre es el real: con 10 trabajadores, un tamaño de 6 o más produce un solo grupo con los 10, y tamaños como 3 o 4 producen grupos de tamaños desiguales. Se eligió **tamaño 2 (5 grupos)** por tener la menor mediana. Los grupos pequeños fueron los más rápidos y el tiempo aumentó al agrandar los grupos; el caso de un solo grupo (26.00 s) es en la práctica la estrategia "por ramas".

## Conclusiones

- **¿Qué estrategia obtuvo el menor tiempo para los 30 tableros? ¿Cuánto mejoró respecto a la versión secuencial?**
  La más rápida fue MPI por tableros: 23.51 s frente a 115.26 s de la versión secuencial, una aceleración de 4.90 (alrededor de 80% menos de tiempo). El híbrido quedó muy cerca (24.05 s, aceleración 4.79; unos 2% más lento) y por ramas fue la más lenta (24.92 s, aceleración 4.63; cerca de 6% más lenta que por tableros). Las tres versiones mejoran mucho respecto a la secuencial, y las diferencias entre ellas son pequeñas comparadas con esa mejora. Ninguna llegó a una aceleración de 10, que sería lo ideal con 10 trabajadores.

- **¿Cómo afectaron la comunicación y las diferencias de duración entre tableros?**
  Los tableros duran entre unos 2 y 10 s, así que repartirlos por adelantado habría dejado procesos esperando a los más lentos. En las tres versiones el reparto es dinámico: cada trabajador pide más trabajo en cuanto termina. En por tableros la comunicación es mínima (un mensaje de ida y uno de vuelta por tablero), y por eso fue la más rápida. Aun así, al final de la ejecución los últimos tableros lentos corren con pocos procesos activos. En por ramas hay muchos más mensajes y, además, al terminar cada tablero todos los trabajadores deben detenerse y responder antes de empezar el siguiente; esa espera se repite 30 veces. También es posible que algunas ramas se exploren de más antes de que llegue el aviso de parada. Estas explicaciones son razonables según cómo está diseñado el programa, pero no se midieron por separado. Que ninguna versión llegue a la aceleración ideal puede deberse a que el coordinador no resuelve tableros (quedan 10 trabajadores de 11 procesos) y a que los procesos comparten los recursos del procesador.

- **¿Cómo se comparó repartir tableros con resolverlos en orden y repartir las ramas de cada uno?**
  Repartir tableros fue ligeramente mejor que resolverlos en orden repartiendo ramas (23.51 s frente a 24.92 s). Hay suficiente trabajo (30 tableros) para mantener ocupados a los 10 trabajadores sin necesidad de dividir cada tablero, y dividirlo agrega mensajes, esperas de sincronización y posible trabajo repetido. El híbrido combina ambas ideas, y la prueba de tamaños de grupo lo confirma: los grupos pequeños (más tableros en paralelo) rindieron mejor que los grandes (más ramas por tablero), y un único grupo grande fue el más lento (26.00 s). Con 30 tableros y 10 trabajadores, el mejor resultado del híbrido (23.48 s con grupos de tamaño 2) quedó prácticamente empatado con por tableros (23.51 s): la diferencia es del orden de la variación entre repeticiones.