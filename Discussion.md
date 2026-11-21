# Discusión de trade-offs

## Comparación


| Atributo                  | Arquitectura 1 (302 + Log gRPC)                     | Arquitectura 2 (301 + rate limiter + caché)             |
| ------------------------- | --------------------------------------------------- | ------------------------------------------------------- |
| Analítica de visitas      | Registra las redirecciones que el Log logra guardar | El acortador solo observa las peticiones que le llegan  |
| Carga sobre el servidor   | Una lectura de DB y un intento gRPC por GET válido  | El navegador evita peticiones y LiteStar evita lecturas |
| Latencia para el usuario  | Incluye el paso por el Shortener                    | El navegador puede reutilizar el 301 que guardó         |
| Control sobre los enlaces | El `302` con `no-store` evita guardar la redirección | Un `301` almacenado puede seguir apuntando al destino anterior |
| Control de arribo         | Sin límite por IP en la aplicación                  | Presupuesto por IP compartido por POST y GET            |
| Complejidad               | Dos procesos, dos bases de datos y un contrato gRPC | Un proceso y una base de datos                          |




## Arquitectura 1

**Gana modificabilidad y observabilidad.** El `302` con `Cache-Control: no-store` pide al navegador
y a los cachés HTTP intermedios que no almacenen la redirección. El Log tiene su propia base de datos,
así que la analítica puede evolucionar de forma independiente mientras se conserve el contrato gRPC.
Cada evento persistido representa una redirección emitida por el Shortener. Para medir visitantes
únicos o confirmaciones de postulación se necesita instrumentación adicional en el destino.
[RFC 9111](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.5)

**Lo paga en desempeño, disponibilidad y complejidad:**

- Cada GET que resuelve un enlace implica una lectura a la base de datos y un intento de envío gRPC.
- La resolución de cada enlace depende de que el Shortener y su base estén disponibles.
- Hay más piezas que desplegar y monitorear, y un contrato entre ellas que mantener.
- No hay control de arribo: una ráfaga de peticiones llega íntegra al Shortener, a la base de
datos y al Log.
- El hit se envía después de responder y su entrega es de mejor esfuerzo. Si el Log está caído,
la redirección sigue funcionando y esos hits se pierden. Si la USM necesita conservarlos durante
una caída, se podría agregar una cola persistente con reintentos y deduplicación de eventos. Eso
suma escrituras, almacenamiento y un componente que operar.



## Arquitectura 2

**Gana desempeño, disponibilidad para enlaces ya cacheados y simplicidad.** Reutilizar un `301`
permite al navegador resolver el enlace corto durante una caída del Shortener, siempre que el destino
siga disponible. LiteStar aplica las dos tácticas del enunciado a las peticiones que llegan al servicio.

- **Controlar arribo de eventos.** El rate limiter de LiteStar acota las peticiones por IP durante
  una ventana de un minuto. El POST y los GET comparten ese presupuesto, incluidos los GET que se
  sirven desde el caché.
- **Mantener múltiples copias de datos.** El caché de respuestas de LiteStar conserva el `301` en
  memoria. Una petición repetida que coincide con una respuesta cacheada evita otra consulta a
  SQLite. El TTL de ese caché se configura en el servidor y es independiente del caché del navegador.

**Lo paga en observabilidad, control y consistencia:**

- El `301` reutilizado por el navegador deja fuera del alcance de la analítica del Shortener las
  peticiones que el navegador resuelve localmente.
- Si se permite editar o retirar enlaces, un `301` guardado puede seguir enviando usuarios al
  destino anterior. Una política HTTP con `max-age` explícito permitiría elegir cuánto tiempo se
  considera fresca la redirección. [RFC 9111](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.1)
- El caché del servidor consume memoria. Si se habilita la edición de enlaces, además habría que
  definir cómo invalidar las redirecciones guardadas en LiteStar.
- Usuarios que comparten una IP pública, por ejemplo detrás del NAT de un campus, también comparten
  el cupo. Una ráfaga de GET puede dejar a esos usuarios sin cupo para crear enlaces durante la ventana.
- Cada instancia mantiene su propio caché y sus contadores. Si se escala a varias instancias, aplicar
  un límite global por IP requeriría compartir los contadores. Los cachés locales pueden seguir
  sirviendo mapeos inmutables a costa de duplicar memoria y consultas iniciales.

## Evidencia del prototipo

- **Arquitectura 1.** Dos GET consecutivos devolvieron `302` y produjeron dos filas en la base del
  Log. Con el Log detenido, el siguiente GET conservó el `302` y no agregó una fila.
- **Arquitectura 2.** Con un límite de cinco peticiones por minuto desde la misma IP, un POST dejó
  cuatro peticiones disponibles. Cuatro GET consecutivos al mismo enlace devolvieron `301` y en total
  hicieron una consulta a SQLite. Los dos GET siguientes devolvieron `429`.

## ¿Son de consideración en este dominio?

En este prototipo los mapeos son pequeños e inmutables. Si la USM espera muchas más visitas que
creaciones de enlaces, el peso de cada trade-off depende de dos preguntas.

**¿Qué debe medir la USM?** Si una campaña de admisión necesita contar los accesos al enlace corto,
elegiría la arquitectura 1. Cada visita que consulta el Shortener ofrece una oportunidad de registrar
el hit. Si basta con medir postulaciones en el sitio de destino, se puede evaluar la arquitectura 2
y mantener esa medición en el sistema de postulaciones.

**¿Cuánto tráfico se espera?** Para enlaces públicos y estables que concentren muchas visitas, como
una guía de postulación difundida durante un proceso de admisión, elegiría la arquitectura 2 si la
USM prioriza descargar al acortador y no necesita un hit por acceso. Validaría con la universidad el
volumen esperado, la proporción de clientes detrás de IP compartidas y la pérdida de eventos que
puede aceptar por campaña.

Si la USM necesita contar accesos y reducir lecturas durante un pico, se puede conservar el `302`
de la arquitectura 1 y cachear el mapeo `hash → URL` dentro del Shortener. Cada GET sigue construyendo
su propia respuesta y emitiendo su evento. También se podría incorporar el rate limiter con un cupo
ajustado al tráfico compartido del campus.

## Bonus: identificadores únicos en un ambiente distribuido

El hash es la codificación base62 del id, que es inyectiva. El problema se reduce entonces a que
el id sea único: si dos nodos nunca entregan el mismo id, nunca habrá dos hashes iguales.


| Estrategia              | Cómo funciona                                                                                | Costo                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Secuencia centralizada  | Todos los nodos piden el siguiente id a un servicio único (secuencia de DB, `INCR` de Redis) | Una llamada de red por URL creada y un punto único de falla                          |
| Asignación de rangos    | El servicio central entrega bloques de ids; cada nodo asigna los de su bloque localmente     | Puede haber saltos si se descartan los IDs sin usar de un bloque                    |
| Secuencias intercaladas | Con N nodos, el nodo k parte en `inicio + k` y avanza de N en N                              | El número de nodos queda fijo                                                        |
| Tipo Snowflake          | Entero de 64 bits con timestamp, id de nodo y contador local                                 | Depende de los relojes; hasta 11 caracteres en base62 en vez de 5                    |
| UUID                    | Valor aleatorio de 128 bits, sin coordinación                                                | Unicidad probabilística; 22 caracteres en base62                                     |


La estrategia elegida es la asignación de rangos: mantiene la unicidad exacta, respeta el id inicial
`597652313`, conserva los hashes cortos y no agrega una llamada de red a cada creación. Un nodo
reservaría, por ejemplo, `[597652313, 597653312]` y el siguiente `[597653313, 597654312]`, y
seguirían operando aunque el servicio central se caiga mientras les queden ids.

El asignador mantiene el próximo ID en almacenamiento persistente. Reserva cada bloque con una
transacción atómica que avanza el contador y confirma la reserva antes de entregarla al nodo. Si un
nodo se pierde y se desconoce qué IDs alcanzó a usar, el bloque se descarta. Esta regla impide que
otro nodo reutilice un ID ya emitido, a costa de dejar huecos. Si el requisito cambiara a una secuencia
global sin huecos, habría que coordinar la asignación del ID y el alta del enlace en una transacción
central por creación.

Los códigos base62 de IDs consecutivos son predecibles. Para enlaces que deban ser privados, el
acceso al destino debe depender de la autorización del usuario, aunque se conozca el código corto.
