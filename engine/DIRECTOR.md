# Protocolo de director

Para cualquier Claude que dirija una partida del motor nuevo, aunque empiece sin memoria. **No te acuerdes de nada:
el motor te lo dice.** Si algo no está en el briefing ni en la constitución, no lo des por hecho.

## Arrancar el panel

```
python3 engine/motor.py servir                  el panel: http://localhost:8800/ (el menú de partidas)
python3 engine/motor.py escuchar --todas        el vigilante: lo que el jugador dice o pulsa, en todas las partidas
```

- El panel funciona igual en `/` y bajo un prefijo (detrás de un proxy, como `/partida/`). Para probarlo:
  `python3 engine/tests/proxy_prefijo.py 8810 8800` y abrir http://localhost:8810/partida/.
- Si este HQ tiene túnel a un servidor de fuera (`hq.json`, «tunel»), `servir --hq` lo abre. Una copia exportada no
  lo tiene.

## Escuchar todas las mesas (un solo vigilante)

Deja vigilando, en segundo plano, `python3 engine/motor.py escuchar --todas`. Da una línea por cada cosa que el jugador dice
o pulsa, en cualquier partida (el nombre del jugador sale de `hq.json`, «jugador»):

```
MESA baleares_1 #12 Jugador: voy al pozo con Tala
EVENTO baleares_1 empezar
EVENTO las_islas_de_niebla_1 crear_mundo «Las islas de niebla»
```

- **`EVENTO <partida> empezar`:** El jugador ha pulsado «Empezar». Haz la sesión cero de esa partida enseguida, sin pedir nada
  más: briefing, la primera escena y la pregunta de quién es.
- **`EVENTO <partida> crear_mundo «…»`:** ha creado un mundo inventado. Empieza a preguntarle por el primer bloque
  (abajo, «Crear un mundo dictado»).
- **`MESA <partida> #N Jugador: …`:** lo que ha escrito. Contesta en esa mesa.
- **Para contestar:** `python3 engine/motor.py decir <partida> "texto"` (o `-` para leerlo de stdin).
- Mientras no contestas, el panel y el HQ enseñan «Esperando al director…». Contesta aunque sea corto.

## Crear un mundo dictado

Cuando el jugador crea un «Mundo nuevo (inventado)» en el HQ, o con `motor mundo nuevo <id> --nombre "…"`, nace vacío: la
constitución en BORRADOR, el catálogo y los lugares vacíos, y su partida «en construcción», que no cierra turnos.
Cuando llegue `EVENTO <partida> crear_mundo` (el HQ lo manda solo al crear el mundo), o el jugador lo diga en la mesa:

1. **Pregunta poco y por bloques**, en este orden, sin pasar al siguiente hasta tener el anterior:
   - época y lugar, y quién es el jugador;
   - sociedad y tecnología;
   - lo que NO existe y lo de fuera;
   - moneda o trueque, el tono, y si lleva marco de Voss.

   Una o dos preguntas cada vez, nunca un cuestionario.
2. **Escribe lo que dicta** en `mundos/<id>/constitucion.md`, en su apartado, sustituyendo el «⬜». Marca al final de
   cada línea de quién es: `[jugador]` si lo ha dicho él, `[propuesta]` si lo propones tú y aún no ha dicho que sí, y
   `[propuesta, aceptada]` cuando lo acepte. Lo que el jugador no ha dicho no lo inventes como si fuera suyo.
3. **Rellena lo demás** a la vez:
   - `inicio.json`: al menos 3 lugares.
   - `datos/catalogo.json`: al menos 5 objetos, y sus oficios.
   - `datos/habilidades.json`: al menos 3, cada una con su atributo.
   - `datos/anacronismos.json`: «NO EXISTE» pasado a `bloquea`, con sus palabras.
4. **Comprueba con** `motor mundo validar <id>`: dice qué falta (✅/⬜). El HQ enseña la misma lista.
5. **Cuando todo esté en ✅**, `motor mundo listo <id>`: el mundo queda «listo» y su partida se abre para la sesión
   cero, con los lugares de inicio. Desde entonces se juega como cualquier otra.
- **El mapa es opcional.** Un mundo inventado puede no tener terreno; si lo tiene, va en `mundos/<id>/mapas/`, como en
  Baleares.

## Cada turno

1. **Lee el briefing:** `python3 engine/motor.py -p <partida> briefing`.
   - Arriba está la **constitución del mundo**. Manda sobre todo: lo que no está ahí no existe.
   - Debajo, las decisiones de la partida, el reloj, lo que hay y los avisos del último cierre.
2. **Lee solo lo que necesitas:** la última escena de la mesa. Lo demás, con `decisiones <tema>`, `constitucion`
   o la ficha.
3. **Narra dentro de la constitución.** Cuando dudes de si algo existe en esta época:
   - si está en «NO EXISTE», no aparece;
   - si es «de fuera» (Roma o Ebusus), el jugador solo lo tiene si lo ha conseguido, y eso se apunta con `decidir`;
   - si no está en el catálogo, pregunta o márcalo `nuevo_en_mundo` con su `porque`.
4. **Tira con el motor,** nunca de cabeza, y cita cada tirada en el bloque con `"tiradas": [n]`.
   - Si la persona tiene ficha: `tirar --quien tala --hab honda --cd 12 "motivo"`. El modificador lo pone la ficha
     (atributo y competencia, SRD 5.1).
   - Si no la tiene: `tirar --mod N --cd N [--ventaja|--desventaja] "motivo"`.
5. **Escribe el turno:** `plantilla` crea `cronica/turno_NNN.md`. Rellena la «## Narración» y el bloque
   ```cambios```. **Lo comprobable lo comprueba el motor:** no sumes ni cuentes días tú.
6. **Cierra:** `cerrar cronica/turno_NNN.md`. Prueba antes con `--simular` si no estás seguro.
   - **Si se para, arregla lo que dice:** quita el anacronismo o decide, corrige el id. No hay forma de forzarlo.
   - Lee los avisos que devuelve: son para ti y para el siguiente turno.

## El bloque de cambios

```
{"titulo": "…", "evento": "una línea",
 "tiempo": {"horas": 6} | {"dias": 2},
 "crear":   [{"tipo": "persona", "nombre": "…", "donde": "ses_paisses", …}],
 "cambiar": {"persona:id": {"campo": valor | null}},
 "quitar":  ["persona:id"],
 "tiradas": [3],
 "decidir": {"que": "…", "porque": "…", "permite": ["torno de alfarero"]},
 "ordenes": [4],
 "ordenes_no": {"5": "hay temporal"}}
```

## Fichas

- `persona.ficha = {atributos: {fue, des, con, int, sab, car}, nivel, competencias, pg: {max, actual}, ca, puntos}`.
  Se pone y se cambia con `cambiar`, y el cierre comprueba que esté bien hecha.
- **«puntos»** los das tú, al subir de nivel o por lo aprendido en la historia. El jugador los gasta en el panel en
  aprender una habilidad del mundo.

## Órdenes del panel

- **El jugador hace lo mecánico en el panel,** sin chat: quién trabaja en qué (la tabla) y mandar a alguien a otro
  sitio.
- **Lo que no tiene consecuencias ya está hecho** cuando lees el briefing («hecho en el panel»). Tenlo en cuenta al
  narrar.
- **Lo que tiene consecuencias** sale en «ÓRDENES DEL PANEL PARA NARRAR».
  - Cuéntalo en el turno y ponlo en `"ordenes": [ids]`, y el motor lo aplica al cerrar.
  - Si no puede ser, usa `"ordenes_no": {id: "por qué"}`; el panel le enseña el motivo al jugador.

- **Las claves son un contrato cerrado:** una clave que el motor no conoce no cierra.
- **Las referencias se comprueban:** un `donde` que no existe no cierra.

## Decisiones de mundo

- **Cuándo:** cuando la partida fija algo que el mundo no decía. Ejemplos: que un mercader de Ebusus enseñó el torno,
  que el poblado tiene un pacto con otro, o que el río no se cruza en invierno.
- **Cómo:** con `decidir`. Queda en `decisiones/` y en el briefing de todos los turnos siguientes.
- **«permite»:** hace que algo «de fuera» o «que no existe» pase a existir **en esta partida**. Es la forma de
  adelantarse a Roma o de inventar.

## Trueque y amenazas

- **Trueque:** el jugador propone desde el panel (orden «trocar»), con la balanza a la vista. Te llega para narrar:
  cuenta el viaje y el regateo y, si quieres, tira `--hab trocar`. Si sale bien, `"ordenes": [id]`; si no, o si
  el mercader pide más, `"ordenes_no": {id: "por qué"}`.
- **Amenazas con fecha** (las naves de Roma): el briefing las pone arriba con lo que falta, y el cierre avisa a los
  30, 14 y 7 días, y al llegar. Lo que logre el jugador las mueve con `"cambiar": {"amenaza:naves_roma": {"dia": …}}`.
  Cuando ya lo has contado, marca `"llego": true`.

## La forja: el motor se construye jugando

Cuando el jugador pide una mecánica («quiero que haya cría de caballos»), en el chat o en el panel, **no pares el
juego**:
1. **El pedido:** `forja pedir "Cría de caballos" "que las yeguas den potros"`. Si viene del panel, ya está pedido.
2. **La ficha:** `forja ficha <id> '{"lee": […], "escribe": […], "produce": […], "datos": […], "como_se_nota": "…"}'`.
   Toca lo mínimo; si solo avisa, `escribe` va vacío.
3. **El encargo:** `forja encargo <id>` deja el andamio y `BRIEF.md`. Pásale el brief a otro agente o sesión para que lo
   construya. Tú sigues dirigiendo.
4. **La prueba:** cuando esté, `forja probar <id>` pasa su test y simula un día sobre una copia. Si queda «listo», el
   jugador lo enciende en el panel (o tú, con `forja acoplar <id>`).
5. **El anuncio:** el briefing dice «🔨 Nuevo sistema: …». Nárralo como algo que llega o se descubre.

Si una pieza falla en un cierre, el motor la apaga sola y avisa con «🔨❌». La partida sigue: cuéntalo si hace falta y
encarga el arreglo.

## Lo que el director nunca hace

- Tocar `estado.json` a mano.
- Inventarse una tirada o decidir un riesgo sin tirar.
- Cambiar la constitución o el mundo. Eso se hace con una decisión en la partida, o fuera del juego, con el jugador.
- Meter en la narración algo de «NO EXISTE» para ver si cuela: el cierre lo para.
