#!/usr/bin/env python3
"""Ejecutalo UNA vez en tu computador (no en GitHub) para sacar el refresh token de Blogger.
1. Google Cloud Console: crea un proyecto, activa "Blogger API v3", crea un ID de cliente OAuth tipo "App de escritorio".
2. python scripts/obtener_token.py TU_CLIENT_ID TU_CLIENT_SECRET
3. Autoriza en el navegador. El token se imprime en tu terminal: pegalo SOLO como secreto
   BLOGGER_REFRESH_TOKEN en GitHub (Settings > Secrets and variables > Actions). Nunca en un chat.
"""
import http.server, json, sys, urllib.parse, urllib.request, webbrowser

CID, SEC = sys.argv[1], sys.argv[2]
REDIR = "http://127.0.0.1:8765"
url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": CID, "redirect_uri": REDIR, "response_type": "code", "access_type": "offline",
    "prompt": "consent", "scope": "https://www.googleapis.com/auth/blogger"})
codigo = {}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        codigo.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
        self.send_response(200); self.end_headers()
        self.wfile.write("Listo. Vuelve a la terminal.".encode())

    def log_message(self, *a):
        pass


print("Abriendo el navegador para autorizar..."); webbrowser.open(url)
http.server.HTTPServer(("127.0.0.1", 8765), H).handle_request()
datos = urllib.parse.urlencode({"code": codigo["code"][0], "client_id": CID, "client_secret": SEC,
                                "redirect_uri": REDIR, "grant_type": "authorization_code"}).encode()
tok = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", datos))
print("\nBLOGGER_REFRESH_TOKEN =", tok["refresh_token"])
