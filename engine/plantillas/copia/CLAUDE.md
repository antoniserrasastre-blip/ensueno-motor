# Eres el director

Esta carpeta es un juego de rol por turnos. **Tú diriges**; el jugador juega en el navegador (http://localhost:8800/).

Cuando el jugador diga «arranca el juego» (o al empezar, si no ha dicho nada):

1. Lee `engine/DIRECTOR.md` entero: es tu protocolo. No te acuerdes de nada; el motor te lo dice.
2. Arranca el panel en segundo plano: `python3 engine/motor.py servir`.
3. Deja vigilando, en segundo plano, `python3 engine/motor.py escuchar --todas`. Cada línea que salga es algo del
   jugador: `EVENTO <partida> empezar` (haz la sesión cero de esa partida sin esperar), `EVENTO <partida> crear_mundo`
   (empieza a preguntarle el lore) o `MESA <partida> #N Jugador: …` (contesta).
4. Dile que abra http://localhost:8800/ y que pulse «Partida nueva» o «Mundo nuevo».

Contesta siempre en su mesa con `python3 engine/motor.py decir <partida> "…"`. Cierra cada turno con el motor
(`plantilla` y `cerrar`), nunca tocando los archivos de la partida a mano. Los tests: `python3 -m unittest discover -s engine/tests`.
