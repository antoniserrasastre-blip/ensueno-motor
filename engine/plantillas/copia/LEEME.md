# EnSueño · motor de rol con Claude de director

Un juego de rol por turnos en el navegador. **Tu Claude es el director**: narra, tira los dados y lleva el mundo; el
motor lo recuerda todo y comprueba que nada se salga de la época.

## Empezar (una vez)

1. Necesitas **Python 3** (sin instalar nada más) y **Claude Code**.
2. Abre Claude Code en esta carpeta y dile: **«Arranca el juego»**. Él pone en marcha el panel y se queda escuchando.
3. Abre **http://localhost:8800/** en el navegador.

## Jugar

- **Partida nueva:** elige un mundo (viene *Baleares, 123 a. C.*) y pulsa **Empezar**. El director empieza solo.
- **Mundo nuevo:** inventa el tuyo: pones el nombre, pulsas y le dictas el lore al director en la mesa.
- En cada partida, la **mesa** es el chat con el director. Lo mecánico (quién trabaja en qué, trueques, fichas)
  se hace en el panel, sin chat.

Todo se guarda en `partidas/` y `mundos/`. Para empezar de cero, borra la partida de `partidas/`.
