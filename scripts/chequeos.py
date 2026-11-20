#!/usr/bin/env python3
"""Criterios de aceptacion automatizables (seccion 5 del prompt) sobre out/.
Sale con codigo 1 si alguna URL no pasa. Los que exigen navegador real
(PageSpeed, captura movil, enlaces 200, distancia real de anuncios) se
miden despues de publicar con scripts/verificar_publicado.py.
"""
import json
import re
import sys
from html.parser import HTMLParser
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "out"
LIMITE_BYTES = 30 * 1024
LIMITE_SIMILITUD = 0.70


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes, self._skip, self.jsonld = [], 0, []
        self._en_ld = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            self._en_ld = dict(attrs).get("type") == "application/ld+json"

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
            self._en_ld = False

    def handle_data(self, data):
        if self._en_ld:
            self.jsonld.append(data)
        elif not self._skip:
            self.partes.append(data)


def leer(ruta):
    p = Visible()
    p.feed(ruta.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", " ".join(p.partes)).strip(), p.jsonld


def bloques_interactivos(html):
    """Devuelve el HTML completo de cada contenedor con botones o campos (respetando el anidado de <div>)."""
    out = []
    for clase in ("ch-barra", "ch-plan", "ch-botones", "ch-form", "ch-modos"):
        i = html.find(f'<div class="{clase}"')
        if i < 0:
            continue
        prof, j = 0, i
        for m in re.finditer(r"<div\b|</div>", html[i:]):
            prof += 1 if m.group(0) == "<div" else -1
            if prof == 0:
                j = i + m.end()
                break
        out.append(html[i:j])
    return out


def tejas(texto, n=5):
    w = re.findall(r"\w+", texto.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def enlaces_docs():
    """Todo enlace interno del sitio publicado apunta a un archivo que existe (equivale al 200)."""
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    sitio = cfg["sitio"].rstrip("/")
    rotos = []
    for pag in (RAIZ / "docs").rglob("*.html"):
        for href in re.findall(r'(?:href|src)="([^"]+)"', pag.read_text(encoding="utf-8")):
            if href.startswith(sitio):
                rel = href[len(sitio):].lstrip("/").split("?")[0]
                destino = RAIZ / "docs" / rel
                if href.endswith("/") or not rel:
                    destino = destino / "index.html"
                if not destino.exists():
                    rotos.append(f"{pag.relative_to(RAIZ)} -> {href}")
            elif "@@URL" in href:
                rotos.append(f"{pag.relative_to(RAIZ)} -> {href}")
    return rotos


def main():
    fallos, textos = [], {}
    if "--docs" in sys.argv:
        rotos = enlaces_docs()
        for r in rotos:
            print("ENLACE ROTO:", r)
        if rotos:
            sys.exit(1)
        print("OK: todos los enlaces internos del sitio existen")
        return
    for ruta in sorted((OUT / "html").glob("*.html")):
        slug = ruta.stem
        ficha = json.loads((OUT / "fichas" / f"{slug}.json").read_text(encoding="utf-8"))
        html = ruta.read_text(encoding="utf-8")
        texto, ld = leer(ruta)
        textos[slug] = texto
        # 1. Cada cifra del texto existe en los datos de la URL
        sobran = sorted(set(str(int(n)) for n in re.findall(r"\d+", texto)) - set(ficha["permitidos"]))
        if sobran:
            fallos.append(f"{slug}: cifras sin respaldo en datos {sobran}")
        # 1b. Ningun placeholder sin reemplazar
        sueltos = re.findall(r"\{[a-z_0-9]+\}", texto)
        if sueltos:
            fallos.append(f"{slug}: placeholders sin reemplazar {sorted(set(sueltos))}")
        # 2. JSON-LD valido y con los tipos esperados
        try:
            tipos = {b["@type"] for b in json.loads(ld[0])}
            if not {"FAQPage", "Dataset"} <= tipos:
                fallos.append(f"{slug}: JSON-LD sin FAQPage/Dataset")
        except Exception as exc:
            fallos.append(f"{slug}: JSON-LD invalido ({exc})")
        # 3. Peso del codigo propio
        if len(html.encode()) > LIMITE_BYTES:
            fallos.append(f"{slug}: {len(html.encode())} bytes > 30 KB")
        # 4. Respaldo local: la herramienta trae sus datos dentro de la pagina
        if '"f":["' not in html:
            fallos.append(f"{slug}: sin datos locales de respaldo")
        # 5. Anuncios fuera de la herramienta y de los botones
        for bloque in bloques_interactivos(html):
            if "ANUNCIO" in bloque:
                fallos.append(f"{slug}: anuncio dentro de la herramienta o junto a botones")
        # 6. Fuente oficial enlazada y aviso legal
        if "boe.es" not in html or "Aviso legal" not in html:
            fallos.append(f"{slug}: falta fuente oficial o aviso legal")
        # 7. Respuesta arriba del todo
        if not re.search(r'<div class="ch"[^>]*>\s*<section class="ch-hero">\s*<p class="ch-resp">', html):
            fallos.append(f"{slug}: la respuesta no es lo primero")
        # 8. Rejilla de 6 a 8 enlaces vecinos (el indice enlaza a todas)
        n = len(re.findall(r"@@URL:", html.split('class="ch-mosaico"')[1].split("</ul>")[0]))
        if not slug.endswith("espana") and not 6 <= n <= 8:
            fallos.append(f"{slug}: {n} enlaces vecinos")
    # 9. Similitud de texto entre URLs
    peor = (0, "", "")
    t = {k: tejas(v) for k, v in textos.items()}
    for a, b in combinations(t, 2):
        sim = len(t[a] & t[b]) / max(1, len(t[a] | t[b]))  # Jaccard de tejas de 5 palabras
        peor = max(peor, (sim, a, b))
        if sim >= LIMITE_SIMILITUD:
            fallos.append(f"similitud {sim:.0%} entre {a} y {b}")
    print(f"URLs revisadas: {len(textos)}. Mayor similitud: {peor[0]:.0%} ({peor[1]} / {peor[2]})")
    for f in fallos:
        print("FALLA:", f)
    if fallos:
        sys.exit(1)
    print("OK: todas las URLs pasan los chequeos automaticos")


if __name__ == "__main__":
    main()
