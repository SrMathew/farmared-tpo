# FarmaRed – TPO Base de Datos II

Persistencia políglota con **MongoDB 8** (replica set `rs0`) + **Redis 7.4**, código en **Python 3.12**.

## Abrir el entorno (GitHub Codespaces)

1. En GitHub: botón **Code → Codespaces → Create codespace on main**
   (o desde VS Code: `Cmd+Shift+P` → *Codespaces: Create New Codespace*).
2. Esperar el build (3–5 min la primera vez).
3. Verificar los motores en la terminal:

   ```bash
   python scripts/verificar_entorno.py
   redis-cli -h redis ping
   ```

Al terminar, detener el Codespace (github.com/codespaces → … → Stop) para no consumir horas.

## Estructura

- `.devcontainer/` – contenedores `app` (Python), `mongo` y `redis`.
- `data/provistos/` – datasets CSV provistos por la cátedra.
- `docs/` – consigna y documentos de diseño.
