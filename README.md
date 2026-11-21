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

- Python 3.11 o superior (probado con Python 3.11.9 y 3.15 en Windows).
- `curl` para probar los endpoints (en Windows viene incluido como `curl.exe`).

No se necesita Docker, `openssl` ni un motor de base de datos externo.

## Instalación

Los comandos de este documento son para Windows PowerShell. `py -3 --version` muestra la
versión predeterminada que usará el launcher. Verifica que sea Python 3.11 o superior.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/gen_certs.py
```

Si `py` no encuentra una versión compatible y ya tienes `uv`, crea `.venv` con Python 3.11
y continúa desde `Activate.ps1`.

```powershell
uv python install 3.11
uv venv --managed-python --python 3.11 --seed .venv
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

Si el puerto gRPC `50051` está ocupado, elige un puerto local libre, por ejemplo `50053`.
Configura el mismo puerto en ambas terminales antes de iniciar cada proceso.

**Terminal 1, servicio Log**

```powershell
$env:LOG_GRPC_ADDRESS = "127.0.0.1:50053"
python -m arch1.log_service
```

**Terminal 2, Shortener v1**

```powershell
$env:LOG_GRPC_TARGET = "127.0.0.1:50053"
python -m arch1.shortener
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

Usa el `short_url` devuelto por el POST en cada prueba. En una base de datos nueva, la primera
URL recibe el ID `597652313` y el hash `eRgfR`.

### Arquitectura 1

Con el Log y el Shortener v1 levantados, en una tercera terminal:

1. Crear una URL corta con el POST de la sección [Uso](#uso) en el puerto `8443` y copiar el valor
   de `short_url`.
2. Guardar la URL devuelta en `$shortUrl` y visitarla dos veces.

   ```powershell
   $shortUrl = 'https://localhost:8443/eRgfR' # Reemplaza por el short_url del POST.
   curl.exe -k -i $shortUrl
   curl.exe -k -i $shortUrl
   ```

   Cada respuesta es `HTTP/1.1 302 Found` con `Location` apuntando a la URL original y
   `Cache-Control: no-store`. En la terminal del Log aparece una línea
   `hit <timestamp> <url corta> -> <url original>` por cada visita.
3. Comprobar el registro de la URL y los hits guardados.

   ```powershell
   python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/arch1/shortener.db').execute('select * from urls')]"
   python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/arch1/log.db').execute('select * from url_hits')]"
   ```

   La primera consulta muestra el ID, el hash y la URL original. La segunda muestra una fila por
   hit registrado, con su timestamp y ambas URLs.
4. Repetir el GET sin `-k` para comprobar el certificado. Si el certificado autofirmado no está en
   el almacén de confianza del sistema, la conexión falla.
5. Como prueba opcional, detener el Log con `Ctrl+C` y repetir el GET. La respuesta sigue siendo
   `302` y el Shortener emite la advertencia `No se pudo registrar el hit`.



### Arquitectura 2

1. Levantar el Shortener v2 con un límite de cinco peticiones por minuto.

   ```powershell
   $env:RATE_LIMIT_PER_MINUTE = "5"
   python -m arch2.shortener
   ```

2. En otra terminal, crear una URL corta con el POST de la sección [Uso](#uso) en el puerto `8444`.
   La respuesta incluye `ratelimit-limit: 5` y `ratelimit-remaining: 4` si es la primera petición
   de esa IP en la ventana. Copiar el `short_url` de la respuesta.
3. Guardar la URL devuelta en `$shortUrl` y hacer seis GET seguidos desde la misma IP, dentro de
   la misma ventana que el POST.

   ```powershell
   $shortUrl = 'https://localhost:8444/eRgfR' # Reemplaza por el short_url del POST.
   1..6 | ForEach-Object { curl.exe -k -s -o NUL -w "%{http_code}\n" $shortUrl }
   ```

   El POST consume una de las cinco peticiones. Los cuatro primeros GET devuelven `301` y los
   dos siguientes devuelven `429`.
4. Ejecutar `curl.exe -k -i $shortUrl` para ver los encabezados. Con el cupo agotado, la respuesta
   es `429 Too Many Requests` con `ratelimit-remaining: 0`. Cuando expira la ventana, vuelve a `301`.
5. El caché del servidor está en `arch2/shortener/app.py`, con `cache=True` en el GET y
   `ResponseCacheConfig` en la aplicación. Para comprobarlo, cuenta las llamadas a
   `find_by_hash` al repetir el mismo GET dentro del TTL y con cupo disponible.
6. Para observar el caché del navegador, abre dos veces el `short_url` con el caché habilitado y
   sin recarga forzada. Si el navegador reutiliza el `301`, el Shortener v2 recibe solo la primera
   petición.



### Resumen


| Requisito                                       | Evidencia                                                        |
| ----------------------------------------------- | ---------------------------------------------------------------- |
| POST devuelve la URL corta                      | Respuesta `201` con `short_url`                                  |
| Id inicial `597652313` y hash base62            | Primer hash `eRgfR` y fila en `shortener.db`                     |
| Arquitectura 1: redirección 302                 | `HTTP/1.1 302 Found` con `Location` y `Cache-Control: no-store`  |
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

- El `302` incluye `Cache-Control: no-store` para indicar a navegadores y cachés HTTP
  intermedios que no almacenen la redirección.
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

