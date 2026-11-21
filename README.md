# Tarea 2 - INF326 Arquitectura de Software

URL shortener implementado con dos arquitecturas sobre LiteStar.

## Integrantes


| Nombre         | Rol         |
| -------------- | ----------- |
| Badir Villegas | 202273020-K |
| Yohanns Jara | 201830035-7 |

## Qué contiene


|                | Arquitectura 1                              | Arquitectura 2                     |
| -------------- | ------------------------------------------- | ---------------------------------- |
| Carpeta        | `arch1/`                                    | `arch2/`                           |
| Redirección    | 302 (temporal)                              | 301 (permanente)                   |
| Adicional      | Evento "url hit" por gRPC a un servicio Log | Rate limiter y caché de respuestas |
| Bases de datos | Shortener DB y Log DB                       | Shortener DB                       |
| Puerto HTTPS   | 8443                                        | 8444                               |


```text
common/               Código compartido: repositorio <id, hash, long_url>, validación de URL,
                      endpoint POST y arranque HTTPS
arch1/proto/          Contrato gRPC (url_hit.proto) y stubs generados
arch1/log_service/    Componente Log: servidor gRPC + Log DB
arch1/shortener/      Shortener v1: endpoints HTTP + cliente gRPC
arch2/shortener/      Shortener v2: endpoints HTTP + rate limiter + caché
scripts/              Generación de certificados y de stubs gRPC
Discussion.md         Discusión de trade-offs y bonus
```



## Pre-requisitos

- Python 3.11 (probado con Python 3.11.9 en Windows).
- `curl` para probar los endpoints (en Windows viene incluido como `curl.exe`).

No se necesita Docker, `openssl` ni un motor de base de datos externo.

## Instalación

Los comandos de este documento son para Windows PowerShell.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/gen_certs.py
```

`scripts/gen_certs.py` crea `certs/cert.pem` y `certs/key.pem`, un certificado autofirmado
para `localhost` que usan ambas arquitecturas. Si PowerShell bloquea `Activate.ps1`, se puede
omitir la activación y reemplazar `python` por `.\.venv\Scripts\python.exe` en todos los comandos.

## Ejecución

Todos los comandos se ejecutan desde la raíz del repositorio.

### Arquitectura 1

Requiere dos terminales, una por componente:

```powershell
python -m arch1.log_service     # Terminal 1: Log gRPC en 127.0.0.1:50051
python -m arch1.shortener       # Terminal 2: Shortener v1 en https://localhost:8443
```



### Arquitectura 2

```powershell
python -m arch2.shortener       # Shortener v2 en https://localhost:8444
```

 Nota: Ambas arquitecturas pueden estar levantadas al mismo tiempo; cada una usa su propia base de datos.

## Uso

Los ejemplos usan el puerto 8443 (arquitectura 1). Para la arquitectura 2 basta cambiarlo por 8444.
La opción `-k` hace que `curl` acepte el certificado autofirmado. Se usa `curl.exe` porque en
Windows PowerShell `curl` a secas es un alias de otro comando.

En PowerShell 7.7.0, usa `ConvertTo-Json` para generar el cuerpo y envíalo por la entrada
estándar de `curl.exe`. Así el JSON conserva las comillas de sus claves y valores.

```powershell
@{ url = 'usm.cl/informatica/postulaciones-a-postgrado/2025/magiste-en-ingenieria-informatica/' } |
    ConvertTo-Json -Compress |
    curl.exe -k -i 'https://localhost:8443/shorten' -H 'Content-Type: application/json' --data-binary '@-'
```

Respuesta (`201 Created`):

```json
{
  "short_url": "https://localhost:8443/eRgfR",
  "hash": "eRgfR",
  "long_url": "https://usm.cl/informatica/postulaciones-a-postgrado/2025/magiste-en-ingenieria-informatica/"
}
```

Visitar la URL corta y ver la redirección sin seguirla:

```powershell
curl.exe -k -i https://localhost:8443/eRgfR
```

- Arquitectura 1 responde `302 Found`, y el servicio Log imprime el hit y lo guarda en la Log DB.
- Arquitectura 2 responde `301 Moved Permanently` e incluye los headers `RateLimit-*`. Al superar
el límite responde `429 Too Many Requests`.

En el navegador también se puede abrir `https://localhost:8443/eRgfR` (hay que aceptar la
advertencia del certificado) y la documentación interactiva en `https://localhost:8443/schema`.

### Endpoints


| Método | Ruta                                 | Respuesta                                                                         |
| ------ | ------------------------------------ | --------------------------------------------------------------------------------- |
| `POST` | `/shorten` con body `{"url": "..."}` | `201` con la URL corta; `400` si la URL no es válida                              |
| `GET`  | `/{hash}`                            | `302` (arq. 1) o `301` (arq. 2) hacia la URL original; `404` si el hash no existe |




### Configuración

Todo tiene valores por defecto; se puede cambiar con variables de entorno.


| Variable                | Componente        | Por defecto                                          |
| ----------------------- | ----------------- | ---------------------------------------------------- |
| `SHORTENER_HOST`        | Shortener v1 y v2 | `127.0.0.1`                                          |
| `SHORTENER_PORT`        | Shortener v1 y v2 | `8443` (v1), `8444` (v2)                             |
| `SHORTENER_DB`          | Shortener v1 y v2 | `data/arch1/shortener.db`, `data/arch2/shortener.db` |
| `LOG_GRPC_TARGET`       | Shortener v1      | `127.0.0.1:50051`                                    |
| `LOG_GRPC_ADDRESS`      | Log               | `127.0.0.1:50051`                                    |
| `LOG_DB`                | Log               | `data/arch1/log.db`                                  |
| `RATE_LIMIT_PER_MINUTE` | Shortener v2      | `60`                                                 |
| `CACHE_TTL_SECONDS`     | Shortener v2      | `300`                                                |


Para ver el rate limiter en acción con pocas peticiones, levantar la arquitectura 2 con un límite
bajo: `$env:RATE_LIMIT_PER_MINUTE = "5"; python -m arch2.shortener`.

### Revisar las bases de datos

Las bases de datos son archivos SQLite que se crean solos en `data/` al primer arranque:

```powershell
python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/arch1/shortener.db').execute('select * from urls')]"
python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/arch1/log.db').execute('select * from url_hits')]"
```



## Cómo verificar cada requisito

Los pasos asumen bases de datos nuevas, de modo que el primer hash generado sea `eRgfR`. Si ya se
crearon URLs antes, basta usar el hash que devuelva el POST, o borrar la carpeta `data/` con los
servicios detenidos para partir de cero.

### Arquitectura 1

Con el Log y el Shortener v1 levantados, en una tercera terminal:

1. Crear una URL corta con el POST de la sección [Uso](#uso). La respuesta trae el hash `eRgfR`,
  que es `597652313` en base62.
2. Visitarla dos veces y comprobar el código 302:
  ```powershell
   curl.exe -k -i https://localhost:8443/eRgfR
   curl.exe -k -i https://localhost:8443/eRgfR
  ```
   Cada respuesta es `HTTP/1.1 302 Found` con el header `location` apuntando a la URL original.
   En la terminal del Log aparece una línea `hit <timestamp> <url corta> -> <url original>` por
   cada visita.
3. Comprobar el id inicial y que los hits quedaron guardados:
  ```powershell
   python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/arch1/shortener.db').execute('select * from urls')]"
   python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/arch1/log.db').execute('select * from url_hits')]"
  ```
   La primera muestra la tupla `(597652313, 'eRgfR', <url original>)`. La segunda muestra una fila
   por visita, con su timestamp y ambas URLs.
4. Comprobar que el certificado es autofirmado: el mismo GET sin `-k` falla con un error de
  certificado no confiable.
5. Opcional: detener el Log con `Ctrl+C` y repetir el GET. La respuesta sigue siendo 302 y, unos
  2 segundos después, la terminal del Shortener muestra la advertencia
   `No se pudo registrar el hit`.



### Arquitectura 2

1. Levantar el Shortener v2 con un límite bajo, para ver el rate limiter con pocas peticiones:
  ```powershell
   $env:RATE_LIMIT_PER_MINUTE = "5"; python -m arch2.shortener
  ```
2. En otra terminal, crear una URL corta con el POST de la sección [Uso](#uso), usando el puerto
  1. La respuesta incluye los headers `ratelimit-limit: 5` y `ratelimit-remaining: 4`.
3. Hacer 6 visitas seguidas:
  ```powershell
   1..6 | ForEach-Object { curl.exe -k -s -o NUL -w "%{http_code}\n" https://localhost:8444/eRgfR }
  ```
   Se obtiene `301` cuatro veces y luego `429` dos veces: el POST ya había consumido una de las 5
   peticiones del minuto.
4. Ver la respuesta completa. Dentro del mismo minuto es un `429 Too Many Requests` con
  `ratelimit-remaining: 0`; pasado el minuto vuelve a ser `301 Moved Permanently`.
5. Caché del servidor: no se distingue desde fuera, porque la respuesta es la misma venga o no
  del caché. Está configurado en `arch2/shortener/app.py`, con `cache=True` en el handler del
   GET y `ResponseCacheConfig` en la aplicación.
6. Caché del navegador: abrir `https://localhost:8444/eRgfR` dos veces en un navegador. La segunda
  visita no debería aparecer en la terminal del Shortener v2, porque el navegador guardó el 301.



### Resumen


| Requisito                                       | Evidencia                                                        |
| ----------------------------------------------- | ---------------------------------------------------------------- |
| POST devuelve la URL corta                      | Respuesta `201` con `short_url`                                  |
| Id inicial `597652313` y hash base62            | Primer hash `eRgfR` y fila en `shortener.db`                     |
| Arquitectura 1: redirección 302                 | `HTTP/1.1 302 Found` con `location`                              |
| Arquitectura 1: evento gRPC con timestamp y URL | Línea en la terminal del Log y fila en `log.db` por cada visita  |
| Arquitectura 2: redirección 301                 | `HTTP/1.1 301 Moved Permanently` con `location`                  |
| Arquitectura 2: rate limiter                    | Headers `ratelimit-*` y `429` al superar el límite               |
| Arquitectura 2: caché                           | `cache=True` y `ResponseCacheConfig` en `arch2/shortener/app.py` |
| HTTPS en ambas                                  | URLs `https://`; `curl` sin `-k` rechaza el certificado          |




## Consideraciones de la implementación

**Generales**

- El id es autoincremental y parte en `597652313`. El hash es la codificación base62 del id
(con `pybase62`), por lo que el primer hash generado es `eRgfR`. Como la codificación es
inyectiva, ids distintos nunca producen el mismo hash.
- Cada POST crea un registro nuevo, aunque la URL original ya se haya acortado antes.
- Si la URL llega sin esquema (como `usm.cl/...` en el enunciado) se le antepone `https://`. Sin
esquema, el navegador interpretaría el destino como una ruta relativa al acortador. Solo se
aceptan URLs `http` y `https`.
- Se usa SQLite para ambas bases de datos por simplicidad de despliegue. Cada arquitectura tiene
su propia Shortener DB, tal como en los diagramas.
- El certificado es autofirmado: la conexión va cifrada, pero el navegador muestra una advertencia.

**Arquitectura 1**

- El evento "url hit" contiene el timestamp en que se recibió el GET, la URL corta visitada y la
URL original. El contrato está en `arch1/proto/url_hit.proto`.
- El hit se envía después de responder la redirección, para que la latencia del Log no afecte al
usuario. El envío es de mejor esfuerzo: si el Log no responde en 2 segundos, el usuario igual es
redirigido, el hit se pierde y queda una advertencia en la salida del Shortener. Cuando el Log
vuelve, el Shortener se reconecta solo.
- El canal gRPC entre Shortener y Log no usa TLS. Ambos componentes viven en el mismo nodo de
despliegue y el Log solo escucha en `127.0.0.1`, por lo que no es alcanzable desde fuera.
- Los stubs gRPC generados están versionados. Si cambia el `.proto`, se regeneran con
`python scripts/gen_proto.py`.

**Arquitectura 2**

- Rate limiter: `RateLimitMiddleware` de LiteStar, con límite por dirección IP y ventana de un
minuto. Aplica a todas las rutas, incluidas las respuestas servidas desde el caché.
- Caché: caché de respuestas de LiteStar sobre el GET, en memoria, con expiración configurable.
Las redirecciones repetidas se responden sin consultar la DB. Los 404 no se cachean.
- No hace falta invalidar el caché porque los registros nunca se modifican ni se eliminan.
- Tanto el caché como los contadores del rate limiter viven en la memoria del proceso: se pierden
al reiniciar y no se comparten entre instancias.
- `curl` no guarda redirecciones, así que siempre llega al servidor. El efecto del 301 sobre el
caché del navegador se observa abriendo la URL corta en un navegador.

