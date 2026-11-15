# Discusión de trade-offs

## Comparación


| Atributo                  | Arquitectura 1 (302 + Log gRPC)                     | Arquitectura 2 (301 + rate limiter + caché)             |
| ------------------------- | --------------------------------------------------- | ------------------------------------------------------- |
| Analítica de visitas      | Completa: cada visita pasa por el Shortener         | Parcial: solo la primera visita de cada navegador       |
| Carga sobre el servidor   | Alta: una petición y una lectura de DB por visita   | Baja: el navegador y el caché absorben las repeticiones |
| Latencia para el usuario  | Siempre incluye el paso por el Shortener            | Las visitas repetidas se resuelven en el navegador      |
| Control sobre los enlaces | Un cambio de destino aplica de inmediato            | Un 301 ya entregado no se puede revertir                |
| Protección ante abuso     | Ninguna                                             | Rate limiter por IP                                     |
| Complejidad               | Dos procesos, dos bases de datos y un contrato gRPC | Un proceso y una base de datos                          |




## Arquitectura 1

**Gana modificabilidad y observabilidad.** El 302 obliga al navegador a consultar al Shortener en
cada visita, lo que permite registrar todas las visitas. El Log es un componente separado con su
propia base de datos, así que la analítica puede evolucionar sin tocar el Shortener.

**Lo paga en desempeño, disponibilidad y complejidad:**

- La carga crece en proporción directa al tráfico: cada visita implica una lectura a la base de
datos y una llamada gRPC.
- El Shortener queda en el camino de todas las visitas. Si se cae, ningún enlace funciona.
- Hay más piezas que desplegar y monitorear, y un contrato entre ellas que mantener.
- No hay control de arribo: una ráfaga de peticiones llega íntegra al Shortener, a la base de
datos y al Log.
- En esta implementación el hit se envía después de responder y con mejor esfuerzo. Se
privilegió la disponibilidad de la redirección sobre la completitud de los datos: si el Log
está caído, esos hits se pierden. Garantizar la entrega exigiría una cola de eventos, es decir,
más complejidad.



## Arquitectura 2

**Gana desempeño, disponibilidad y simplicidad.** El 301 deja que el navegador resuelva las
visitas repetidas sin contactar al servidor, incluso si este está caído. El caché evita consultar
la base de datos para los enlaces más visitados. El rate limiter acota la carga máxima que puede
generar cada cliente.

**Lo paga en observabilidad, control y consistencia:**

- No hay analítica, y el 301 impide agregarla después: el servidor solo vería la primera visita
de cada navegador.
- Un 301 guardado por un navegador no se puede revertir desde el servidor. Si los enlaces
llegaran a ser editables o eliminables, los usuarios seguirían llegando al destino antiguo.
- El caché del servidor puede entregar datos desactualizados hasta que expire, y consume memoria.
- El límite por IP puede rechazar usuarios legítimos que comparten una misma dirección pública,
por ejemplo detrás de un NAT.
- El caché y los contadores del rate limiter viven en la memoria del proceso. Con varias
instancias no se comparten, y el límite efectivo se multiplica por el número de instancias.
Escalar horizontalmente exigiría un almacén compartido, como Redis.



## ¿Son de consideración en este dominio?

En un acortador de URLs las lecturas superan ampliamente a las escrituras, y los registros son
pequeños e inmutables. Eso hace que el peso de cada trade-off dependa de dos preguntas.

**¿Se necesita saber cuántas visitas recibe cada enlace?** Es el trade-off más importante, porque
es el único que no se puede resolver agregando componentes: el caché del navegador y el conteo de
visitas son incompatibles. Si la analítica importa, el 302 es obligatorio y su costo en carga es
el precio a pagar.

**¿Cuánto tráfico se espera?** Con tráfico bajo o moderado, el costo de desempeño de la
arquitectura 1 es poco relevante, ya que resolver un hash es una lectura indexada muy barata. Con
tráfico alto, ese costo se multiplica por cada visita y las tácticas de la arquitectura 2 pasan a
ser necesarias.

Los demás trade-offs pesan menos:

- La pérdida de control por el 301 no afecta mientras los enlaces sean inmutables, como en esta
implementación. Pasaría a ser grave si se permitiera editarlos.
- La inconsistencia del caché tampoco se manifiesta hoy, por la misma razón.
- La complejidad adicional de la arquitectura 1 es real pero acotada: un servicio y una base de
datos más.
- El estado local de la arquitectura 2 solo importa al escalar a más de una instancia.

Por último, las tácticas de la arquitectura 2 no dependen del código 301. El rate limiter y el
caché del servidor podrían agregarse a la arquitectura 1 manteniendo el 302, con lo que se
obtendría protección y menor carga sobre la base de datos sin renunciar a la analítica.

**Aplicado a la USM como mandante.** A la primera pregunta la respuesta es sí: una universidad usa enlaces cortos sobre todo para difusión (admisión, postulaciones, eventos), y contar las visitas es lo que permite evaluar esas campañas. A la segunda, el tráfico de un acortador institucional es moderado, con picos acotados en períodos de postulación. Con analítica valiosa y carga baja, se recomienda la arquitectura 1, ya que sus costos pesan poco a esa escala y lo que entrega es lo que más valor tiene para la universidad. La arquitectura 2 convendría solo si la USM no necesitara métricas.

## Bonus: identificadores únicos en un ambiente distribuido

El hash es la codificación base62 del id, que es inyectiva. El problema se reduce entonces a que
el id sea único: si dos nodos nunca entregan el mismo id, nunca habrá dos hashes iguales.


| Estrategia              | Cómo funciona                                                                                | Costo                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Secuencia centralizada  | Todos los nodos piden el siguiente id a un servicio único (secuencia de DB, `INCR` de Redis) | Una llamada de red por URL creada y un punto único de falla                          |
| Asignación de rangos    | El servicio central entrega bloques de ids; cada nodo asigna los de su bloque localmente     | Ids no consecutivos en el tiempo; se pierden los de un bloque si el nodo se reinicia |
| Secuencias intercaladas | Con N nodos, el nodo k parte en `inicio + k` y avanza de N en N                              | El número de nodos queda fijo                                                        |
| Tipo Snowflake          | Entero de 64 bits con timestamp, id de nodo y contador local                                 | Depende de los relojes; hasta 11 caracteres en base62 en vez de 5                    |
| UUID                    | Valor aleatorio de 128 bits, sin coordinación                                                | Unicidad probabilística; 22 caracteres en base62                                     |


La estrategia elegida es la asignación de rangos: mantiene la unicidad exacta, respeta el id inicial
`597652313`, conserva los hashes cortos y no agrega una llamada de red a cada creación. Un nodo
reservaría, por ejemplo, `[597652313, 597653312]` y el siguiente `[597653313, 597654312]`, y
seguirían operando aunque el servicio central se caiga mientras les queden ids.