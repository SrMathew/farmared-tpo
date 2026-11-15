<p align="center">
  <img src="./assets/itba_logo.png" height="120"/>
</p>
<h1 align="center">Base de Datos 2</h1>
<h2 align="center">Trabajo Práctico Obligatorio</h2>
<h3 align="center">FarmaRed – Sistema de Gestión de Red de Farmacias</h3>

* Fecha de entrega: 15/11/2026
* Fecha de defensa: 16/11/2026

## Grupo 13

* **62722**: **Cornejo**, Mateo

Trabajo realizado de forma individual, por excepción de la cátedra.

## 📚 Documentos Importantes 📚

En el directorio `docs` se encuentran los siguientes documentos:

* [`TPO_FarmaRed.pdf`](./docs/consigna/TPO_FarmaRed.pdf) - Enunciado del trabajo práctico.
* `Informe.pdf` - Informe de entrega: arquitectura políglota, modelo de datos, estrategia de carga, las 15 consultas, decisiones de consistencia e integridad, limitaciones y conclusiones. Se agrega con la entrega.

## 🧩 Arquitectura 🧩

Sistema de backoffice para FarmaRed S.A., una red de farmacias con droguería propia. Gestiona clientes, sucursales, farmacéuticos, proveedores, catálogo de productos, stock por lote, recetas y ventas, con una arquitectura de **persistencia políglota**. El código está en
**Python 3.12**.

Motor                               | Paradigma   | Rol
------------------------------------|-------------|------------------------------------------
**MongoDB 8** (replica set `rs0`)   | Documentos  | Único sistema de registro: todas las entidades, incluido el stock por lote
**Redis 7.4**                       | Clave-valor | Datos derivados de MongoDB: caché del catálogo, ranking de productos y claves de idempotencia


## 🌐 Servicios 🌐

El proyecto corre dentro de un dev container formado por tres servicios. Los motores no
publican puertos en la máquina anfitriona: se acceden desde el contenedor `app` por nombre
de host, y VS Code reenvía los puertos cuando hace falta.

Servicio | Imagen                              | Host    | Puerto
---------|-------------------------------------|---------|--------
`app`    | Python 3.12 (dev container)         | —       | —
`mongo`  | `mongo:8.0`, replica set `rs0`      | `mongo` | 27017
`redis`  | `redis:7.4`, persistencia AOF       | `redis` | 6379

## 🛠️ Construcción y Ejecución 🛠️

El proyecto se ejecuta **solo dentro de su dev container**. No hace falta instalar Python ni
los motores en tu máquina. Hay dos formas de abrirlo, y en las dos los comandos son los
mismos.

### GitHub Codespaces

1. En el repositorio de GitHub: **Code → Codespaces → Create codespace on main**.
   Desde VS Code: `Cmd/Ctrl+Shift+P` → *Codespaces: Create New Codespace*.
2. Esperar a que termine la creación (de 3 a 5 minutos la primera vez). Al terminar, las
   dependencias ya están instaladas.
3. Al terminar de trabajar, detener el Codespace para no consumir horas:
   `Cmd/Ctrl+Shift+P` → *Codespaces: Stop Current Codespace*.

### Docker local

Requisitos: [Git](https://git-scm.com/downloads),
[Docker Desktop](https://www.docker.com/products/docker-desktop/) y
[VS Code](https://code.visualstudio.com/) con la extensión *Dev Containers*.

1. Clonar el repositorio y abrir la carpeta en VS Code.
2. `Cmd/Ctrl+Shift+P` → *Dev Containers: Reopen in Container*.

### Verificar el entorno

En la terminal del dev container:

```bash
make check
```

Tiene que mostrar:

```
MongoDB: OK (replica set: rs0)
Redis:   OK
```

## 📥 Carga de Datos 📥

En la terminal del dev container:

```bash
make load
```

La carga es la migración del sistema anterior. Lee dos carpetas:

Carpeta        | Contenido
---------------|------------------------------------------------------------------
`data/given/`  | Los 9 datasets CSV provistos por la cátedra, sin modificar
`data/added/`  | Los registros adicionales propios: 10 o más por dataset, con IDs desde 101

Antes de escribir valida todos los datos contra las reglas de negocio (claves foráneas,
condición de venta, dispensas de las recetas, totales, sucursales, stock). Si alguna regla
no se cumple, muestra todos los problemas, no escribe nada y termina con error.

La carga es **reproducible e idempotente**: vacía las colecciones de MongoDB y les aplica sus
validadores e índices, así que ejecutarla otra vez deja exactamente el mismo estado. También
borra los datos derivados de Redis, que se regeneran a partir de MongoDB.

Los registros adicionales usan fechas relativas a la fecha del sistema (`HOY-30`, `HOY+90`),
para que sus casos borde (lotes por vencer, recetas atrasadas, ventas del mes) sigan siendo
válidos cualquier día en que se ejecute la carga.

Al terminar informa cuántos documentos cargó por colección y tres observaciones sobre los
datos de la cátedra, que se cargan tal cual:

* `V001` fue registrada por `F004` y `V014` incluye `PRD012`, que hoy están inactivos. Los
  datos no traen fecha de baja, así que no se puede saber si lo estaban el día de la venta.
* En `RC002` la próxima dispensa está a 31 días de la última, y no a 30.

## 🔎 Consultas 🔎

Cada consulta se ejecuta desde la terminal del dev container, después de `make load`:

```bash
python -m farmared <consulta> [parámetros]
```

El resultado se imprime en formato JSON. Cada consulta está en su propio módulo dentro de
`farmared/services/`, y su sentencia de MongoDB está en `farmared/adapters/mongo/queries.py`.

\#  | Consulta | Comando | Motor | Módulo
----|----------|---------|-------|-------
1   | Productos activos con todos los datos de su proveedor | `python -m farmared q01` | MongoDB + Redis (caché) | [`q01_active_products_with_supplier.py`](./farmared/services/q01_active_products_with_supplier.py)
2   | Ventas en estado "Pendiente" con su farmacéutico (nombre, matrícula y sucursal) y el total | `python -m farmared q02` | MongoDB | [`q02_pending_sales.py`](./farmared/services/q02_pending_sales.py)
3   | Historial completo de un cliente: ventas y recetas en orden cronológico | `python -m farmared q03 C006` | MongoDB | [`q03_customer_history.py`](./farmared/services/q03_customer_history.py)
4   | Clientes con más de una receta, indicando la cantidad | `python -m farmared q04` | MongoDB | [`q04_customers_with_several_prescriptions.py`](./farmared/services/q04_customers_with_several_prescriptions.py)

`q01` responde desde la caché de Redis cuando existe (el campo `origen` del resultado indica
de dónde salió la respuesta). Con `--no-cache` lee siempre de MongoDB.

Las consultas 5 a 15 se agregan en los próximos commits.

## 🧪 Tests y Calidad 🧪

Comando                 | Qué hace
------------------------|------------------------------------------------------
`make help`             | Lista los comandos disponibles
`make check`            | Verifica que MongoDB (replica set) y Redis respondan
`make load`             | Valida y carga los datasets en MongoDB
`make test`             | Corre todos los tests
`make test-unit`        | Corre los tests que no necesitan los motores
`make test-integration` | Corre los tests contra MongoDB y Redis
`make lint`             | Revisa el estilo y el formato del código con ruff
`make format`           | Corrige el estilo y formatea el código
`make typecheck`        | Revisa los tipos con mypy

## 📁 Estructura del Repositorio 📁

```
.devcontainer/   Definición del entorno: contenedores app, mongo y redis
assets/          Imágenes del README
data/given/      Datasets CSV provistos por la cátedra
data/added/      Registros adicionales propios
docs/            Enunciado e informe
farmared/        Paquete Python del sistema
farmared/services/  Un módulo por consulta (q01 a q15)
scripts/         Puntos de entrada ejecutables: check_environment.py y load_data.py
tests/           Tests (pytest)
pyproject.toml   Dependencias y configuración de las herramientas
Makefile         Atajos para los comandos habituales
```
