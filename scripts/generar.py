#!/usr/bin/env python3
"""Genera las paginas de calendario laboral (HTML de entrada para Blogger),
la imagen PNG y el PDF de cada URL, y su ficha de datos para los chequeos.

Determinista: todo texto con cifras sale de data/es/festivos-AAAA.json.
Uso: python scripts/generar.py 2027
"""
import calendar
import csv
import html
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "out"
IMG = RAIZ / "docs" / "img"  # GitHub Pages sirve /docs
TEMPLATE_VERSION = "4"
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
FUENTE_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FUENTE_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
COL = {"nacional": (176, 39, 47), "autonómica": (224, 140, 20), "fin": (120, 128, 124), "txt": (30, 42, 36)}


def fecha_larga(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]}"


def tipo(marca):
    return "autonómica" if marca == "***" else "nacional"


def datos_region(base, clave, cfg, regiones):
    """Ficha de datos de una URL: todo lo que la pagina puede afirmar."""
    anio = base["anio"]
    if clave == "ES":
        comunes = [f for f in base["fiestas"] if len(f["marcas"]) == len(base["regiones"])
                   and set(f["marcas"].values()) == {"*"}]
        fiestas = [{"fecha": f["fecha"], "nombre": f["nombre"], "tipo": "nacional"} for f in comunes]
        meta = {"nombre": "España", "slug": "espana", "vecinos": [r["slug"] for r in regiones.values()]}
    else:
        fiestas = [{"fecha": f["fecha"], "nombre": f["nombre"], "tipo": tipo(f["marcas"][clave])}
                   for f in base["fiestas"] if clave in f["marcas"]]
        meta = regiones[clave]
    meses = meses_de(anio, {f["fecha"] for f in fiestas})
    puentes = calcular_puentes(anio, {f["fecha"]: f["nombre"] for f in fiestas})
    clave_de = {r["slug"]: k for k, r in regiones.items()}
    def fechas_de(k):
        return {f["fecha"]: f["nombre"] for f in base["fiestas"] if k in f["marcas"]}
    diferencias = []
    if clave != "ES":
        mias = fechas_de(clave)
        for vs in meta["vecinos"][:4]:
            suyas = fechas_de(clave_de[vs])
            diferencias.append({"vecina": regiones[clave_de[vs]]["nombre"], "slug": vs,
                                "solo_aqui": sorted((f, mias[f]) for f in set(mias) - set(suyas)),
                                "solo_alli": sorted((f, suyas[f]) for f in set(suyas) - set(mias))})
    totales = {r["slug"]: sum(1 for f in base["fiestas"] if k in f["marcas"]) for k, r in regiones.items()}
    propias_slug = {r["slug"]: [[f["fecha"], f["nombre"]] for f in base["fiestas"] if f["marcas"].get(k) == "***"] for k, r in regiones.items()}
    totales_es = sum(1 for f in base["fiestas"] if len(f["marcas"]) == len(base["regiones"]) and set(f["marcas"].values()) == {"*"})
    por_comunidad = {}
    if clave == "ES":
        por_comunidad = {r["nombre"]: [[f["fecha"], f["nombre"]] for f in base["fiestas"] if f["marcas"].get(k) == "***"]
                         for k, r in regiones.items()}
    extras = {}
    nota = (base.get("notas") or {}).get(clave)
    if nota:
        extras = nota
    fuente = base["fuente"]
    return {
        "anio": anio, "clave": clave, "region": meta["nombre"], "slug": meta["slug"], "vecinos": meta["vecinos"],
        "fiestas": fiestas, "total": len(fiestas),
        "nacionales": sum(f["tipo"] == "nacional" for f in fiestas),
        "autonomicas": sum(f["tipo"] == "autonómica" for f in fiestas),
        "locales_por_municipio": 2, "maximo_legal": 14,
        "entre_semana": sum(date.fromisoformat(f["fecha"]).weekday() < 5 for f in fiestas),
        "en_sabado": [f["fecha"] for f in fiestas if date.fromisoformat(f["fecha"]).weekday() == 5],
        "meses": meses, "laborables_anio": sum(m["laborables"] for m in meses),
        "puentes": puentes, "nota": extras, "fuente": fuente,
        "diferencias": diferencias, "por_comunidad": por_comunidad, "totales": totales, "totales_es": totales_es, "propias_slug": propias_slug,
        "sitio": cfg["sitio"], "assets": cfg["assets"],
    }


def meses_de(anio, festivo_set):
    meses = []
    for m in range(1, 13):
        dias_mes = calendar.monthrange(anio, m)[1]
        habiles = [date(anio, m, d) for d in range(1, dias_mes + 1) if date(anio, m, d).weekday() < 5]
        fest_sem = [d for d in habiles if d.isoformat() in festivo_set]
        meses.append({"mes": m, "laborables": len(habiles) - len(fest_sem), "festivos_entre_semana": len(fest_sem)})
    return meses


def nombre_pag(m):
    """Nombre del municipio en titulos: Murcia municipio se distingue de la Region."""
    return "Murcia capital" if m["slug"] == "murcia-capital" else m["nombre"]


def dia_fecha(iso):
    return f"{DIAS[date.fromisoformat(iso).weekday()]} {fecha_larga(iso)}"


def datos_municipio(base, cfg, regiones, loc, m, sin_pagina=()):
    """Ficha de un municipio: festivos de su comunidad mas sus 2 fiestas locales del boletin autonomico."""
    d = datos_region(base, loc["region_clave"], cfg, regiones)
    anio = d["anio"]
    regionales = d["fiestas"]
    choque = {f["fecha"] for f in regionales} & set(m["fechas"])
    assert not choque, f"{m['nombre']}: fiesta local que coincide con una regional {choque}"
    fiestas = sorted(regionales + [{"fecha": x, "nombre": "Fiesta local", "tipo": "local"} for x in m["fechas"]], key=lambda f: f["fecha"])
    otros = [o for o in loc["municipios"] if o["slug"] != m["slug"]]
    comparten = [{"fecha": x, "municipios": [[o["slug"], nombre_pag(o)] for o in otros if x in o["fechas"]]} for x in m["fechas"]]
    # Mosaico: primero los que comparten fecha, luego los vecinos en orden alfabetico del boletin
    elegidos = []
    for c in comparten:
        for s_, _ in c["municipios"]:
            if s_ not in elegidos and s_ not in sin_pagina:
                elegidos.append(s_)
    i = next(k for k, o in enumerate(loc["municipios"]) if o["slug"] == m["slug"])
    n = len(loc["municipios"])
    for paso in range(1, n):
        for k in (i + paso, i - paso):
            s_ = loc["municipios"][k % n]["slug"]
            if s_ != m["slug"] and s_ not in elegidos and s_ not in sin_pagina:
                elegidos.append(s_)
    por_slug = {o["slug"]: o for o in loc["municipios"]}
    mosaico = [{"slug": s_, "nombre": nombre_pag(por_slug[s_]), "fechas": por_slug[s_]["fechas"],
                "comunes": sorted(set(por_slug[s_]["fechas"]) & set(m["fechas"]))} for s_ in elegidos[:6]]
    meses = meses_de(anio, {f["fecha"] for f in fiestas})
    d.update({
        "clave": "MU:" + m["slug"], "region": nombre_pag(m), "slug": m["slug"], "municipio_borm": m["borm"],
        "comunidad": loc["region_nombre"], "comunidad_slug": loc["region_slug"], "vecinos": [],
        "fiestas": fiestas, "total": len(fiestas), "regionales": len(regionales), "locales": m["fechas"],
        "nacionales": sum(f["tipo"] == "nacional" for f in fiestas), "autonomicas": sum(f["tipo"] == "autonómica" for f in fiestas),
        "entre_semana": sum(date.fromisoformat(f["fecha"]).weekday() < 5 for f in fiestas),
        "en_sabado": [f["fecha"] for f in fiestas if date.fromisoformat(f["fecha"]).weekday() == 5],
        "meses": meses, "laborables_anio": sum(x["laborables"] for x in meses),
        "laborables_region": d["laborables_anio"],
        "puentes": calcular_puentes(anio, {f["fecha"]: f["nombre"] for f in fiestas}),
        "nota": {}, "diferencias": [], "por_comunidad": {}, "totales": {}, "propias_slug": {},
        "comparten": comparten, "mosaico": mosaico,
        "gemelos": [nombre_pag(o) for o in otros if sorted(o["fechas"]) == sorted(m["fechas"])], "fuente_local": loc["fuente"],
        "miga": [[f"calendario-laboral-{anio}-{loc['region_slug']}", loc["region_nombre"]], [None, nombre_pag(m)]],
    })
    return d


def calcular_puentes(anio, festivos):
    """Bloques de 3 o mas dias libres con algun festivo, y dias laborables sueltos que los unen (puentes)."""
    libre = lambda d: d.weekday() >= 5 or d.isoformat() in festivos
    ini, fin = date(anio, 1, 1), date(anio, 12, 31)

    def bloque(d, paso):
        n, x = 0, d
        while ini <= x <= fin and libre(x):
            n, x = n + 1, x + timedelta(days=paso)
        return n
    res, d = [], ini
    while d <= fin:
        if libre(d):
            n = bloque(d, 1)
            dias = [d + timedelta(days=i) for i in range(n)]
            fi = [festivos[x.isoformat()] for x in dias if x.isoformat() in festivos and x.weekday() < 5]
            if n >= 3 and fi:
                res.append({"tipo": "largo", "desde": dias[0].isoformat(), "hasta": dias[-1].isoformat(), "dias": n, "fiestas": fi})
            d += timedelta(days=n)
        else:
            izq, der = bloque(d - timedelta(days=1), -1), bloque(d + timedelta(days=1), 1)
            if izq and der:
                desde, hasta = d - timedelta(days=izq), d + timedelta(days=der)
                rango = [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]
                fi = [festivos[x.isoformat()] for x in rango if x.isoformat() in festivos and x.weekday() < 5]
                if fi:
                    res.append({"tipo": "puente", "dia_puente": d.isoformat(), "desde": desde.isoformat(), "hasta": hasta.isoformat(),
                                "dias": izq + der + 1, "fiestas": fi})
            d += timedelta(days=1)
    # Un bloque largo que ya queda dentro de un puente no se repite
    pts = [p for p in res if p["tipo"] == "puente"]
    res = [p for p in res if p["tipo"] == "puente" or not any(q["desde"] <= p["desde"] and p["hasta"] <= q["hasta"] for q in pts)]
    return sorted(res, key=lambda p: p["desde"])


def slug_url(d):
    return f"calendario-laboral-{d['anio']}-{d['slug']}"


def es_mu(d):
    return d["clave"].startswith("MU:")


def titulo(d):
    if es_mu(d):
        return f"Calendario laboral {d['anio']} {d['region']}: fiestas locales y festivos"
    if d["clave"] == "ES":
        return f"Calendario laboral {d['anio']} en España: festivos nacionales y por comunidad"
    return f"Calendario laboral {d['anio']} {d['region']}: festivos y puentes"


def meta_desc(d):
    if es_mu(d):
        a, b = d["locales"]
        return (f"{d['region']} tiene {d['total']} festivos en {d['anio']}: los {d['regionales']} de la {d['comunidad']} "
                f"y sus fiestas locales del {fecha_larga(a)} y el {fecha_larga(b)}. Calendario para imprimir y puentes.")
    if d["clave"] == "ES":
        return (f"Los {d['total']} festivos nacionales comunes de {d['anio']} y los de cada comunidad, "
                f"con calendario para imprimir en PNG y PDF y calculadora de días laborables.")
    return (f"{d['region']} tiene {d['total']} festivos en {d['anio']} sin contar los locales. "
            f"Calendario para imprimir, puentes y calculadora de días laborables.")


def texto_respuesta(d):
    if es_mu(d):
        a, b = d["locales"]
        return (f"{d['region']} tiene {d['total']} festivos laborales en {d['anio']}: los {d['regionales']} de la {d['comunidad']} "
                f"y {len(d['locales'])} fiestas locales, el {dia_fecha(a)} y el {dia_fecha(b)}.",
                f"{d['entre_semana']} de esos festivos caen de lunes a viernes.")
    if d["clave"] == "ES":
        return (f"En {d['anio']} hay {d['total']} festivos nacionales comunes a toda España. "
                f"Cada comunidad completa su calendario con sus fiestas propias y cada municipio añade {d['locales_por_municipio']} locales.",
                f"Hasta un máximo de {d['maximo_legal']} fiestas laborales al año por municipio.")
    reparto = (f"{d['nacionales']} nacionales y {d['autonomicas']} autonómicos" if d["autonomicas"]
               else "todos de ámbito nacional")
    return (f"{d['region']} tiene {d['total']} festivos laborales en {d['anio']}: "
            f"{reparto}. Tu municipio suma {d['locales_por_municipio']} fiestas locales más.",
            f"{d['entre_semana']} de esos festivos caen de lunes a viernes.")


MES3 = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def resumen_anio(d):
    """Frase con datos propios de la region: fiestas propias, mes mas cargado y puentes."""
    propias = [f for f in d["fiestas"] if f["tipo"] == "autonómica"]
    maxfs = max(m["festivos_entre_semana"] for m in d["meses"])
    tops = [MESES[m["mes"] - 1] for m in d["meses"] if m["festivos_entre_semana"] == maxfs]
    pts = [p for p in d["puentes"] if p["tipo"] == "puente"]
    largos = [p for p in d["puentes"] if p["tipo"] == "largo"]
    mayor = max(d["puentes"], key=lambda p: p["dias"]) if d["puentes"] else None
    partes = []
    if es_mu(d):
        locs = [f for f in d["fiestas"] if f["tipo"] == "local"]
        sab = [f for f in locs if date.fromisoformat(f["fecha"]).weekday() == 5]
        partes.append(f"Las fiestas locales de {html.escape(d['region'])} en {d['anio']} son el {dia_fecha(locs[0]['fecha'])} y el {dia_fecha(locs[1]['fecha'])}, "
                      f"y se suman a la fiesta regional del {fecha_larga(propias[0]['fecha'])} ({html.escape(propias[0]['nombre'])}).")
        for f in locs:
            x = f["fecha"]
            wd = date.fromisoformat(x).weekday()
            if wd == 5:
                partes.append(f"La del {fecha_larga(x)} cae en sábado: solo cambia el calendario de quien trabaja ese día.")
                continue
            pt = next((q for q in d["puentes"] if q["desde"] <= x <= q["hasta"]), None)
            if pt and pt["tipo"] == "largo":
                partes.append(f"La del {fecha_larga(x)} deja {pt['dias']} días seguidos sin trabajar, {rango(pt['desde'], pt['hasta'])}.")
            elif pt:
                partes.append(f"Con la del {fecha_larga(x)} hay puente si pides el {dia_fecha(pt['dia_puente'])}: {pt['dias']} días libres seguidos.")
            else:
                partes.append(f"La del {fecha_larga(x)} cae en {DIAS[wd]} y no forma puente con el fin de semana.")
        menos = d["laborables_region"] - d["laborables_anio"]
        partes.append(f"Sus fiestas locales le quitan {menos} día{'s' if menos != 1 else ''} laborable{'s' if menos != 1 else ''} al calendario regional: "
                      f"{d['laborables_anio']} en lugar de {d['laborables_region']}.")
        propias = []
    elif propias:
        partes.append(f"Las fiestas propias de {html.escape(d['region'])} en {d['anio']} son: " + ", ".join(f"{fecha_larga(f['fecha'])} ({html.escape(f['nombre'])})" for f in propias) + ".")
    elif d["clave"] != "ES":
        partes.append(f"En {d['anio']}, {html.escape(d['region'])} no tiene fiestas autonómicas propias en día laborable: todos sus festivos son de ámbito nacional.")
    if len(tops) == 1:
        partes.append(f"{tops[0].capitalize()} es el mes con más festivos entre semana ({maxfs}).")
    else:
        lista = ", ".join(tops[:-1]) + " y " + tops[-1]
        partes.append(f"{lista.capitalize()} empatan como los meses con más festivos entre semana ({maxfs} cada uno).")
    if mayor:
        partes.append(f"Salen {len(largos)} fines de semana largos y {len(pts)} puentes posibles; el descanso más largo es de {mayor['dias']} días.")
    return "<p class=\"ch-resumen\">" + " ".join(partes) + "</p>"


def filas_festivos(d):
    out = []
    for f in d["fiestas"]:
        x = date.fromisoformat(f["fecha"])
        c = {"nacional": "n", "local": "l"}.get(f["tipo"], "a")
        etq = {"nacional": "festivo nacional", "local": "solo en " + html.escape(d["region"])}.get(f["tipo"], "festivo autonómico")
        if es_mu(d) and f["tipo"] != "local":
            etq = ""
        out.append(f'<li><span class="ch-baldosa {c}"><b>{x.day}</b>{MES3[x.month - 1]}</span>'
                   f'<span class="ch-fx"><strong>{html.escape(f["nombre"])}</strong><em>{DIAS[x.weekday()]}{", " + etq if etq else ""}</em></span></li>')
    return "".join(out)


def nota_region(d, base, regiones):
    n = d["nota"]
    if es_mu(d):
        return (f"<p class=\"ch-nota\">Las fiestas locales solo son festivas dentro del término municipal de {html.escape(d['region'])}. "
                f"Cuentan las del municipio donde está tu centro de trabajo, no las del lugar donde vives.</p>"
                + (f"<p class=\"ch-nota\">{html.escape(' y '.join(d['gemelos']))} tiene exactamente las mismas fiestas locales en {d['anio']}, así que este calendario también le sirve.</p>" if d["gemelos"] else ""))
    if d.get("hub"):
        return (f"<p class=\"ch-nota\">Las {d['locales_por_municipio']} fiestas locales de cada uno de los {d['hub']['n']} municipios están en "
                f"<a href=\"@@URL:{d['hub']['slug']}@@\">{html.escape(d['hub']['titulo'])}</a>.</p>")
    if d["clave"] == "ES":
        return "<p class=\"ch-nota\">Las fiestas propias de cada comunidad están en el mosaico de comunidades, más abajo.</p>"
    if not n:
        return ""
    if "islas" in n:
        items = "".join(f"<li>{isla}: {fecha_larga(f)} ({html.escape(nom)})</li>" for isla, (f, nom) in n["islas"].items())
        return f"<p class=\"ch-nota\">Cada isla suma una fiesta insular. {html.escape(n['texto'])}</p><ul class=\"ch-islas\">{items}</ul>"
    return f"<p class=\"ch-nota\">{html.escape(n['texto'])}</p>"


def rango(a, b):
    x, y = date.fromisoformat(a), date.fromisoformat(b)
    if x.month == y.month:
        return f"del {x.day} al {y.day} de {MESES[y.month - 1]}"
    return f"del {fecha_larga(a)} al {fecha_larga(b)}"


def lista_puentes(d):
    if not d["puentes"]:
        return "<li>Ningún festivo se junta con un fin de semana este año.</li>"
    out = []
    for p in d["puentes"]:
        nombres = html.escape(", ".join("la fiesta local" if x == "Fiesta local" else x for x in p["fiestas"]))
        if p["tipo"] == "largo":
            out.append(f"<li><b class=\"ch-num\">{p['dias']}</b><span><strong>{rango(p['desde'], p['hasta']).capitalize()}</strong>{p['dias']} días seguidos sin trabajar por {nombres}.</span></li>")
        else:
            out.append(f"<li class=\"ch-pte\"><b class=\"ch-num\">{p['dias']}</b><span><strong>Puente: pide el {DIAS[date.fromisoformat(p['dia_puente']).weekday()]} {fecha_larga(p['dia_puente'])}</strong>y tienes libres {p['dias']} días seguidos, {rango(p['desde'], p['hasta'])}, por {nombres}.</span></li>")
    return "".join(out)


def bloque_comparten(d):
    out = [f"<section class=\"ch-bloque\"><h2>Municipios con la misma fiesta local</h2><ul class=\"ch-difs\">"]
    for c in d["comparten"]:
        if c["municipios"]:
            lista = ", ".join(f"<a href=\"@@URL:calendario-laboral-{d['anio']}-{s_}@@\">{html.escape(n)}</a>" for s_, n in c["municipios"])
            txt = f"También es fiesta local en {lista}."
        else:
            txt = f"Ningún otro municipio de la {html.escape(d['comunidad'])} tiene fiesta local ese día."
        out.append(f"<li><strong>{dia_fecha(c['fecha']).capitalize()}</strong><p>{txt}</p></li>")
    out.append("</ul></section>")
    return "".join(out)


def bloque_diferencias(d):
    if es_mu(d):
        return bloque_comparten(d)
    if not d["diferencias"]:
        return ""
    out = [f"<section class=\"ch-bloque\"><h2>Qué cambia respecto a las comunidades vecinas</h2><ul class=\"ch-difs\">"]
    for v in d["diferencias"]:
        aqui = ", ".join(f"{fecha_larga(f)} ({html.escape(n)})" for f, n in v["solo_aqui"]) or "ninguno"
        alli = ", ".join(f"{fecha_larga(f)} ({html.escape(n)})" for f, n in v["solo_alli"]) or "ninguno"
        out.append(f"<li><a href=\"@@URL:calendario-laboral-{d['anio']}-{v['slug']}@@\">{html.escape(v['vecina'])}</a>"
                   f"<p><span>Festivo aquí y laborable allí</span>{aqui}</p><p><span>Festivo allí y laborable aquí</span>{alli}</p></li>")
    out.append("</ul><p class=\"ch-nota\">Comparación de festivos nacionales y autonómicos; las fiestas locales de cada municipio pueden cambiarla.</p></section>")
    return "".join(out)


def filas_meses(d):
    out = []
    for m in d["meses"]:
        fs = m["festivos_entre_semana"]
        nota = f"{fs} festivo" + ("s" if fs != 1 else "") if fs else "sin festivos"
        if es_mu(d):
            nl = sum(1 for x in d["locales"] if int(x[5:7]) == m["mes"] and date.fromisoformat(x).weekday() < 5)
            if nl:
                nota += f", {'la fiesta local' if nl == 1 else 'las 2 fiestas locales'}" if fs > nl else (" (fiesta local)" if nl == 1 else " (las 2 fiestas locales)")
        out.append(f"<li><span>{MESES[m['mes'] - 1].capitalize()}</span><b>{m['laborables']}</b><em>{nota}</em></li>")
    return "".join(out)


def faq(d):
    reg, a = d["region"], d["anio"]
    primero = d["fiestas"][0]
    ultimo = d["fiestas"][-1]
    sab = d["en_sabado"]
    qs = [
        (f"¿Cuántos festivos hay en {reg} en {a}?",
         f"{d['total']} entre nacionales y autonómicos, más {d['locales_por_municipio']} fiestas locales que fija cada municipio."),
        (f"¿Cuántos días laborables tiene {a} en {reg}?",
         f"{d['laborables_anio']} días de lunes a viernes, descontados los {d['entre_semana']} festivos que caen entre semana. Resta además los locales de tu municipio."),
        (f"¿Cuál es el primer y el último festivo de {a}?",
         f"El primero es el {fecha_larga(primero['fecha'])} ({primero['nombre']}) y el último el {fecha_larga(ultimo['fecha'])} ({ultimo['nombre']})."
         + (f" El {fecha_larga(sab[0])} cae en sábado." if sab else "")),
    ]
    propias = [f for f in d["fiestas"] if f["tipo"] == "autonómica"]
    if es_mu(d):
        a, b = d["locales"]
        qs = [
            (f"¿Cuántos festivos hay en {reg} en {d['anio']}?",
             f"{d['total']}: los {d['regionales']} de la {d['comunidad']} y {len(d['locales'])} fiestas locales."),
            (f"¿Cuáles son las fiestas locales de {reg} en {d['anio']}?",
             f"El {dia_fecha(a)} y el {dia_fecha(b)}, según el {d['fuente_local']['boletin']}."),
            (f"¿Cuántos días laborables tiene {d['anio']} en {reg}?",
             f"{d['laborables_anio']} días de lunes a viernes, ya descontados los {d['entre_semana']} festivos que caen entre semana, locales incluidos."),
            (f"¿Me corresponden las fiestas locales de {reg} si vivo en otro municipio?",
             f"Depende de dónde trabajes: se aplican las del municipio donde está tu centro de trabajo. Si trabajas en {reg}, libras el {fecha_larga(a)} y el {fecha_larga(b)}."),
        ]
        h = "".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(r)}</p></details>" for q, r in qs)
        return h, qs
    if d["clave"] != "ES":
        if propias:
            r = "Además de los nacionales, " + reg + " celebra " + "; ".join(f"el {fecha_larga(f['fecha'])}, {f['nombre']} ({DIAS[date.fromisoformat(f['fecha']).weekday()]})" for f in propias) + "."
        else:
            r = f"En {a} no tiene fiestas autonómicas propias en día laborable: sus {d['total']} festivos son de ámbito nacional."
        qs.append((f"¿Qué festivos propios tiene {reg} en {a}?", r))
    h = "".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(r)}</p></details>" for q, r in qs)
    return h, qs


def jsonld(d, qs, url):
    return json.dumps([
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in qs]},
        {"@context": "https://schema.org", "@type": "Dataset", "name": titulo(d), "description": meta_desc(d),
         "url": url, "isBasedOn": [d["fuente"]["url"], d["fuente_local"]["url"]] if d.get("fuente_local") else d["fuente"]["url"],
         "temporalCoverage": f"{d['anio']}-01-01/{d['anio']}-12-31",
         "spatialCoverage": {"@type": "Place", "name": d["region"] + (f", {d['comunidad']}" if d.get("comunidad") else "")},
         "isAccessibleForFree": True,
         "creator": {"@type": "Organization", "name": "Calendario Hoy", "url": d["sitio"]},
         "distribution": [{"@type": "DataDownload", "encodingFormat": "image/png", "contentUrl": f"{d['assets']}/img/{slug_url(d)}.png"},
                          {"@type": "DataDownload", "encodingFormat": "application/pdf", "contentUrl": f"{d['assets']}/img/{slug_url(d)}.pdf"}]},
    ], ensure_ascii=False).replace("</", "<\\/")


def enlaces_vecinos(d, regiones):
    """Mosaico de azulejos: cada comunidad con su fiesta propia y su total."""
    if es_mu(d):
        a = d["anio"]
        items = [f"<li><a href=\"@@URL:calendario-laboral-{a}-{d['comunidad_slug']}@@\"><span>{html.escape(d['comunidad'])}</span>"
                 f"<small>Los festivos comunes a toda la región</small><b>{d['regionales']} festivos</b></a></li>",
                 f"<li><a href=\"@@URL:{d['hub_slug']}@@\"><span>Todos los municipios</span>"
                 f"<small>Las fiestas locales de cada municipio</small><b>Ver la lista</b></a></li>"]
        for v in d["mosaico"]:
            fx = " y ".join(fecha_larga(x) for x in v["fechas"])
            b = ("Comparte el " + fecha_larga(v["comunes"][0])) if v["comunes"] else "Otras fechas"
            items.append(f"<li><a href=\"@@URL:calendario-laboral-{a}-{v['slug']}@@\"><span>{html.escape(v['nombre'])}</span><small>{fx}</small><b>{b}</b></a></li>")
        return "".join(items)
    por_slug = {r["slug"]: r for r in regiones.values()}
    slugs = list(por_slug) if d["clave"] == "ES" else d["vecinos"]
    items = [] if d["clave"] == "ES" else [f"<li><a href=\"@@URL:calendario-laboral-{d['anio']}-espana@@\"><span>Toda España</span><small>Los festivos comunes a todas las comunidades</small><b>{d['totales_es']} festivos</b></a></li>"]
    for s_ in slugs:
        pr = d["propias_slug"][s_]
        if pr and d["clave"] == "ES":
            fiesta = "; ".join(f"{fecha_larga(x[0])}, {html.escape(x[1])}" for x in pr)
        elif pr:
            fiesta = f"{fecha_larga(pr[0][0])}, {html.escape(pr[0][1])}" + (f", y {len(pr) - 1} más" if len(pr) > 1 else "")
        else:
            fiesta = "Sin fiesta propia en día laborable"
        items.append(f"<li><a href=\"@@URL:calendario-laboral-{d['anio']}-{s_}@@\"><span>{html.escape(por_slug[s_]['nombre'])}</span><small>{fiesta}</small><b>{d['totales'][s_]} festivos</b></a></li>")
    return "".join(items)


COBALTO, TINTA, OCRE, VERDE, GRIS, CAL, LOZA, JUNTA = (29, 63, 165), (20, 33, 61), (224, 160, 42), (47, 125, 91), (110, 119, 138), (238, 242, 248), (255, 255, 255), (221, 227, 237)
FUENTES = RAIZ / "fonts"


def fuente(nombre, px, peso=None):
    f = ImageFont.truetype(str(FUENTES / nombre), px)
    if peso:
        f.set_variation_by_name(peso)
    return f


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def azulejo(g, x, y, t, fondo, trazo, w):
    """Motivo de azulejo: cuartos de circulo en las esquinas y rombo central."""
    g.rectangle((x, y, x + t, y + t), fill=fondo)
    r = t * 0.42
    for cx, cy, a0 in ((x, y, 0), (x + t, y, 90), (x + t, y + t, 180), (x, y + t, 270)):
        g.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + 90, fill=trazo, width=w)
    m = t / 2
    d = t * 0.2
    g.polygon([(x + m, y + m - d), (x + m + d, y + m), (x + m, y + m + d), (x + m - d, y + m)], outline=trazo, width=w)
    g.ellipse((x + m - w, y + m - w, x + m + w, y + m + w), fill=trazo)


def dibujar(d, ruta_png, ruta_pdf, colores=None):
    S = 2
    W, H = 1240 * S, 1754 * S
    im = Image.new("RGB", (W, H), LOZA)
    g = ImageDraw.Draw(im)
    serif = lambda px: fuente("YoungSerif-Regular.ttf", px * S)
    sans = lambda px, p="Regular": fuente("Figtree[wght].ttf", px * S, p)
    # Banda de cobalto con cenefa de azulejos
    banda = 380 * S
    g.rectangle((0, 0, W, banda), fill=COBALTO)
    t = 62 * S
    for i in range(W // t + 1):
        azulejo(g, i * t, 0, t, COBALTO, (165, 183, 232), 2 * S)
    g.line((0, t, W, t), fill=(165, 183, 232), width=2 * S)
    g.text((70 * S, 84 * S), str(d["anio"]), font=serif(150), fill=LOZA)
    g.text((74 * S, 268 * S), "Calendario laboral" + (f", {d['comunidad']}" if d.get("comunidad") else ""), font=sans(28, "Medium"), fill=(196, 208, 240))
    g.text((74 * S, 330 * S), d["region"], font=sans(40, "Bold"), fill=LOZA, anchor="lm")
    # Ficha con el total
    fx, fy, fw, fh = 930 * S, 112 * S, 240 * S, 220 * S
    g.rounded_rectangle((fx, fy, fx + fw, fy + fh), 18 * S, fill=LOZA)
    g.text((fx + fw / 2, fy + 100 * S), str(d["total"]), font=serif(120), fill=COBALTO, anchor="mm")
    g.text((fx + fw / 2, fy + 172 * S), "festivos", font=sans(28, "SemiBold"), fill=TINTA, anchor="mm")
    g.text((fx + fw / 2, fy + 200 * S), "con los locales" if d.get("comunidad") else "sin contar locales", font=sans(18), fill=GRIS, anchor="mm")
    # Meses
    tipos = {f["fecha"]: f["tipo"] for f in d["fiestas"]}
    cw, ch, gx, gy = 350 * S, 280 * S, 45 * S, 18 * S
    x_ini, y_ini = 70 * S, 420 * S
    paso, alto = 48 * S, 34 * S
    for m in range(12):
        x0, y0 = x_ini + (m % 3) * (cw + gx), y_ini + (m // 3) * (ch + gy)
        g.text((x0, y0), MESES[m].capitalize(), font=serif(32), fill=COBALTO)
        for i, ini in enumerate("LMXJVSD"):
            g.text((x0 + i * paso + paso / 2, y0 + 62 * S), ini, font=sans(17, "SemiBold"), fill=GRIS, anchor="mm")
        primero = date(d["anio"], m + 1, 1).weekday()
        for dia in range(1, calendar.monthrange(d["anio"], m + 1)[1] + 1):
            pos = primero + dia - 1
            cx, cy = x0 + (pos % 7) * paso, y0 + 80 * S + (pos // 7) * alto
            iso = date(d["anio"], m + 1, dia).isoformat()
            tp = tipos.get(iso)
            caja = (cx + 3 * S, cy + 2 * S, cx + paso - 3 * S, cy + alto - 2 * S)
            if tp == "nacional":
                g.rounded_rectangle(caja, 6 * S, fill=COBALTO)
                color, fnt = LOZA, sans(19, "Bold")
            elif tp == "autonómica":
                g.rounded_rectangle(caja, 6 * S, fill=OCRE)
                color, fnt = TINTA, sans(19, "Bold")
            elif tp == "local":
                g.rounded_rectangle(caja, 6 * S, fill=VERDE)
                color, fnt = LOZA, sans(19, "Bold")
            elif pos % 7 > 4:
                g.rounded_rectangle(caja, 6 * S, fill=CAL)
                color, fnt = GRIS, sans(19)
            else:
                color, fnt = TINTA, sans(19, "Medium")
            g.text((cx + paso / 2, cy + alto / 2), str(dia), font=fnt, fill=color, anchor="mm")
    # Pie: leyenda, casillas para las fiestas locales y fuente
    yl = H - 150 * S
    g.line((70 * S, yl - 24 * S, W - 70 * S, yl - 24 * S), fill=JUNTA, width=2 * S)
    items = (("Festivo nacional", COBALTO), ("Festivo autonómico", OCRE)) + ((("Fiesta local", VERDE),) if d.get("comunidad") else ())
    x = 70 * S
    for txt, col in items:
        g.rounded_rectangle((x, yl, x + 34 * S, yl + 26 * S), 6 * S, fill=col)
        g.text((x + 46 * S, yl + 13 * S), txt, font=sans(20, "Medium"), fill=TINTA, anchor="lm")
        x += 300 * S
    if not d.get("comunidad"):
        g.text((x, yl + 13 * S), "Mis fiestas locales", font=sans(20, "Medium"), fill=TINTA, anchor="lm")
        for k in range(2):
            bx = x + 200 * S + k * 70 * S
            g.rounded_rectangle((bx, yl - 4 * S, bx + 52 * S, yl + 30 * S), 6 * S, outline=VERDE, width=3 * S)
    fte = f"Fuente: {d['fuente']['boe']} ({d['fuente']['id']})"
    if d.get("fuente_local"):
        fte = f"Fuentes: {d['fuente']['boe']} y {d['fuente_local']['boletin']}"
    g.text((70 * S, H - 70 * S), fte, font=sans(18), fill=GRIS, anchor="lm")
    g.text((W - 70 * S, H - 70 * S), "calendariohoy", font=serif(26), fill=COBALTO, anchor="rm")
    final = im.resize((W // S, H // S), Image.LANCZOS)
    final.quantize(colors=128, method=Image.Quantize.MEDIANCUT).save(ruta_png, optimize=True)
    final.save(ruta_pdf, "PDF", resolution=150)


def numeros_permitidos(d):
    """Todas las cifras que la pagina puede mostrar, derivadas de la ficha."""
    s = set()

    def rec(x):
        if isinstance(x, dict):
            for v in x.values():
                rec(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                rec(v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            s.add(str(x))
        elif isinstance(x, str):
            for n in re.findall(r"\d+", x):
                s.add(str(int(n)))
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x):
                a, m, dd = x.split("-")
                s.update({str(int(m)), str(int(dd)), m, dd})
    rec(d)
    return sorted(s, key=lambda v: (len(v), v))


def franja(cols):
    cols = [c if c.upper() != "#FFFFFF" else "#E3E7EE" for c in cols]
    n = len(cols)
    return "linear-gradient(90deg," + ",".join(f"{c} {round(i * 100 / n)}% {round((i + 1) * 100 / n)}%" for i, c in enumerate(cols)) + ")"


def render(plantilla, valores):
    return re.sub(r"\{([a-z_0-9]+)\}", lambda m: str(valores[m.group(1)]) if m.group(1) in valores else m.group(0), plantilla)


def sin_tildes(t):
    import unicodedata
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def datos_hub(base, cfg, regiones, loc, datos_mu, igual=None):
    """Listado de las fiestas locales de todos los municipios de una comunidad."""
    anio = loc["anio"]
    reg = datos_region(base, loc["region_clave"], cfg, regiones)
    igual = igual or {}
    munis = [{"slug": m["slug"], "nombre": nombre_pag(m), "fechas": m["fechas"], "pagina": igual.get(m["slug"], m["slug"]),
              "igual_que": nombre_pag(next(o for o in loc["municipios"] if o["slug"] == igual[m["slug"]])) if m["slug"] in igual else ""}
             for m in loc["municipios"]]
    cuenta = {}
    for m in munis:
        for x in m["fechas"]:
            cuenta.setdefault(x, []).append(m["nombre"])
    repetidas = sorted(([x, v] for x, v in cuenta.items() if len(v) >= 3), key=lambda t: (-len(t[1]), t[0]))
    por_mes = [{"mes": k, "fiestas": sum(1 for m in munis for x in m["fechas"] if int(x[5:7]) == k)} for k in range(1, 13)]
    sabado = [[x, v] for x, v in sorted(cuenta.items()) if date.fromisoformat(x).weekday() == 5]
    slug = hub_slug(loc)
    nombre = loc["region_nombre"]
    return {
        "anio": anio, "clave": "HUB:" + loc["region_slug"], "slug": slug, "region": nombre, "comunidad_slug": loc["region_slug"],
        "titulo": f"Fiestas locales {anio} en la {nombre}: los {len(munis)} municipios",
        "meta_descripcion": f"Las 2 fiestas locales de {anio} de cada uno de los {len(munis)} municipios de la {nombre}, con buscador y enlace al calendario laboral de cada municipio.",
        "municipios": munis, "n": len(munis), "regionales": reg["total"], "fiestas": reg["fiestas"], "locales_por_municipio": 2,
        "fechas_distintas": len(cuenta), "repetidas": repetidas, "por_mes": por_mes, "en_sabado": sabado,
        "fuente": reg["fuente"], "fuente_local": loc["fuente"], "sitio": cfg["sitio"], "assets": cfg["assets"],
        "miga": [[f"calendario-laboral-{anio}-{loc['region_slug']}", nombre], [None, f"Fiestas locales {anio}"]],
        "destacados": ["murcia-capital", "cartagena", "lorca", "molina-de-segura", "alcantarilla", "mazarron", "aguilas"],
    }


def valores_hub(d, cfg):
    a, nom = d["anio"], d["region"]
    filas = "".join(f'<li data-n="{sin_tildes(m["nombre"])}"><a href="@@URL:calendario-laboral-{a}-{m["pagina"]}@@">{html.escape(m["nombre"])}</a>'
                    f'<span>{dia_fecha(m["fechas"][0])} y {dia_fecha(m["fechas"][1])}'
                    + (f'. Mismas fiestas locales que {html.escape(m["igual_que"])}' if m["igual_que"] else "") + '</span></li>' for m in d["municipios"])
    rep = "".join(f"<li><b class=\"ch-num\">{len(v)}</b><span><strong>{dia_fecha(x).capitalize()}</strong>{html.escape(', '.join(v))}.</span></li>"
                  for x, v in d["repetidas"])
    meses = "".join(f"<li><span>{MESES[m['mes'] - 1].capitalize()}</span><b>{m['fiestas']}</b><em>{'fiesta local' if m['fiestas'] == 1 else 'fiestas locales'}</em></li>"
                    for m in d["por_mes"])
    top = d["repetidas"][0]
    sab = d["en_sabado"]
    qs = [
        (f"¿Cuántas fiestas locales tiene cada municipio de la {nom} en {a}?",
         f"{d['locales_por_municipio']}. Se suman a los {d['regionales']} festivos de toda la región, así que cada municipio tiene {d['regionales'] + d['locales_por_municipio']} festivos en total."),
        (f"¿Qué día es fiesta local en más municipios de la {nom}?",
         f"El {dia_fecha(top[0])}, que es fiesta local en {len(top[1])} municipios: {', '.join(top[1])}."),
        (f"¿Hay fiestas locales en sábado en {a}?",
         ("Sí: " + "; ".join(f"el {dia_fecha(x)} en {' y '.join(v)}" for x, v in sab) + ". Solo afectan a quien trabaja ese sábado.") if sab
         else "No, todas caen de lunes a viernes."),
        ("¿Dónde se publican las fiestas locales?",
         f"En el {d['fuente_local']['boletin']}, con la resolución de la Dirección General de Trabajo ({d['fuente_local']['id']})."),
    ]
    faq_html = "".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(r)}</p></details>" for q, r in qs)
    ld = json.dumps([
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in qs]},
        {"@context": "https://schema.org", "@type": "Dataset", "name": d["titulo"], "description": d["meta_descripcion"],
         "url": f"@@URL:{d['slug']}@@", "isBasedOn": [d["fuente_local"]["url"], d["fuente"]["url"]],
         "temporalCoverage": f"{a}-01-01/{a}-12-31", "spatialCoverage": {"@type": "Place", "name": nom}, "isAccessibleForFree": True,
         "creator": {"@type": "Organization", "name": "Calendario Hoy", "url": d["sitio"]}},
    ], ensure_ascii=False).replace("</", "<\\/")
    por_slug = {m["slug"]: m for m in d["municipios"]}
    mos = [f"<li><a href=\"@@URL:calendario-laboral-{a}-{d['comunidad_slug']}@@\"><span>{html.escape(nom)}</span><small>Calendario laboral de toda la región</small><b>{d['regionales']} festivos</b></a></li>"]
    for s_ in d["destacados"]:
        m = por_slug[s_]
        mos.append(f"<li><a href=\"@@URL:calendario-laboral-{a}-{s_}@@\"><span>{html.escape(m['nombre'])}</span><small>{fecha_larga(m['fechas'][0])} y {fecha_larga(m['fechas'][1])}</small><b>Ver su calendario</b></a></li>")
    fl, fb = d["fuente_local"], d["fuente"]
    return {
        "anio": a, "region": html.escape(nom), "n": d["n"], "regionales": d["regionales"], "fechas_distintas": d["fechas_distintas"],
        "locales_por_municipio": d["locales_por_municipio"],
        "respuesta": html.escape(f"Cada municipio de la {nom} tiene {d['locales_por_municipio']} fiestas locales en {a}, que se suman a los {d['regionales']} festivos de toda la región. Busca el tuyo en la lista."),
        "filas": filas, "repetidas": rep, "meses": meses, "faq_html": faq_html, "jsonld": ld, "mosaico": "".join(mos),
        "pie": (f"fiestas locales, <a href=\"{fl['url']}\" rel=\"noopener\">{html.escape(fl['titulo'])}</a> ({fl['boletin']}, {fl['id']}); "
                f"festivos nacionales y regionales, <a href=\"{fb['url']}\" rel=\"noopener\">{html.escape(fb['titulo'])}</a> ({fb['boe']})."),
        "sitio": cfg["sitio"],
        "datos_js": json.dumps({"anio": a, "f": sorted({x for m in d["municipios"] for x in m["fechas"]})}, separators=(",", ":")),
    }


def hub_slug(loc):
    return f"fiestas-locales-{loc['anio']}-{slug_region(loc)}"


def slug_region(loc):
    return "region-de-" + loc["region_slug"] if loc["region_slug"] == "murcia" else loc["region_slug"]


MODOS_REGION = ('<div class="ch-modos" role="radiogroup" aria-label="Qué marcar al tocar un día"><button type="button" class="ch-modo" data-m="l" role="radio" aria-checked="true"><i class="l"></i>Mis 2 fiestas locales</button>'
                '<button type="button" class="ch-modo" data-m="v" role="radio" aria-checked="false"><i class="v"></i>Mis vacaciones</button></div>')
MODOS_MUNI = ('<div class="ch-modos" role="radiogroup" aria-label="Qué marcar al tocar un día"><button type="button" class="ch-modo" data-m="v" role="radio" aria-checked="true"><i class="v"></i>Mis vacaciones</button></div>')


def valores_pagina(d, cfg, regiones, clave):
    anio = d["anio"]
    slug = slug_url(d)
    mu = es_mu(d)
    faq_html, qs = faq(d)
    resp, sub = texto_respuesta(d)
    colores = (regiones.get(clave) or {}).get("colores") or ["#AA151B", "#F1BF00", "#AA151B"]
    if clave == "ES":
        etq_total, etq_lab, tit_mos = "festivos comunes a toda España", "días laborables contando solo los festivos comunes", f"Festivos propios de cada comunidad en {anio}"
    elif mu:
        etq_total, etq_lab, tit_mos = f"festivos con los {len(d['locales'])} locales", f"días laborables en {html.escape(d['region'])}", f"Otros municipios de la {html.escape(d['comunidad'])}"
    else:
        etq_total, etq_lab, tit_mos = "festivos nacionales y autonómicos", "días laborables, sin contar las fiestas locales", f"Calendario laboral {anio} de otras comunidades"
    pie = f'<a href="{d["fuente"]["url"]}" rel="noopener">{html.escape(d["fuente"]["titulo"])}</a> ({d["fuente"]["boe"]})'
    if mu:
        fl = d["fuente_local"]
        pie = (f"festivos nacionales y regionales, <a href=\"{d['fuente']['url']}\" rel=\"noopener\">{d['fuente']['boe']}</a>; "
               f"fiestas locales, <a href=\"{fl['url']}\" rel=\"noopener\">{fl['boletin']}</a> ({fl['id']}).")
        pie_extra = ""
    else:
        pie += "."
        pie_extra = " Las fiestas locales de cada municipio las publica su comunidad autónoma o su provincia."
    return {
        "template_version": TEMPLATE_VERSION, "anio": anio, "total": d["total"], "slug": slug, "entre_semana": d["entre_semana"],
        "titulo_mosaico": tit_mos, "etq_total": etq_total, "etq_laborables": etq_lab,
        "franja": franja(colores), "region": html.escape(d["region"]),
        "respuesta": html.escape(resp), "subrespuesta": html.escape(sub),
        "img_png": f"{cfg['assets']}/img/{slug}.png", "img_pdf": f"{cfg['assets']}/img/{slug}.pdf",
        "img_alt": html.escape(f"Calendario laboral {anio} de {d['region']} con los festivos marcados, para imprimir"),
        "proximo_txt": "", "laborables_anio": d["laborables_anio"],
        "filas_festivos": filas_festivos(d), "nota_region": nota_region(d, None, regiones),
        "lista_puentes": lista_puentes(d), "resumen": resumen_anio(d), "diferencias": bloque_diferencias(d), "filas_meses": filas_meses(d),
        "faq_html": faq_html, "enlaces_vecinos": enlaces_vecinos(d, regiones),
        "pie_fuente": pie + pie_extra, "sitio": cfg["sitio"], "jsonld": jsonld(d, qs, f"@@URL:{slug}@@"),
        "leyenda_extra": '<li><i class="l"></i>Fiesta local</li>' if mu else "",
        "modos": MODOS_MUNI if mu else MODOS_REGION,
        "calc_txt": f"con las fiestas locales de {html.escape(d['region'])} ya descontadas" if mu else "sin contar las fiestas locales",
        "datos_js": json.dumps({"anio": anio, "r": d["slug"], "f": [f["fecha"] for f in d["fiestas"]], "n": [f["nombre"] for f in d["fiestas"]],
                                "t": [{"nacional": 1, "local": 2}.get(f["tipo"], 0) for f in d["fiestas"]],
                                "mu": 1 if mu else 0, "mn": d["region"] if mu else "", "cfg": cfg["assets"] + "/config.json"},
                               ensure_ascii=False, separators=(",", ":")),
    }


def fila_cola(d, slug, tipo_, prioridad):
    return {"slug": slug, "titulo": d["titulo"], "meta_descripcion": d["meta_descripcion"], "tipo": tipo_,
            "seccion": "laboral", "anio": d["anio"], "region": d["region"], "prioridad": prioridad,
            "template_version": TEMPLATE_VERSION, "estado": "pendiente",
            "clave_duplicado": f"laboral|{d['anio']}|{d.get('clave_slug', d['slug'])}", "url_publicada": "", "post_id": "",
            "intentos": 0, "ultimo_error": "", "fecha_publicacion": "", "enlaces_pendientes": 0}


def guardar(d, slug, html_txt):
    (OUT / "html" / f"{slug}.html").write_text(html_txt, encoding="utf-8")
    d["permitidos"] = numeros_permitidos(d)
    (OUT / "fichas" / f"{slug}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    base = json.loads((RAIZ / f"data/es/festivos-{anio}.json").read_text(encoding="utf-8"))
    regiones = json.loads((RAIZ / "data/es/regiones.json").read_text(encoding="utf-8"))
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    locs = [json.loads(x.read_text(encoding="utf-8")) for x in sorted((RAIZ / "data/es").glob(f"locales-{anio}-*.json"))]
    loc_de = {l["region_clave"]: l for l in locs}
    plantilla = (RAIZ / "plantillas/entrada.html").read_text(encoding="utf-8")
    p_hub = (RAIZ / "plantillas/locales.html").read_text(encoding="utf-8")
    for sub in ("html", "fichas"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    (RAIZ / "docs" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    cola = []
    for prioridad, clave in enumerate(["ES"] + list(regiones)):
        d = datos_region(base, clave, cfg, regiones)
        loc = loc_de.get(clave)
        if loc:
            d["hub"] = {"slug": hub_slug(loc), "n": len(loc["municipios"]), "titulo": f"Fiestas locales {anio} en la {loc['region_nombre']}"}
        slug = slug_url(d)
        dibujar(d, IMG / f"{slug}.png", IMG / f"{slug}.pdf")
        d["titulo"], d["meta_descripcion"] = titulo(d), meta_desc(d)
        guardar(d, slug, render(plantilla, valores_pagina(d, cfg, regiones, clave)))
        cola.append(fila_cola(d, slug, "pagina_indice" if clave == "ES" else "entrada", 100 - prioridad if clave == "ES" else 50))
    for loc in locs:
        datos_mu, vistos, sin_pagina, igual = [], {}, set(), {}
        for m in loc["municipios"]:
            k = tuple(sorted(m["fechas"]))
            if k in vistos:  # mismas fechas que otro municipio: su pagina seria un duplicado
                sin_pagina.add(m["slug"])
                igual[m["slug"]] = vistos[k]
            else:
                vistos[k] = m["slug"]
        for m in loc["municipios"]:
            if m["slug"] in sin_pagina:
                continue
            d = datos_municipio(base, cfg, regiones, loc, m, sin_pagina)
            d["hub_slug"] = hub_slug(loc)
            slug = slug_url(d)
            dibujar(d, IMG / f"{slug}.png", IMG / f"{slug}.pdf")
            d["titulo"], d["meta_descripcion"] = titulo(d), meta_desc(d)
            guardar(d, slug, render(plantilla, valores_pagina(d, cfg, regiones, loc["region_clave"])))
            cola.append(fila_cola(d, slug, "municipio", 40))
            datos_mu.append(d)
        d = datos_hub(base, cfg, regiones, loc, datos_mu, igual)
        guardar(d, d["slug"], render(p_hub, valores_hub(d, cfg)))
        cola.append(fila_cola(d, d["slug"], "listado_locales", 45))
    ruta_cola = RAIZ / "queue.csv"
    previa = {}
    if ruta_cola.exists():
        with ruta_cola.open(encoding="utf-8") as fh:
            previa = {r["clave_duplicado"]: r for r in csv.DictReader(fh)}
    with ruta_cola.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cola[0]))
        w.writeheader()
        for fila in cola:
            vieja = previa.get(fila["clave_duplicado"])
            if vieja and vieja["estado"] in ("publicado", "actualizar"):
                fila.update({k: vieja.get(k, "") for k in ("estado", "url_publicada", "post_id", "fecha_publicacion", "enlaces_pendientes")})
                if vieja["template_version"] != fila["template_version"]:
                    fila["estado"] = "actualizar"
            w.writerow(fila)
    print(f"Generadas {len(cola)} URLs en {OUT}")


if __name__ == "__main__":
    main()
