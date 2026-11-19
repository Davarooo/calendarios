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
TEMPLATE_VERSION = "1"
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
    festivo_set = {f["fecha"] for f in fiestas}
    meses = []
    for m in range(1, 13):
        dias_mes = calendar.monthrange(anio, m)[1]
        habiles = [date(anio, m, d) for d in range(1, dias_mes + 1) if date(anio, m, d).weekday() < 5]
        fest_sem = [d for d in habiles if d.isoformat() in festivo_set]
        meses.append({"mes": m, "laborables": len(habiles) - len(fest_sem), "festivos_entre_semana": len(fest_sem)})
    puentes = calcular_puentes(anio, {f["fecha"]: f["nombre"] for f in fiestas})
    clave_de = {r["slug"]: k for k, r in regiones.items()}
    def fechas_de(k):
        return {f["fecha"]: f["nombre"] for f in base["fiestas"] if k in f["marcas"]}
    diferencias = []
    if clave != "ES":
        mias = fechas_de(clave)
        for vs in meta["vecinos"][:3]:
            suyas = fechas_de(clave_de[vs])
            diferencias.append({"vecina": regiones[clave_de[vs]]["nombre"], "slug": vs,
                                "solo_aqui": sorted((f, mias[f]) for f in set(mias) - set(suyas)),
                                "solo_alli": sorted((f, suyas[f]) for f in set(suyas) - set(mias))})
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
        "diferencias": diferencias, "por_comunidad": por_comunidad,
        "sitio": cfg["sitio"], "assets": cfg["assets"],
    }


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
    return sorted(res, key=lambda p: p.get("dia_puente", p.get("desde")))


def slug_url(d):
    return f"calendario-laboral-{d['anio']}-{d['slug']}"


def titulo(d):
    if d["clave"] == "ES":
        return f"Calendario laboral {d['anio']} en España: festivos nacionales y por comunidad"
    return f"Calendario laboral {d['anio']} {d['region']}: festivos y puentes"


def meta_desc(d):
    if d["clave"] == "ES":
        return (f"Los {d['total']} festivos nacionales comunes de {d['anio']} y los de cada comunidad, "
                f"con calendario para imprimir en PNG y PDF y calculadora de días laborables.")
    return (f"{d['region']} tiene {d['total']} festivos en {d['anio']} sin contar los locales. "
            f"Calendario para imprimir, puentes y calculadora de días laborables.")


def texto_respuesta(d):
    if d["clave"] == "ES":
        return (f"En {d['anio']} hay {d['total']} festivos nacionales comunes a toda España. "
                f"Cada comunidad completa su calendario con sus fiestas propias y cada municipio añade {d['locales_por_municipio']} locales.",
                f"Hasta un máximo de {d['maximo_legal']} fiestas laborales al año por municipio.")
    reparto = (f"{d['nacionales']} nacionales y {d['autonomicas']} autonómicos" if d["autonomicas"]
               else "todos de ámbito nacional")
    return (f"{d['region']} tiene {d['total']} festivos laborales en {d['anio']}: "
            f"{reparto}. Tu municipio suma {d['locales_por_municipio']} fiestas locales más.",
            f"{d['entre_semana']} de esos festivos caen de lunes a viernes.")


def filas_festivos(d):
    out = []
    for f in d["fiestas"]:
        w = DIAS[date.fromisoformat(f["fecha"]).weekday()]
        out.append(f"<tr><td>{fecha_larga(f['fecha'])}</td><td>{w}</td><td>{html.escape(f['nombre'])}</td><td><span class=\"ch-tipo ch-{'nac' if f['tipo'] == 'nacional' else 'aut'}\">{f['tipo']}</span></td></tr>")
    return "".join(out)


def nota_region(d, base, regiones):
    n = d["nota"]
    if d["clave"] == "ES":
        filas = []
        for clave, meta in regiones.items():
            propias = [f for f in base["fiestas"] if f["marcas"].get(clave) == "***"]
            txt = "; ".join(f"{fecha_larga(f['fecha'])} ({html.escape(f['nombre'])})" for f in propias) or "sin fiestas autonómicas propias"
            filas.append(f"<tr><td><a href=\"@@URL:calendario-laboral-{d['anio']}-{meta['slug']}@@\">{meta['nombre']}</a></td><td>{txt}</td></tr>")
        return ("<h2>Fiestas propias de cada comunidad</h2><table class=\"ch-tab\"><thead><tr><th>Comunidad</th><th>Fiestas autonómicas</th></tr></thead><tbody>"
                + "".join(filas) + "</tbody></table>")
    if not n:
        return ""
    if "islas" in n:
        items = "".join(f"<li>{isla}: {fecha_larga(f)} ({html.escape(nom)})</li>" for isla, (f, nom) in n["islas"].items())
        return f"<p class=\"ch-nota\">Cada isla suma una fiesta insular. {html.escape(n['texto'])}</p><ul class=\"ch-list\">{items}</ul>"
    return f"<p class=\"ch-nota\">{html.escape(n['texto'])}</p>"


def lista_puentes(d):
    if not d["puentes"]:
        return "<li>Ningún festivo se junta con un fin de semana este año.</li>"
    out = []
    for p in d["puentes"]:
        nombres = html.escape(", ".join(p["fiestas"]))
        if p["tipo"] == "largo":
            out.append(f"<li><strong>Del {fecha_larga(p['desde'])} al {fecha_larga(p['hasta'])}</strong>: {p['dias']} días seguidos sin trabajar ({nombres}).</li>")
        else:
            out.append(f"<li><strong>Puente del {fecha_larga(p['dia_puente'])}</strong> ({DIAS[date.fromisoformat(p['dia_puente']).weekday()]}): pidiendo ese día salen {p['dias']} días libres, del {fecha_larga(p['desde'])} al {fecha_larga(p['hasta'])} ({nombres}).</li>")
    return "".join(out)


def bloque_diferencias(d):
    if not d["diferencias"]:
        return ""
    out = [f"<h2>Qué cambia respecto a las comunidades vecinas</h2><ul class=\"ch-list\">"]
    for v in d["diferencias"]:
        aqui = ", ".join(f"{fecha_larga(f)} ({html.escape(n)})" for f, n in v["solo_aqui"]) or "ninguno"
        alli = ", ".join(f"{fecha_larga(f)} ({html.escape(n)})" for f, n in v["solo_alli"]) or "ninguno"
        out.append(f"<li><a href=\"@@URL:calendario-laboral-{d['anio']}-{v['slug']}@@\">{html.escape(v['vecina'])}</a>: "
                   f"festivo en {html.escape(d['region'])} y laborable allí: {aqui}. Festivo allí y laborable en {html.escape(d['region'])}: {alli}.</li>")
    out.append("</ul>")
    return "".join(out)


def filas_meses(d):
    return "".join(f"<tr><td>{MESES[m['mes'] - 1].capitalize()}</td><td>{m['laborables']}</td><td>{m['festivos_entre_semana']}</td></tr>" for m in d["meses"])


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
    h = "".join(f"<details><summary>{html.escape(q)}</summary><p>{html.escape(r)}</p></details>" for q, r in qs)
    return h, qs


def jsonld(d, qs, url):
    return json.dumps([
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}} for q, r in qs]},
        {"@context": "https://schema.org", "@type": "Dataset", "name": titulo(d), "description": meta_desc(d),
         "url": url, "isBasedOn": d["fuente"]["url"], "temporalCoverage": f"{d['anio']}-01-01/{d['anio']}-12-31",
         "spatialCoverage": {"@type": "Place", "name": d["region"]},
         "license": "https://www.boe.es/datosabiertos/", "isAccessibleForFree": True,
         "creator": {"@type": "Organization", "name": "Calendario Hoy", "url": d["sitio"]},
         "distribution": [{"@type": "DataDownload", "encodingFormat": "image/png", "contentUrl": f"{d['assets']}/img/{slug_url(d)}.png"},
                          {"@type": "DataDownload", "encodingFormat": "application/pdf", "contentUrl": f"{d['assets']}/img/{slug_url(d)}.pdf"}]},
    ], ensure_ascii=False).replace("</", "<\\/")


def enlaces_vecinos(d, regiones):
    """Pestanas de indice con la franja de color de cada comunidad."""
    por_slug = {r["slug"]: r for r in regiones.values()}
    items = [("España", "espana", "#AA151B")] if d["clave"] != "ES" else []
    items += [(por_slug[s]["nombre"], s, por_slug[s]["colores"][0] if por_slug[s]["colores"][0] != "#FFFFFF" else por_slug[s]["colores"][1]) for s in d["vecinos"]]
    return "".join(f"<a href=\"@@URL:calendario-laboral-{d['anio']}-{s}@@\" style=\"--c:{c}\">{html.escape(t)}</a>" for t, s, c in items[:8 if d['clave'] != 'ES' else 19])


TINTA, ROJO, AMARILLO, AZUL, GRAFITO, MESA = (24, 35, 63), (224, 38, 46), (255, 214, 10), (36, 72, 168), (120, 128, 140), (238, 241, 246)
FUENTES = RAIZ / "fonts"


def fuente(nombre, px):
    return ImageFont.truetype(str(FUENTES / nombre), px)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def circulo_rotulador(g, cx, cy, r, semilla, grosor):
    """Circulo a mano alzada: radio con ruido, cierre que se pasa de largo y doble trazo."""
    import math
    import random
    rnd = random.Random(semilla)
    for pasada in range(2):
        a0 = rnd.uniform(0, math.tau)
        fase, amp = rnd.uniform(0, math.tau), r * 0.06
        pts = []
        for i in range(60):
            t = a0 + (math.tau + 0.55) * i / 59
            rr = r * (1.0 + 0.05 * pasada) + amp * math.sin(2 * t + fase) + rnd.uniform(-1, 1) * r * 0.015
            pts.append((cx + rr * 1.08 * math.cos(t), cy + rr * 0.94 * math.sin(t)))
        g.line(pts, fill=ROJO + (235 - 70 * pasada,), width=grosor - pasada * grosor // 3, joint="curve")


def subrayado(capa, x, y, w, h, semilla):
    import random
    rnd = random.Random(semilla)
    sk = rnd.uniform(-0.06, 0.06) * h
    ImageDraw.Draw(capa).polygon([(x, y + sk), (x + w, y - sk), (x + w + 3, y + h - sk), (x - 2, y + h + sk)], fill=AMARILLO + (235,))


def dibujar(d, ruta_png, ruta_pdf, colores):
    S = 2  # se dibuja al doble y se reduce: trazos suaves
    W, H = 1240 * S, 1754 * S
    im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # subrayador (debajo de los numeros)
    tinta = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # rotulador (encima)
    g, gt = ImageDraw.Draw(im), ImageDraw.Draw(tinta)
    # Franja con los colores de la comunidad
    franja = 22 * S
    colores = [c if c.upper() != "#FFFFFF" else "#E3E7EE" for c in colores]
    for i, c in enumerate(colores):
        g.rectangle((i * W // len(colores), 0, (i + 1) * W // len(colores), franja), fill=hex_rgb(c))
    g.line((0, franja, W, franja), fill=MESA, width=2 * S)
    # Cabecera: ano enorme, titulo y hoja de taco con el total
    g.text((70 * S, 52 * S), str(d["anio"]), font=fuente("Anton-Regular.ttf", 190 * S), fill=TINTA)
    g.text((74 * S, 300 * S), "Calendario laboral", font=fuente("FiraSans-Medium.ttf", 40 * S), fill=GRAFITO)
    g.text((74 * S, 350 * S), d["region"], font=fuente("FiraSans-SemiBold.ttf", 54 * S), fill=TINTA)
    tx, ty, tw, th = 905 * S, 70 * S, 265 * S, 300 * S
    g.rounded_rectangle((tx, ty, tx + tw, ty + th), 14 * S, fill=(255, 255, 255), outline=TINTA, width=3 * S)
    g.rectangle((tx + 3 * S, ty + 3 * S, tx + tw - 3 * S, ty + 62 * S), fill=ROJO)
    for k in range(14):  # perforado
        g.ellipse((tx + 14 * S + k * 17 * S, ty + 66 * S, tx + 20 * S + k * 17 * S, ty + 72 * S), fill=MESA)
    for ax in (tx + 70 * S, tx + tw - 70 * S):  # anillas
        g.rounded_rectangle((ax - 9 * S, ty - 26 * S, ax + 9 * S, ty + 22 * S), 9 * S, fill=GRAFITO)
    g.text((tx + tw / 2, ty + 33 * S), "festivos", font=fuente("FiraSans-SemiBold.ttf", 30 * S), fill="white", anchor="mm")
    g.text((tx + tw / 2, ty + 172 * S), str(d["total"]), font=fuente("Anton-Regular.ttf", 150 * S), fill=TINTA, anchor="mm")
    g.text((tx + tw / 2, ty + 268 * S), "sin contar locales", font=fuente("FiraSans-Regular.ttf", 22 * S), fill=GRAFITO, anchor="mm")
    # Meses
    tipos = {f["fecha"]: f["tipo"] for f in d["fiestas"]}
    f_mes, f_dia, f_ini = fuente("Anton-Regular.ttf", 38 * S), fuente("FiraSans-Medium.ttf", 25 * S), fuente("FiraSans-Regular.ttf", 19 * S)
    cw, ch, x_ini, y_ini = 360 * S, 270 * S, 70 * S, 445 * S
    paso = 50 * S
    for m in range(12):
        x0, y0 = x_ini + (m % 3) * (cw + 30 * S), y_ini + (m // 3) * (ch + 12 * S)
        g.text((x0, y0), MESES[m].capitalize(), font=f_mes, fill=TINTA)
        for i, ini in enumerate("LMXJVSD"):
            g.text((x0 + i * paso + paso / 2, y0 + 58 * S), ini, font=f_ini, fill=GRAFITO if i > 4 else TINTA, anchor="mm")
        g.line((x0, y0 + 74 * S, x0 + 7 * paso, y0 + 74 * S), fill=MESA, width=2 * S)
        primero = date(d["anio"], m + 1, 1).weekday()
        for dia in range(1, calendar.monthrange(d["anio"], m + 1)[1] + 1):
            pos = primero + dia - 1
            cx, cy = x0 + (pos % 7) * paso + paso / 2, y0 + 98 * S + (pos // 7) * 31 * S
            iso = date(d["anio"], m + 1, dia).isoformat()
            t = tipos.get(iso)
            if t == "autonómica":
                subrayado(capa, cx - 21 * S, cy - 13 * S, 42 * S, 26 * S, iso)
            elif t == "nacional":
                circulo_rotulador(gt, cx, cy, 16.5 * S, iso, 4 * S)
            color = TINTA if t else (GRAFITO if pos % 7 > 4 else TINTA)
            g.text((cx, cy), str(dia), font=fuente("FiraSans-SemiBold.ttf", 25 * S) if t else f_dia, fill=color, anchor="mm")
    # Leyenda y casillas para escribir a mano las fiestas locales
    yl = H - 150 * S
    circulo_rotulador(gt, 92 * S, yl + 18 * S, 18 * S, "leyenda", 4 * S)
    g.text((126 * S, yl + 18 * S), "Festivo nacional", font=f_ini, fill=TINTA, anchor="lm")
    subrayado(capa, 360 * S, yl + 4 * S, 44 * S, 28 * S, "leyenda")
    g.text((418 * S, yl + 18 * S), "Festivo autonómico", font=f_ini, fill=TINTA, anchor="lm")
    g.text((700 * S, yl + 18 * S), "Mis fiestas locales:", font=f_ini, fill=TINTA, anchor="lm")
    for k in range(2):
        bx = 905 * S + k * 140 * S
        for z in range(0, 120 * S, 14 * S):
            g.line((bx + z, yl + 36 * S, bx + z + 8 * S, yl + 36 * S), fill=GRAFITO, width=2 * S)
    g.text((70 * S, H - 62 * S), f"Fuente: {d['fuente']['id']} ({d['fuente']['boe']})",
           font=fuente("FiraSans-Regular.ttf", 19 * S), fill=GRAFITO)
    g.text((W - 70 * S, H - 66 * S), "calendariohoy", font=fuente("Anton-Regular.ttf", 26 * S), fill=ROJO, anchor="ra")
    final = Image.alpha_composite(Image.alpha_composite(im, capa), tinta)
    # Los numeros van encima del subrayado: se repintan sobre la capa amarilla
    g2 = ImageDraw.Draw(final)
    for m in range(12):
        x0, y0 = x_ini + (m % 3) * (cw + 30 * S), y_ini + (m // 3) * (ch + 12 * S)
        primero = date(d["anio"], m + 1, 1).weekday()
        for dia in range(1, calendar.monthrange(d["anio"], m + 1)[1] + 1):
            iso = date(d["anio"], m + 1, dia).isoformat()
            if tipos.get(iso) == "autonómica":
                pos = primero + dia - 1
                g2.text((x0 + (pos % 7) * paso + paso / 2, y0 + 98 * S + (pos // 7) * 31 * S), str(dia),
                        font=fuente("FiraSans-SemiBold.ttf", 25 * S), fill=TINTA, anchor="mm")
    final = final.convert("RGB").resize((W // S, H // S), Image.LANCZOS)
    final.quantize(colors=64, method=Image.Quantize.MEDIANCUT).save(ruta_png, optimize=True)
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


def main():
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    base = json.loads((RAIZ / f"data/es/festivos-{anio}.json").read_text(encoding="utf-8"))
    regiones = json.loads((RAIZ / "data/es/regiones.json").read_text(encoding="utf-8"))
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    plantilla = (RAIZ / "plantillas/entrada.html").read_text(encoding="utf-8")
    for sub in ("html", "fichas"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    (RAIZ / "docs" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    cola = []
    for prioridad, clave in enumerate(["ES"] + list(regiones)):
        d = datos_region(base, clave, cfg, regiones)
        slug = slug_url(d)
        url = f"@@URL:{slug}@@"
        dibujar(d, IMG / f"{slug}.png", IMG / f"{slug}.pdf", (regiones.get(clave) or {}).get("colores") or ["#AA151B", "#F1BF00", "#AA151B"])
        faq_html, qs = faq(d)
        resp, sub = texto_respuesta(d)
        valores = {
            "template_version": TEMPLATE_VERSION, "anio": anio, "total": d["total"],
            "franja": franja((regiones.get(clave) or {}).get("colores") or ["#AA151B", "#F1BF00", "#AA151B"]), "region": html.escape(d["region"]),
            "respuesta": html.escape(resp), "subrespuesta": html.escape(sub),
            "img_png": f"{cfg['assets']}/img/{slug}.png", "img_pdf": f"{cfg['assets']}/img/{slug}.pdf",
            "img_alt": html.escape(f"Calendario laboral {anio} de {d['region']} con los festivos marcados, para imprimir"),
            "proximo_txt": "", "laborables_anio": d["laborables_anio"],
            "filas_festivos": filas_festivos(d), "nota_region": nota_region(d, base, regiones),
            "lista_puentes": lista_puentes(d), "diferencias": bloque_diferencias(d), "filas_meses": filas_meses(d),
            "faq_html": faq_html, "enlaces_vecinos": enlaces_vecinos(d, regiones),
            "fuente_url": d["fuente"]["url"], "fuente_titulo": html.escape(d["fuente"]["titulo"]),
            "fuente_boe": d["fuente"]["boe"], "sitio": cfg["sitio"], "jsonld": jsonld(d, qs, url),
            "datos_js": json.dumps({"anio": anio, "r": d["slug"], "f": [f["fecha"] for f in d["fiestas"]],
                                    "n": [f["nombre"] for f in d["fiestas"]], "t": [1 if f["tipo"] == "nacional" else 0 for f in d["fiestas"]], "cfg": cfg["assets"] + "/config.json"},
                                   ensure_ascii=False, separators=(",", ":")),
        }
        (OUT / "html" / f"{slug}.html").write_text(render(plantilla, valores), encoding="utf-8")
        d["permitidos"] = numeros_permitidos(d)
        d["titulo"], d["meta_descripcion"] = titulo(d), meta_desc(d)
        (OUT / "fichas" / f"{slug}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        cola.append({"slug": slug, "titulo": d["titulo"], "meta_descripcion": d["meta_descripcion"],
                     "tipo": "pagina_indice" if clave == "ES" else "entrada",
                     "seccion": "laboral", "anio": anio, "region": d["region"],
                     "prioridad": 100 - prioridad if clave == "ES" else 50,
                     "template_version": TEMPLATE_VERSION, "estado": "pendiente",
                     "clave_duplicado": f"laboral|{anio}|{d['slug']}", "url_publicada": "", "post_id": "",
                     "intentos": 0, "ultimo_error": "", "fecha_publicacion": "", "enlaces_pendientes": 0})
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
            if vieja and vieja["estado"] == "publicado":
                fila.update({k: vieja.get(k, "") for k in ("estado", "url_publicada", "post_id", "fecha_publicacion", "enlaces_pendientes")})
                if vieja["template_version"] != fila["template_version"]:
                    fila["estado"] = "actualizar"
            w.writerow(fila)
    print(f"Generadas {len(cola)} URLs en {OUT}")


if __name__ == "__main__":
    main()
