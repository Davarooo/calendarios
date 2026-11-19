#!/usr/bin/env python3
"""Arma el sitio estatico en docs/ (GitHub Pages) a partir de out/html y queue.csv.

- Publica como maximo N URLs nuevas por ejecucion (prioridad de queue.csv).
- Resuelve los enlaces @@URL:slug@@: si la vecina aun no esta publicada, deja solo el texto.
- Envuelve cada entrada en una pagina completa con CSS en linea (sin peticiones extra).
- Genera paginas de confianza, sitemap.xml, robots.txt y 404.html.
Uso: python scripts/sitio.py --publicar 24
"""
import argparse
import csv
import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
COLA = RAIZ / "queue.csv"
INDICE = "calendario-laboral-2027-espana"  # la pagina indice es la portada
CONFIANZA = {
    "acerca": ("Acerca de Calendario Hoy", "Qué hace Calendario Hoy, de dónde salen sus datos oficiales y cómo se actualizan."),
    "metodologia": ("Metodología", "Fuentes oficiales, cálculos de días laborables y puentes, y controles antes de publicar."),
    "privacidad": ("Política de privacidad", "Qué datos trata Calendario Hoy y cómo ejercer tus derechos."),
    "contacto": ("Contacto", "Avisa de una fecha que no coincida con el boletín oficial."),
    "aviso-legal": ("Aviso legal", "Condiciones de uso de los calendarios de Calendario Hoy."),
}


def url_de(sitio, slug):
    return f"{sitio}/" if slug == INDICE else f"{sitio}/{slug}/"


def ruta_de(slug):
    return DOCS / "index.html" if slug == INDICE else DOCS / slug / "index.html"


def resolver(cuerpo, urls):
    cuerpo = re.sub(r'<a href="@@URL:([a-z0-9-]+)@@"([^>]*)>(.*?)</a>',
                    lambda m: (f'<a href="{urls[m.group(1)]}"{m.group(2)}>{m.group(3)}</a>' if m.group(1) in urls else m.group(3)), cuerpo)
    return re.sub(r"@@URL:([a-z0-9-]+)@@", lambda m: urls.get(m.group(1), ""), cuerpo)


def pagina(css, sitio, titulo, desc, canonical, cuerpo, imagen=None, h1=None):
    og = f'<meta property="og:image" content="{imagen}">' if imagen else ""
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}"><meta name="theme-color" content="#E0262E">
<meta property="og:type" content="website"><meta property="og:title" content="{html.escape(titulo)}"><meta property="og:url" content="{canonical}">{og}
<style>{css}</style></head><body>
<header class="top"><a class="marca" href="{sitio}/">Calendario<b>Hoy</b></a><nav><a href="{sitio}/">Laboral</a></nav></header>
<main><article><h1>{html.escape(h1 or titulo)}</h1>
{cuerpo}
</article></main>
<footer><a href="{sitio}/acerca/">Acerca de</a><a href="{sitio}/metodologia/">Metodología</a><a href="{sitio}/privacidad/">Privacidad</a><a href="{sitio}/contacto/">Contacto</a><a href="{sitio}/aviso-legal/">Aviso legal</a></footer>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--publicar", type=int, default=0, help="URLs nuevas a publicar en esta ejecucion")
    args = ap.parse_args()
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    sitio = cfg["sitio"].rstrip("/")
    css = (RAIZ / "plantillas/estilo.css").read_text(encoding="utf-8")
    with COLA.open(encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nuevas = 0
    for f in sorted([f for f in filas if f["estado"] == "pendiente"], key=lambda f: -int(f["prioridad"])):
        if nuevas >= args.publicar:
            break
        f["estado"], f["fecha_publicacion"] = "publicado", ahora
        nuevas += 1
    publicadas = [f for f in filas if f["estado"] in ("publicado", "actualizar")]
    urls = {f["slug"]: url_de(sitio, f["slug"]) for f in publicadas}
    urls.update({s: f"{sitio}/{s}/" for s in CONFIANZA})
    # Entradas
    for f in publicadas:
        cuerpo = resolver((RAIZ / "out/html" / f"{f['slug']}.html").read_text(encoding="utf-8"), urls)
        destino = ruta_de(f["slug"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        imagen = f"{sitio}/img/{f['slug']}.png"
        destino.write_text(pagina(css, sitio, f["titulo"], f["meta_descripcion"], urls[f["slug"]], cuerpo, imagen), encoding="utf-8")
        f["url_publicada"], f["estado"] = urls[f["slug"]], "publicado"
        f["enlaces_pendientes"] = str(cuerpo.count("@@URL:"))
    # Paginas de confianza
    for slug, (titulo, desc) in CONFIANZA.items():
        cuerpo = re.sub(r"<!--.*?-->\n?", "", (RAIZ / "blogger/paginas" / f"{slug}.html").read_text(encoding="utf-8"), flags=re.S)
        (DOCS / slug).mkdir(parents=True, exist_ok=True)
        (DOCS / slug / "index.html").write_text(pagina(css, sitio, f"{titulo} | Calendario Hoy", desc, urls[slug], resolver(cuerpo, urls), h1=titulo), encoding="utf-8")
    # Paginas que ya no estan en la cola: se retiran
    validas = {ruta_de(f["slug"]).parent for f in publicadas} | {DOCS / s for s in CONFIANZA}
    for d in DOCS.iterdir():
        if d.is_dir() and d.name not in ("img",) and d not in validas:
            shutil.rmtree(d)
    # 404, sitemap y robots
    (DOCS / "404.html").write_text(pagina(css, sitio, "Página no encontrada | Calendario Hoy", "La página no existe.", f"{sitio}/404.html",
                                          f'<p>Esta página no existe. <a href="{sitio}/">Ver el calendario laboral</a>.</p>', h1="Página no encontrada"), encoding="utf-8")
    hoy = ahora[:10]
    entradas = [(urls[f["slug"]], (f["fecha_publicacion"] or ahora)[:10]) for f in publicadas] + [(urls[s], hoy) for s in CONFIANZA]
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"<url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in entradas) + "</urlset>\n", encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {sitio}/sitemap.xml\n", encoding="utf-8")
    with COLA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"Publicadas en total: {len(publicadas)} (nuevas en esta ejecucion: {nuevas})")


if __name__ == "__main__":
    main()
