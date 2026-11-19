#!/usr/bin/env python3
"""Prueba de fuente + extractor: lee la resolucion oficial de fiestas laborales
del BOE (XML de datos abiertos) y guarda data/es/festivos-AAAA.json.

Solo libreria estandar. No inventa nada: las columnas (comunidades), los dias
y el significado de los asteriscos se leen del propio documento. Si la
estructura no cuadra, termina con codigo 1 para que Actions avise.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = "CalendariosBot/0.1 (+https://github.com/Davarooo)"  # se identifica, no se disfraza
# Resolucion de 8 de octubre de 2026 (BOE 13-10-2026), fiestas laborales 2027
DOCS = {2027: "BOE-A-2026-21254"}
MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}


def descargar(url, intentos=4):
    for n in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/xml"})
            with urllib.request.urlopen(req, timeout=60) as r:
                print(f"HTTP {r.status} {url} ({r.headers.get('Content-Length', '?')} bytes)")
                return r.read()
        except Exception as exc:
            print(f"Intento {n + 1} fallo: {exc}")
            if n == intentos - 1:
                raise
            time.sleep(15 * 2 ** n)  # reintento progresivo


def limpio(s):
    return re.sub(r"\s+", " ", "".join(s)).strip()


def texto(el):
    return limpio(el.itertext())


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def parsear(xml_bytes, anio):
    raiz = ET.fromstring(xml_bytes)
    filas = [[texto(c) for c in tr if c.tag in ("td", "th")] for tr in raiz.iter("tr")]
    filas = [f for f in filas if any(f)]
    claves = ("andalucia", "aragon", "madrid", "galicia", "cataluna", "melilla")
    es_region = lambda c: any(k in sin_tildes(c) for k in claves)
    cab_idx = next(i for i, f in enumerate(filas) if sum(map(es_region, f)) >= 4)
    regiones = [c for c in filas[cab_idx] if not sin_tildes(c).startswith("fecha")]
    ancho = len(regiones) + 1
    fiestas, mes = [], None
    for f in filas[cab_idx + 1:]:
        primera = sin_tildes(f[0]).strip(" .")
        if primera in MESES:
            mes = MESES[primera]
            continue
        dia = re.match(r"(\d{1,2})\s+(.*)", f[0])
        if not dia or len(f) != ancho or not mes:
            continue
        marcas = {regiones[i]: f[i + 1] for i in range(len(regiones)) if f[i + 1].strip()}
        fiestas.append({"fecha": date(anio, mes, int(dia.group(1))).isoformat(),
                        "nombre": dia.group(2).strip(" ."), "marcas": marcas})
    todo = texto(raiz)
    leyenda = {m.group(2): limpio(m.group(1)) for m in
               re.finditer(r"(Fiesta [^()*]{5,160}?)\s*\((\*{1,3})\)", todo)}
    if len(regiones) < 17 or len(fiestas) < 10:
        raise ValueError(f"Estructura inesperada: {len(regiones)} regiones, {len(fiestas)} fiestas")
    return {"anio": anio, "regiones": regiones, "leyenda": leyenda, "fiestas": fiestas}


def main():
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    doc = DOCS[anio]
    xml = descargar(f"https://www.boe.es/diario_boe/xml.php?id={doc}")
    datos = parsear(xml, anio)
    datos["fuente"] = {"id": doc, "url": f"https://www.boe.es/diario_boe/txt.php?id={doc}"}
    salida = RAIZ / "data" / "es" / f"festivos-{anio}.json"
    print(f"Leido del BOE: {len(datos['fiestas'])} fiestas, {len(datos['regiones'])} regiones")
    if salida.exists():
        previo = json.loads(salida.read_text(encoding="utf-8"))
        cambios = [k for k in ("regiones", "fiestas", "leyenda") if previo.get(k) != datos[k]]
        if not cambios:
            print("OK: los datos publicados coinciden con el BOE")
            return
        for f_new in datos["fiestas"]:
            if f_new not in previo.get("fiestas", []):
                print("DIFERENCIA:", f_new)
        for k in ("regiones", "fiestas", "leyenda"):
            previo[k] = datos[k]
        salida.write_text(json.dumps(previo, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"AVISO: cambiaron {cambios}; revisar antes de regenerar paginas")
        sys.exit(1)
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Creado {salida}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
