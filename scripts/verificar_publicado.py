#!/usr/bin/env python3
"""Criterios que solo se miden con la pagina publicada: enlaces 200 y
PageSpeed movil (LCP < 2,5 s, CLS < 0,1). Escribe informes/verificacion.json."""
import csv, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "CalendariosBot/0.1 (verificacion propia)"}


def estado(url):
    try:
        req = urllib.request.Request(url, headers=UA, method="GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def pagespeed(url):
    import os
    params = {"url": url, "strategy": "mobile", "category": "performance"}
    if os.environ.get("PSI_API_KEY"):  # opcional: sin clave Google suele rechazar las llamadas desde GitHub
        params["key"] = os.environ["PSI_API_KEY"]
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?{q}", timeout=120) as r:
        a = json.load(r)["lighthouseResult"]["audits"]
    return a["largest-contentful-paint"]["numericValue"] / 1000, a["cumulative-layout-shift"]["numericValue"]


def main():
    filas = [f for f in csv.DictReader((RAIZ / "queue.csv").open(encoding="utf-8")) if f["url_publicada"]]
    informe, fallos = [], 0
    for f in filas:
        code, html = estado(f["url_publicada"])
        cuerpo = html.split("<div class=\"ch\"", 1)[-1]
        enlaces = sorted(set(re.findall(r'href="(https?://[^"]+)"', cuerpo)))
        rotos = [u for u in enlaces if estado(u)[0] != 200]
        visibles = [m for m in ("post-timestamp", "post-author", "post-labels") if m in html]
        try:
            lcp, cls = pagespeed(f["url_publicada"])
        except Exception as exc:
            lcp, cls = None, None
            print(f"PageSpeed no disponible para {f['slug']}: {exc}")
        ok = code == 200 and not rotos and not visibles and (lcp is None or (lcp < 2.5 and cls < 0.1))
        fallos += not ok
        informe.append({"slug": f["slug"], "http": code, "enlaces": len(enlaces), "rotos": rotos,
                        "metadatos_visibles": visibles, "lcp_s": lcp, "cls": cls, "ok": ok})
        print(("OK   " if ok else "FALLA"), f["slug"], code, f"LCP={lcp} CLS={cls} rotos={len(rotos)}")
        time.sleep(5)
    (RAIZ / "informes").mkdir(exist_ok=True)
    (RAIZ / "informes" / "verificacion.json").write_text(json.dumps(informe, indent=1), encoding="utf-8")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
