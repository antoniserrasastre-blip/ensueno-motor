# El motor nuevo

Motor de rol por turnos para cualquier mundo: Claude dirige y el motor recuerda y comprueba. El protocolo del director
está en `engine/DIRECTOR.md`.

```
python3 engine/motor.py servir                      el panel: HQ en http://localhost:8800/
python3 engine/motor.py servir --hq                 …y además por el túnel de hq.json, si lo hay
python3 engine/motor.py nueva partidas/x --mundo mundos/baleares_123
python3 engine/motor.py -p partidas/baleares_1 briefing
python3 -m unittest discover -s engine/tests        los tests
```

- **Núcleo** (`nucleo/`): partida y mundo, tipos, bloque de cambios, reloj, d20, sistemas, cierre, constitución y
  briefing.
- **Panel:**
  - `hq/` es la pantalla de inicio, con las partidas.
  - `panel/` es el panel de una partida del motor nuevo.
  - Las partidas de otros motores, si `hq.json` las tiene, se abren tal cual por un pasillo.
- **Mundos** en `mundos/` y **partidas** en `partidas/`.
- **Copia para regalar:** `python3 engine/motor.py exportar <carpeta>` (sin nada privado; ver LEEME.md en la copia).
