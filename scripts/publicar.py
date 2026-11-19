#!/usr/bin/env python3
"""Publica en Blogger (API v3) la siguiente URL pendiente de queue.csv.

Una URL por ejecucion: el workflow corre cada hora y se respeta un tope diario.
Credenciales SOLO por variables de entorno (secretos de GitHub):
  BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN, BLOGGER_BLOG_ID
Permiso OAuth minimo: https://www.googleapis.com/auth/blogger

Truco de permalink: Blogger crea la URL a partir del titulo de la primera
publicacion. Se publica con el slug como titulo y luego se cambia al titulo real.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COLA = RAIZ / "queue.csv"
API = "https://www.googleapis.com/blogger/v3"
TOPE_DIARIO = int(os.environ.get("TOPE_DIARIO", "24"))
ESPERAS = (60, 180, 600)  # reintento progresivo ante quotaExceeded / rateLimitExceeded


def token():
    datos = urllib.parse.urlencode({
        "client_id": os.environ["BLOGGER_CLIENT_ID"], "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", datos, timeout=30) as r:
        return json.load(r)["access_token"]


def api(metodo, ruta, tok, cuerpo=None):
    for n, espera in enumerate((0,) + ESPERAS):
        time.sleep(espera)
        req = urllib.request.Request(API + ruta, method=metodo,
                                     data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                     headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "ignore")
            if e.code in (403, 429) and re.search(r"quotaExceeded|rateLimitExceeded|userRateLimitExceeded", txt) and n < len(ESPERAS):
                print(f"Cuota de Blogger: espero {ESPERAS[n]} s (intento {n + 1})")
                continue
            raise RuntimeError(f"HTTP {e.code}: {txt[:300]}")


def leer_cola():
    with COLA.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def guardar_cola(filas):
    with COLA.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def resolver_enlaces(html, filas):
    """@@URL:slug@@ -> URL publicada. Si la vecina aun no existe, se deja solo el texto (nunca un enlace roto)."""
    urls = {f["slug"]: f["url_publicada"] for f in filas if f["url_publicada"]}
    pendientes = 0

    def a_tag(m):
        nonlocal pendientes
        slug, texto = m.group(1), m.group(2)
        if slug in urls:
            return f'<a href="{urls[slug]}">{texto}</a>'
        pendientes += 1
        return texto
    html = re.sub(r'<a href="@@URL:([a-z0-9-]+)@@">(.*?)</a>', a_tag, html)
    html = re.sub(r"@@URL:([a-z0-9-]+)@@", lambda m: urls.get(m.group(1), ""), html)  # JSON-LD
    return html, pendientes


def publicadas_hoy(filas):
    hoy = datetime.now(timezone.utc).date().isoformat()
    return sum(f.get("fecha_publicacion", "").startswith(hoy) for f in filas)


def main():
    filas = leer_cola()
    for f in filas:
        f.setdefault("fecha_publicacion", "")
        f.setdefault("enlaces_pendientes", "0")
    if publicadas_hoy(filas) >= TOPE_DIARIO:
        print("Tope diario alcanzado")
        return
    blog = os.environ["BLOGGER_BLOG_ID"]
    tok = token()
    # 1) Prioridad: re-enlazar publicadas cuyas vecinas ya existen; 2) actualizar; 3) nuevas
    candidatas = ([f for f in filas if f["estado"] == "publicado" and int(f["enlaces_pendientes"] or 0) > 0]
                  + [f for f in filas if f["estado"] == "actualizar"]
                  + sorted([f for f in filas if f["estado"] in ("pendiente", "error") and int(f["intentos"] or 0) < 3],
                           key=lambda f: -int(f["prioridad"])))
    if not candidatas:
        print("Nada pendiente")
        return
    f = candidatas[0]
    html = (RAIZ / "out" / "html" / f"{f['slug']}.html").read_text(encoding="utf-8")
    html, pend = resolver_enlaces(html, filas)
    tipo = "pages" if f["tipo"] == "pagina_indice" else "posts"
    nueva = not f["post_id"]
    try:
        if not nueva:
            res = api("PATCH", f"/blogs/{blog}/{tipo}/{f['post_id']}", tok, {"title": f["titulo"], "content": html})
            if pend == 0 and int(f["enlaces_pendientes"] or 0) > 0:
                print(f"Re-enlazada {f['slug']}")
        else:
            res = api("POST", f"/blogs/{blog}/{tipo}?isDraft=false", tok,
                      {"title": f["slug"].replace("-", " "), "content": html})
            f["post_id"], f["url_publicada"] = res["id"], res["url"]
            api("PATCH", f"/blogs/{blog}/{tipo}/{res['id']}", tok, {"title": f["titulo"]})
            f["fecha_publicacion"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        f["estado"], f["ultimo_error"], f["enlaces_pendientes"] = "publicado", "", str(pend)
        print(f"OK {f['slug']} -> {f['url_publicada']} (enlaces pendientes: {pend})")
    except Exception as exc:
        f["estado"], f["intentos"], f["ultimo_error"] = "error", str(int(f["intentos"] or 0) + 1), str(exc)[:200]
        print(f"ERROR {f['slug']}: {exc}")
    # Al publicar una nueva, las ya publicadas que la enlazan pasan a re-enlazar
    if f["estado"] == "publicado" and nueva:
        for o in filas:
            if o is not f and o["estado"] == "publicado" and f"@@URL:{f['slug']}@@" in \
                    (RAIZ / "out" / "html" / f"{o['slug']}.html").read_text(encoding="utf-8"):
                o["enlaces_pendientes"] = str(max(1, int(o["enlaces_pendientes"] or 0)))
    guardar_cola(filas)
    if f["estado"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
