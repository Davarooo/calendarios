#!/usr/bin/env python3
"""Copia mensual de todas las entradas y paginas publicadas -> backups/AAAA-MM.json"""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from publicar import api, token

RAIZ = Path(__file__).resolve().parent.parent


def todo(tok, blog, tipo):
    items, page = [], ""
    while True:
        res = api("GET", f"/blogs/{blog}/{tipo}?fetchBodies=true&maxResults=500&status=live{page}", tok)
        items += res.get("items", [])
        if not res.get("nextPageToken"):
            return items
        page = f"&pageToken={res['nextPageToken']}"


def main():
    blog, tok = os.environ["BLOGGER_BLOG_ID"], token()
    datos = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "posts": todo(tok, blog, "posts"), "pages": todo(tok, blog, "pages")}
    (RAIZ / "backups").mkdir(exist_ok=True)
    ruta = RAIZ / "backups" / f"{datetime.now(timezone.utc):%Y-%m}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    print(f"Copia: {len(datos['posts'])} entradas, {len(datos['pages'])} paginas -> {ruta}")


if __name__ == "__main__":
    main()
