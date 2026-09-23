#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test hors ligne de l'assistant : aucun Hub, aucun accès réseau réel.

Faux Hub en local (127.0.0.1) : sans jeton il répond 401 Basic realm=Protected,
avec le bon jeton il rend le JSON de server.xml. Rien ne sort de la machine.

1. empreinte sans jeton (hub_fingerprint)
2. relais d'une requête arrivée par le proxy (forme URL absolue) + réponse
3. capture du token et de l'UID au passage
4. transparence : relais vers un autre hôte (cloud) et tunnel CONNECT, plus le
   refus des clients venus d'ailleurs que du réseau local
5. extraction du token et de l'UID d'un extrait de capture collé
6. run complet du wizard (entrées simulées, capture par le proxy, YAML généré)
7. branche "modules suivants" : question au futur, UID pris de l'ecoute

Sans dependance : Python 3.8+ seulement. Lancement :

    python tests/selftest.py

Sortie : une ligne OK/FAIL par verification, puis le total ; code de retour 1
s'il reste une seule verification en echec.
"""

import base64
import contextlib
import io
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import yokis_setup  # noqa: E402

TOKEN = base64.b64encode(b"leo@example.com:secret").decode()
UID = "0A1B2C"

seen = []        # chemins recus par le faux Hub
orders = []      # ordres command.xml recus (relais compris)
checks = []


def check(label, condition, detail=""):
    checks.append((label, bool(condition), detail))
    print("{} {} {}".format("OK  " if condition else "FAIL", label, detail))


class FakeHubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        seen.append(self.path)
        if self.headers.get("Authorization") != "Basic " + TOKEN:
            body = b'{"error":"unauthorized"}'
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Protected"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if "command.xml" in self.path:
            orders.append(self.path)
        payload = {"data": {"table": [
            {"uid": UID, "var": 1, "data": 42, "cpt": 7, "alive": 1},
            {"uid": "ZZ9999", "var": 0, "data": 0, "cpt": 1, "alive": 1},
        ]}}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_fake_hub():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeHubHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "127.0.0.1:{}".format(httpd.server_address[1])


def send_via_proxy(port, absolute_url, token=None):
    """Simule un client regle sur le proxy : URL absolue dans la ligne de requete."""
    host = absolute_url.split("/")[2]
    lines = ["GET {} HTTP/1.1".format(absolute_url), "Host: " + host,
             "Connection: close"]
    if token:
        lines.append("Authorization: Basic " + token)
    sock = socket.create_connection(("127.0.0.1", port), timeout=10)
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    sock.close()
    return data.decode("utf-8", "replace")


def recv_until(sock, marker, limit=4096):
    """Lit jusqu'au marqueur (ou le plafond) : reponses et tunnels partiels."""
    data = b""
    while marker not in data and len(data) < limit:
        chunk = sock.recv(256)
        if not chunk:
            break
        data += chunk
    return data


class CloudHandler(BaseHTTPRequestHandler):
    """Faux cloud : ce que l'app Yokis appelle en dehors du Hub."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b"cloud-ok"
        self.send_response(200)
        self.send_header("X-Cloud", "oui")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_fake_cloud():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), CloudHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "127.0.0.1:{}".format(httpd.server_address[1])


def echo_one(conn):
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            conn.sendall(b"echo:" + data)
    except OSError:
        pass
    finally:
        conn.close()


def start_echo():
    """Serveur TCP minimal : sert de destination au tunnel CONNECT."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(5)
    port = listener.getsockname()[1]

    def serve():
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            threading.Thread(target=echo_one, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    return listener, port

# --------------------------------------------------------------------------
# 1. Empreinte sans jeton
# --------------------------------------------------------------------------
httpd, fake = start_fake_hub()
check("empreinte du faux Hub sans jeton", yokis_setup.hub_fingerprint(fake))
closed = socket.socket()
closed.bind(("127.0.0.1", 0))
dead_port = closed.getsockname()[1]
closed.close()
check("pas d'empreinte sur un port ferme",
      not yokis_setup.hub_fingerprint("127.0.0.1:{}".format(dead_port)))

# --------------------------------------------------------------------------
# 2 a 4. Proxy : capture, relais transparent, tunnel, clients du LAN
# --------------------------------------------------------------------------
cloud_httpd, cloud = start_fake_cloud()
echo_listener, echo_port = start_echo()
proxy = yokis_setup.HubProxy(fake, timeout=8)
port = proxy.start()
check("ouverture du proxy", bool(port), "port {}".format(port))

captured = {}


def wait():
    captured["token"], captured["uid"] = proxy.wait_for_token()


waiter = threading.Thread(target=wait)
waiter.start()
time.sleep(0.6)

order_url = "http://{}/command.xml?action=order&id={}&order=on".format(fake, UID)
answer = send_via_proxy(port, order_url, TOKEN)
waiter.join(timeout=10)

check("token capture au passage", captured.get("token") == TOKEN)
check("UID capture dans l'URL", captured.get("uid") == UID)
check("l'ordre a bien ete relaye au Hub",
      any("id={}".format(UID) in path and "order=on" in path for path in orders),
      str(orders))
check("le client recoit la reponse du Hub",
      answer.startswith("HTTP/1.1 200") and '"uid"' in answer)

# Transparence : le trafic qui ne vise pas le Hub doit passer quand meme,
# sinon l'app Yokis (qui parle aussi a son cloud) decroche a l'ecran.
cloud_answer = send_via_proxy(port, "http://{}/api/etat".format(cloud))
check("HTTP vers un autre hote relaye (cloud)",
      cloud_answer.startswith("HTTP/1.1 200") and "cloud-ok" in cloud_answer)
check("en-tete du cloud transmis", "x-cloud: oui" in cloud_answer.lower())

tunnel = socket.create_connection(("127.0.0.1", port), timeout=10)
tunnel.sendall("CONNECT 127.0.0.1:{} HTTP/1.1\r\n"
               "Host: 127.0.0.1:{}\r\n\r\n".format(echo_port, echo_port).encode())
connect_answer = recv_until(tunnel, b"\r\n\r\n").decode("utf-8", "replace")
check("tunnel CONNECT etabli", connect_answer.startswith("HTTP/1.1 200"),
      connect_answer.splitlines()[0] if connect_answer else "")
tunnel.sendall(b"ping")
echoed = recv_until(tunnel, b"echo:ping")
check("octets tunnelises dans les deux sens", echoed.endswith(b"echo:ping"),
      repr(echoed))
tunnel.close()

check("hote injoignable : 502 propre",
      send_via_proxy(port, "http://127.0.0.1:{}/".format(dead_port))
      .startswith("HTTP/1.1 502"))
check("client hors LAN refuse", not proxy.client_allowed("8.8.8.8"))
check("client du meme /24 accepte",
      proxy.client_allowed((proxy._prefix or "") + ".42"))
check("boucle locale acceptee", proxy.client_allowed("127.0.0.1"))
proxy.stop()

# --------------------------------------------------------------------------
# 5. Saisie de secours : extrait de capture colle
# --------------------------------------------------------------------------
pasted = ("GET http://192.168.0.156/command.xml?action=order&id=8F3A11&order=on "
          "HTTP/1.1\nHost: 192.168.0.156\nAuthorization: Basic " + TOKEN + "\n")
yokis_setup.ask = lambda prompt: pasted
check("token + UID extraits d'une requete collee",
      yokis_setup.read_credentials() == (TOKEN, "8F3A11"))

yokis_setup.ask = lambda prompt: TOKEN + "\n"
check("token seul colle accepte",
      yokis_setup.read_credentials() == (TOKEN, None))

yokis_setup.ask = lambda prompt: "GET http://192.168.0.156/command.xml?id=8F3A11"
try:
    yokis_setup.read_credentials()
    check("requete sans jeton refusee proprement", False)
except SystemExit:
    check("requete sans jeton refusee proprement", True)

# --------------------------------------------------------------------------
# 6. Run complet du wizard, entrees simulees
# --------------------------------------------------------------------------
workdir = os.path.join(os.environ["TEMP"], "yokis_wizard_run")
os.makedirs(workdir, exist_ok=True)
os.chdir(workdir)
out_path = os.path.join(workdir, "yokis_entities.yaml")
if os.path.exists(out_path):
    os.remove(out_path)

answers = ["2", "Volet Test", "", "n"]


def fake_ask(prompt):
    if not answers:
        raise AssertionError("question non prevue : " + prompt)
    return answers.pop(0)


# stdin_typed_line patché : le selftest ne tape jamais d'Entrée.
yokis_setup.stdin_typed_line = lambda: None

real_start = yokis_setup.HubProxy.start
ports = {}


def spy_start(self, port=0):
    chosen = real_start(self, port)
    ports["port"] = chosen
    return chosen


def simulate_phone():
    deadline = time.time() + 15
    while "port" not in ports and time.time() < deadline:
        time.sleep(0.05)
    time.sleep(0.3)
    send_via_proxy(ports["port"], order_url, TOKEN)


wizard_proxy = {}


def spy_init(self, ip, timeout=180):
    real_init(self, ip, timeout=timeout)
    wizard_proxy["obj"] = self


real_init = yokis_setup.HubProxy.__init__
yokis_setup.HubProxy.__init__ = spy_init
yokis_setup.HubProxy.start = spy_start
yokis_setup.ask = fake_ask
webbrowser.open = lambda *args, **kwargs: False

args = type("Args", (), {"ip": fake, "token": None, "out": out_path,
                         "scan": False, "discover": False})()
phone = threading.Thread(target=simulate_phone)
phone.start()

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    yokis_setup.run_wizard(args)
phone.join(timeout=15)
output = buffer.getvalue()

check("le wizard a annonce la capture", "capture automatique" in output)
check("le wizard a utilise le module capture",
      "capturé, module {} !".format(UID) in output)
yaml_text = open(out_path, encoding="utf-8").read() if os.path.exists(out_path) else ""
check("YAML genere avec le token capture",
      "Basic " + TOKEN in yaml_text and UID in yaml_text)
check("module nomme comme demande", "volet_test" in yaml_text,
      yaml_text.splitlines()[0] if yaml_text else "(pas de fichier)")
check("rappel de retirer le proxy", "Proxy sur Aucun" in output)
check("module capture : question au passe",
      "Quel équipement venez-vous d'actionner ?" in output)
check("token verifie contre le Hub apres capture",
      "token accepté par le Hub" in output)
check("le Hub a servi la table des etats",
      any("server.xml" in path for path in seen))
check("le proxy a ete referme", wizard_proxy["obj"]._httpd is None)

# --------------------------------------------------------------------------
# 7. Branche "modules suivants" : la question reste au futur, et l'UID vient
#    de l'ecoute du Hub (patchee ici : aucun trafic).
# --------------------------------------------------------------------------
extra_answers = ["1", "Lampe Test", "n"]


def ask_extra(prompt):
    if not extra_answers:
        raise AssertionError("question non prevue : " + prompt)
    return extra_answers.pop(0)


real_listen = yokis_setup.listen_for_action
yokis_setup.listen_for_action = lambda ip, token, etype, timeout=120: "ZZ9999"
yokis_setup.ask = ask_extra
buffer2 = io.StringIO()
with contextlib.redirect_stdout(buffer2):
    suivants = yokis_setup.name_modules(yokis_setup.fetch_table(fake, TOKEN),
                                        fake, TOKEN, None)
out2 = buffer2.getvalue()
yokis_setup.listen_for_action = real_listen

check("module suivant : question au futur",
      "Quel équipement voulez-vous connecter ?" in out2)
check("module suivant : UID pris de l'ecoute",
      bool(suivants) and suivants[0]["uid"] == "ZZ9999",
      str([m["uid"] for m in suivants]))

failed = [label for label, ok, _ in checks if not ok]
print("\n{} / {} verifications passees".format(len(checks) - len(failed),
                                               len(checks)))
if failed:
    print("ECHECS : " + " | ".join(failed))
    sys.exit(1)
print("TOUT OK")