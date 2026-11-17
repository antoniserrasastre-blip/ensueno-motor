"""Ánimo: el de cada persona de los tuyos sale de lo que le pasa (datos/animo.json): el hambre, el tiempo, si hace
lo que sabe hacer y los motivos que pone el director (persona.motivos: [{que, valor, hasta?}]). Se guarda en
persona.animo (−10 a 10) con sus motivos, para que el director y el panel vean por qué. Muy bajo, avisa: es una
escena para el director, no un castigo automático."""
NOMBRE = "animo"
LEE = ["personas", "reloj"]
ESCRIBE = ["personas"]
PRODUCE = ["aviso:animo"]
DATOS = ["animo"]


def al_cerrar(s):
    A = s.datos["animo"]
    clima = (s.e["reloj"].get("clima") or {}).get("tiempo")
    for p in s.col.get("personas", {}).values():
        if not p.get("tuyo"):
            continue
        motivos = []
        if p.get("hambre"):
            motivos.append(["tiene hambre", A["hambre_por_dia"] * min(p["hambre"], 5)])
        if clima in A.get("clima", {}):
            motivos.append([f"el tiempo ({clima})", A["clima"][clima]])
        primero = min((p.get("trabajos") or {}).items(), key=lambda kv: kv[1], default=(None, 0))[0]
        hab = (s.datos.get("produccion") or {}).get(primero, {}).get("habilidad")
        if hab and hab in (p.get("ficha") or {}).get("competencias", []):
            motivos.append(["hace lo que sabe hacer", A.get("hace_lo_suyo", 1)])
        motivos += [[m["que"], m["valor"]] for m in p.get("motivos", []) if m.get("hasta", 10 ** 9) >= s.e["reloj"]["dia"]]
        p["animo"] = max(-10, min(10, A.get("base", 0) + sum(v for _, v in motivos)))
        p["animo_motivos"] = motivos
        if p["animo"] <= A.get("crisis", -5):
            s.inc.setdefault("crisis", []).append(p["nombre"])


def informe(s):
    return [f"😣 {n} está muy mal de ánimo: una escena para el director" for n in s.inc.get("crisis", [])]
