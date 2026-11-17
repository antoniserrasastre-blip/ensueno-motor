"""El d20, como en D&D 5e: d20 + modificador contra una CD. Ventaja: el mejor de dos; desventaja: el peor.
Un 1 natural es pifia y un 20, maestría. Cada tirada queda en dados.jsonl con un número: el director la cita en
el bloque de cambios y nunca se la inventa."""
import random
import time


def tirar(partida, mod=0, cd=None, ventaja=False, desventaja=False, motivo="", azar=None):
    azar = azar or random.SystemRandom()
    dados = [azar.randint(1, 20)] + ([azar.randint(1, 20)] if ventaja or desventaja else [])
    d20 = max(dados) if ventaja and not desventaja else min(dados) if desventaja and not ventaja else dados[0]
    total = d20 + mod
    resultado = "pifia" if d20 == 1 else "maestria" if d20 == 20 else \
        ("exito" if total >= cd else "fallo") if cd is not None else "tirada"
    previas = (partida.dir / "dados.jsonl").read_text(encoding="utf-8").count("\n") if (partida.dir / "dados.jsonl").exists() else 0
    t = {"n": previas + 1, "dados": dados, "d20": d20, "mod": mod, "total": total, "cd": cd, "resultado": resultado,
         "motivo": motivo, "turno": partida.estado()["turno"] + 1, "cuando": time.strftime("%d-%m-%Y %H:%M")}
    partida.anotar("dados.jsonl", t)
    return t


def texto(t):
    v = f" ({'/'.join(map(str, t['dados']))})" if len(t["dados"]) > 1 else ""
    cd = f" vs CD {t['cd']}" if t["cd"] is not None else ""
    return f"tirada #{t['n']}: d20 {t['d20']}{v} {t['mod']:+d} = {t['total']}{cd} → {t['resultado'].upper()}" + \
        (f" · {t['motivo']}" if t["motivo"] else "")
