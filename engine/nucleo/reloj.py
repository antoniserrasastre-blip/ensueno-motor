"""El reloj de dentro: {"dia": n, "hora": 0–23}. El tiempo pasa por tramos que acaban a medianoche: en cada
tramo corre cada_tramo de los sistemas y en cada medianoche, cada_dia. Así un salto de siete días se resuelve
día a día, en orden."""
from . import sistemas as S


def avanzar(ses, horas, sis):
    if horas < 0:
        raise SystemExit("tiempo: no se puede ir hacia atrás")
    r = ses.e["reloj"]
    queda = horas
    while queda > 0:
        tramo = min(queda, 24 - r["hora"])
        for s in sis:
            S.correr(s, "cada_tramo", ses, tramo, r["dia"])
        r["hora"] += tramo
        queda -= tramo
        if r["hora"] >= 24:
            r["hora"] -= 24
            r["dia"] += 1
            for s in sis:
                S.correr(s, "cada_dia", ses, r["dia"])


def texto(r):
    momento = "madrugada" if r["hora"] < 6 else "mañana" if r["hora"] < 13 else "tarde" if r["hora"] < 20 else "noche"
    return f"día {r['dia']}, {r['hora']:02d}:00 ({momento})"
