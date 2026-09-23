#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YokisHub4HomeAssistant : assistant de configuration.

Découvre un Yokis Hub sur le réseau local, liste automatiquement tous ses
modules (UID inclus) et génère les blocs YAML prêts à coller dans le
`configuration.yaml` de Home Assistant : rest_command, capteurs REST,
capteurs template de reprise et entités light / cover / switch.

Aucune dépendance externe : Python 3.8+ suffit.

Utilisation :
    python yokis_setup.py            assistant interactif complet
    python yokis_setup.py --scan    chercher le Hub sur le réseau local
    python yokis_setup.py --discover --ip <IP> --token <B64>   lister les modules

"""

import argparse
import concurrent.futures
import datetime
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if os.name == "nt":
    try:
        import ctypes
        _kernel = ctypes.windll.kernel32
        _kernel.SetConsoleMode(_kernel.GetStdHandle(-11), 7)
    except Exception:
        pass

C_RESET = "\033[0m"
C_TITLE = "\033[1;36m"
C_OK = "\033[1;32m"
C_WARN = "\033[1;33m"
C_PROMPT = "\033[1;37m"
C_DIM = "\033[2m"


def c(color, text):
    """Texte coloré refermé proprement (pas de fuite de couleur)."""
    return color + text + C_RESET


def clear_screen():
    """Vide la console au lancement pour partir sur une base propre."""
    os.system("cls" if os.name == "nt" else "clear")

HUB_PORT_PATH = "server.xml?gettable&update=1"
SCAN_INTERVAL = {"light": 5, "cover": 10, "switch": 5}
TYPE_LABELS = {
    "light": "Lampe / éclairage",
    "cover": "Volet roulant (position)",
    "gate": "Portail / porte (impulsion)",
    "switch": "Interrupteur avec état",
}


class HubError(Exception):
    pass


# --------------------------------------------------------------------------
# Réseau
# --------------------------------------------------------------------------

_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _open_direct(url_or_req, timeout):
    """GET sans passer par le proxy système. Lève HTTPError/URLError."""
    return _DIRECT_OPENER.open(url_or_req, timeout=timeout)


def hub_request(ip, token, path, timeout=4):
    """GET authentifié vers le Hub. Lève HubError en cas d'échec lisible."""
    url = "http://{}/{}".format(ip, path)
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Basic " + token)
    try:
        with _open_direct(req, timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise HubError("token refusé (401) par le Hub " + ip)
        raise HubError("HTTP {} du Hub {}".format(exc.code, ip))
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise HubError("Hub {} injoignable ({})".format(ip, exc.__class__.__name__))


def fetch_table(ip, token):
    raw = hub_request(ip, token, HUB_PORT_PATH)
    try:
        payload = json.loads(raw)
        table = payload["data"]["table"]
    except (ValueError, KeyError, TypeError):
        raise HubError("réponse illisible depuis {} (pas un Yokis Hub ?)".format(ip))
    return table


def is_private_lan(ip):
    """True si l'IPv4 est en plage privée RFC1918 (LAN de maison)."""
    try:
        a, b = int(ip.split(".")[0]), int(ip.split(".")[1])
    except (ValueError, IndexError):
        return False
    return (a == 10
            or (a == 192 and b == 168)
            or (a == 172 and 16 <= b <= 31))


def local_ipv4s():
    """Toutes les IPv4 non-loopback de la machine (toutes les interfaces).

    L'astuce UDP seule ne voit qu'une route : avec VPN, VirtualBox ou
    plusieurs cartes, le Hub peut être sur un autre /24 que celui-là.
    """
    found = set()

    def add(ip):
        if ip and not ip.startswith("127.") and ip not in found:
            try:
                socket.inet_aton(ip)
            except OSError:
                return
            found.add(ip)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for dest in ("10.255.255.255", "192.168.255.255", "172.31.255.255"):
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                probe.connect((dest, 1))
                add(probe.getsockname()[0])
                probe.close()
            except OSError:
                pass
        sock.connect(("10.255.255.255", 1))
        add(sock.getsockname()[0])
    except OSError:
        pass
    finally:
        sock.close()

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None,
                                       socket.AF_INET, socket.SOCK_STREAM):
            add(info[4][0])
    except OSError:
        pass

    return sorted(found, key=lambda ip: (not is_private_lan(ip), ip))


def local_subnet():
    """Toutes les IP à sonder : un /24 par interface privée de la machine.

    Compat : renvoie une liste plate d'IP (comme l'ancien /24 unique).
    """
    prefixes = []
    for ip in local_ipv4s():
        if not is_private_lan(ip):
            continue
        prefix = ip.rsplit(".", 1)[0]
        if prefix not in prefixes:
            prefixes.append(prefix)
    if not prefixes:
        # Dernier recours : la route UDP, ou l'exemple documenté.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("10.255.255.255", 1))
            ip = sock.getsockname()[0]
        except OSError:
            ip = "192.168.0.10"
        finally:
            sock.close()
        if is_private_lan(ip):
            prefixes = [ip.rsplit(".", 1)[0]]
    hosts = []
    for prefix in prefixes:
        for n in range(1, 255):
            host = "{}.{}".format(prefix, n)
            if host not in hosts:
                hosts.append(host)
    return hosts


def arp_candidates():
    """IP déjà vues dans le cache ARP : le Hub est souvent déjà là (rapide)."""
    try:
        out = subprocess.check_output(["arp", "-a"], timeout=2)
    except (OSError, subprocess.SubprocessError):
        return []
    ips = []
    for line in out.decode("utf-8", "replace").splitlines():
        for token in line.replace("\t", " ").split():
            if not is_private_lan(token):
                continue
            host = token.rsplit(".", 1)[-1]
            if host in ("0", "255"):
                continue
            if token not in ips:
                ips.append(token)
    return ips


def hub_fingerprint(ip, timeout=3):
    """Empreinte SANS token : True si l'IP répond 401 Basic realm=Protected.

    Seul un Yokis Hub répond exactement ça sur server.xml. Aucun
    identifiant n'est envoyé : la réponse 401 contient le realm en clair.
    """
    url = "http://{}/{}".format(ip, HUB_PORT_PATH)
    try:
        with _open_direct(url, timeout) as resp:
            resp.read(1)
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            return False
        www_auth = exc.headers.get("WWW-Authenticate", "")
        return "basic realm=" in www_auth.lower() and "protected" in www_auth.lower()
    except (urllib.error.URLError, socket.timeout, OSError):
        return False
    return False


def scan_lan(token=None, timeout=1, verbose=True):
    """Trouve le Yokis Hub : ARP d'abord, puis tous les /24 locaux.

    1. Cache ARP (hosts déjà parlés, souvent le Hub, quasi instantané).
    2. Balayage parallèle de chaque /24 privé des interfaces de la machine.
    Avec token : vérifie en plus que la table est lisible.
    Sans token : empreinte 401 seule, aucun identifiant envoyé.
    """
    def probe(ip):
        if not hub_fingerprint(ip, timeout=timeout):
            return None
        if token:
            try:
                raw = hub_request(ip, token, HUB_PORT_PATH, timeout=timeout)
                payload = json.loads(raw)
                if "data" in payload and "table" in payload["data"]:
                    return ip, len(payload["data"]["table"])
            except (HubError, ValueError):
                return ip, None  # Hub trouvé, table illisible (mauvais token ?)
            return None
        return ip, None

    found = []
    seen = set()

    def consider(result):
        if result and result[0] not in seen:
            seen.add(result[0])
            found.append(result)
            if verbose:
                extra = (" ({} modules)".format(result[1])
                         if result[1] is not None else "")
                print(c(C_OK, "  [OK] Yokis Hub trouvé : {}{}"
                      .format(result[0], extra)))

    if verbose:
        print(c(C_DIM, "  · cache ARP..."))
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        for result in pool.map(probe, arp_candidates()):
            consider(result)
    if found:
        return found

    targets = [ip for ip in local_subnet() if ip not in seen]
    if verbose:
        prefixes = sorted({ip.rsplit(".", 1)[0] for ip in targets})
        print(c(C_DIM, "  · scan de {} IP ({} /24)..."
              .format(len(targets), len(prefixes))))
    workers = min(128, max(32, len(targets)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(probe, targets):
            consider(result)
    return found


def explain_scan_failure():
    """Après un scan vide : où on est, et ce qu'il faut vérifier."""
    ips = local_ipv4s()
    private = [ip for ip in ips if is_private_lan(ip)]
    print(c(C_WARN, "\nAucun Hub trouvé."))
    if not private:
        print("  Ce PC n'a aucune IP privée (192.168.x / 10.x / 172.16-31.x) :")
        print("  il est probablement hors du Wi-Fi de la maison (4G/5G,")
        print("  autre réseau). Reconnectez-vous au même Wi-Fi que le Hub.")
        if ips:
            print(c(C_DIM, "  (IP visibles : {})".format(", ".join(ips))))
    else:
        print("  IP locales de ce PC : {}".format(", ".join(private)))
        print("  Vérifiez que ce PC et le Yokis Hub sont sur le même Wi-Fi")
        print("  (pas le téléphone en 4G/5G, pas un autre VLAN / Guest).")
        print("  Puis relancez le scan, ou donnez l'IP du Hub à la main")
        print("  (étiquette du boîtier / routeur, ex. 192.168.0.156).")


def test_module(ip, token, uid):
    """Allume le module 3 s puis l'éteint, pour l'identifier physiquement."""
    hub_request(ip, token, "command.xml?action=order&id={}&order=on".format(uid))
    time.sleep(3)
    hub_request(ip, token, "command.xml?action=order&id={}&order=off".format(uid))


def snapshot_table(ip, token, timeout=4):
    """Lit la table du Hub et la renvoie indexée par UID (var, data, cpt, alive)."""
    raw = hub_request(ip, token, HUB_PORT_PATH, timeout=timeout)
    payload = json.loads(raw)
    snap = {}
    for entry in payload["data"]["table"]:
        snap[entry.get("uid")] = {
            "var": entry.get("var"),
            "data": entry.get("data"),
            "cpt": entry.get("cpt"),
            "alive": entry.get("alive"),
        }
    return snap


def diff_snapshots(before, after):
    """UID dont l'activité a changé entre deux snapshots.

    var et data portent l'état (lampe, position de volet) ; cpt est un
    compteur d'activité qui augmente à chaque ordre reçu, même quand
    l'état final revient identique (ex : télérupteur déjà allumé).
    Les trois ensemble détectent toute action réelle.
    """
    changed = []
    for uid, state in after.items():
        old = before.get(uid)
        if old is None:
            changed.append(uid)
        elif (state["var"] != old["var"]
              or state["data"] != old["data"]
              or state["cpt"] != old["cpt"]):
            changed.append(uid)
    return changed


# --------------------------------------------------------------------------
# Texte
# --------------------------------------------------------------------------

def slugify(text):
    """Nom lisible -> identifiant : accents retirés, séparateurs -> _."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    out = []
    for char in text.lower():
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_") or "module"


def mask_token(token):
    if len(token) <= 10:
        return "*" * len(token)
    return token[:4] + "*" * (len(token) - 8) + token[-4:]


def ask(prompt):
    """Pose une question et lit la réponse.

    Toute la session ne doit avoir QU'UN seul lecteur de stdin : deux
    input() concurrents (question du wizard + abandon par Entree d'une
    ecoute) se volent des lignes. Les questions passent donc par la
    file du lecteur dedie (voir plus bas), demarre au premier appel.
    Les lignes deja arrivees sont servies avant la sentinel d'EOF.
    """
    start_stdin_reader()
    print(c(C_PROMPT, prompt), end="", flush=True)
    line = _stdin_lines.get()
    if line is None:
        print("\nEntrée fermée : arrêt de l'assistant.")
        raise SystemExit(1)
    return line


# Un seul lecteur de stdin, partagé par toute la session : voir ask().
_stdin_lines = queue.Queue()
_stdin_reader_done = threading.Event()
_stdin_closed = threading.Event()
_stdin_thread_started = threading.Event()


def _stdin_reader():
    try:
        while True:
            line = input()
            _stdin_lines.put(line)
    except (EOFError, OSError, ValueError, KeyboardInterrupt):
        pass
    finally:
        _stdin_closed.set()
        _stdin_reader_done.set()
        _stdin_lines.put(None)  # sentinel : EOF, tout ask() échoue


def start_stdin_reader():
    """Démarre l'unique lecteur de stdin, en arrière-plan."""
    if _stdin_thread_started.is_set():
        return
    _stdin_thread_started.set()
    threading.Thread(target=_stdin_reader, daemon=True).start()


def stdin_typed_line():
    """Ligne tapée, sans bloquer : la ligne, "" si Entrée seul, None si rien.

    Pour les écoutes ("Entrée = abandonner") : elles sondent la file
    du lecteur dédié au lieu de faire leur propre input(), donc elles
    ne peuvent plus voler la réponse d'une question. Renvoie None
    s'il n'y a rien de tapé. Entrée fermée (stdin redirigé, tests,
    scripts) : renvoie aussi None. Sans clavier, l'écoute va au bout
    de son délai ou de sa condition, comme un simple timeout.
    """
    if not _stdin_thread_started.is_set():
        start_stdin_reader()
    if _stdin_closed.is_set() and _stdin_lines.empty():
        return None
    try:
        line = _stdin_lines.get(timeout=0.2)
    except queue.Empty:
        return None
    if line is None:  # EOF : plus rien à lire, écoute en délai simple
        _stdin_lines.put(None)  # remettre la sentinelle pour les suivants
        return None
    return line


def wait_enter_or(stop_condition, timeout, step=0.5):
    """Attend Entrée ou une condition, sans bloquer stdin.

    True si Entrée tapée, False si stop_condition(), None si délai écoulé.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = stdin_typed_line()
        if line is not None:
            return True
        if stop_condition is not None and stop_condition():
            return False
        time.sleep(step)
    return None


def ask_int(prompt, low, high, default):
    raw = ask("{} [{}] : ".format(prompt, default)).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if low <= value <= high else default


def states_of(entity):
    return "states('" + entity + "')"


# --------------------------------------------------------------------------
# Fragments YAML (un dict de listes de lignes par module)
# --------------------------------------------------------------------------

def frag_sensor_rest(name, uid, ip, token, suffix, unit, scan):
    """Capteur REST lisant l'état du module dans server.xml."""
    return [
        "    # {} : lecture directe du Hub (UID {})".format(name, uid),
        "  - platform: rest",
        "    name: {} {}".format(name, suffix),
        "    resource: http://{}/{}".format(ip, HUB_PORT_PATH),
        "    method: GET",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
        "    value_template: >-",
        '      {{% set m = value_json.data.table | selectattr("uid", "equalto", "{}") | list | first %}}'.format(uid),
        "      {{ m.var | default(0) }}",
        '    unit_of_measurement: "{}"'.format(unit),
        "    scan_interval: {}".format(scan),
    ]


def frag_light(module):
    name, uid = module["name"], module["uid"]
    slug = module.get("slug") or slugify(name)
    on, off = "yokis_{}_on".format(slug), "yokis_{}_off".format(slug)
    sensor = "sensor.{}_etat".format(slug)
    ip, token = module["ip"], module["token"]

    rest = [
        "  # {} : lampe (UID {})".format(name, uid),
        "  {}:".format(on),
        '    url: "http://{}/command.xml?action=order&id={}&order=on"'.format(ip, uid),
        "    method: get",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
        "  {}:".format(off),
        '    url: "http://{}/command.xml?action=order&id={}&order=off"'.format(ip, uid),
        "    method: get",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
    ]
    sensor = frag_sensor_rest(name, uid, ip, token, "Etat", "%", SCAN_INTERVAL["light"])
    tpl_light = [
        "      # {} : lampe".format(name),
        "      - name: {}".format(name),
        '        unique_id: "light_{}"'.format(slug),
        "        turn_on:",
        "          - action: rest_command.{}".format(on),
        "        turn_off:",
        "          - action: rest_command.{}".format(off),
        "        state: >-",
        "          {{ " + states_of(sensor_name(module)) + " | int(0) == 100 }}",
        "        availability: >-",
        "          {{ " + states_of(sensor_name(module)) + " not in ['unavailable', 'unknown', None, ''] }}",
    ]
    return {"rest": rest, "sensors": sensor, "tpl_lights": tpl_light}


def sensor_name(module):
    return "sensor.{}_etat".format(slugify(module["name"]))


def frag_cover(module):
    name, uid = module["name"], module["uid"]
    slug = module.get("slug") or slugify(name)
    cmd_pos = "yokis_{}_set_position".format(slug)
    sensor_brut = "sensor.{}_brut".format(slug)
    sensor_lis = "sensor.{}".format(slug)
    ip, token = module["ip"], module["token"]

    rest = [
        "  # {} : volet roulant (UID {})".format(name, uid),
        "  {}:".format(cmd_pos),
        '    url: "http://{}/command.xml?action=order&id={}&order=varX&ext1={{{{ position }}}}"'.format(ip, uid),
        "    method: get",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
    ]
    sensor = frag_sensor_rest(name, uid, ip, token, "Brut", "%", SCAN_INTERVAL["cover"])
    tpl_sensor = [
        "      # {} : reprend la dernière valeur si le Hub répond mal".format(name),
        "      - name: {}".format(name),
        '        unique_id: "sensor_{}"'.format(slug),
        '        unit_of_measurement: "%"',
        "        state: >-",
        "          {% if " + states_of(sensor_brut) + " not in ['unknown', 'unavailable', '', None] %}",
        "            {{ " + states_of(sensor_brut) + " }}",
        "          {% else %}",
        "            {{ " + states_of(sensor_lis) + " }}",
        "          {% endif %}",
    ]
    tpl_cover = [
        "      # {} : volet roulant".format(name),
        "      - name: {}".format(name),
        '        unique_id: "cover_{}"'.format(slug),
        "        position: >-",
        "          {{ " + states_of(sensor_lis) + " | int(0) }}",
        "        set_cover_position:",
        "          - action: rest_command.{}".format(cmd_pos),
        "            data:",
        '              position: "{{ position }}"',
        "        icon: >-",
        "          {% set p = " + states_of(sensor_lis) + " | int(0) %}",
        "          {% if p == 0 %} mdi:blinds",
        "          {% elif p == 100 %} mdi:blinds-open",
        "          {% else %} mdi:blinds-horizontal",
        "          {% endif %}",
    ]
    return {"rest": rest, "sensors": sensor,
            "tpl_sensors": tpl_sensor, "tpl_covers": tpl_cover}


def frag_gate(module):
    name, uid = module["name"], module["uid"]
    slug = module.get("slug") or slugify(name)
    cmd_toggle = "yokis_{}_toggle".format(slug)
    ip, token = module["ip"], module["token"]

    rest = [
        "  # {} : impulsion (UID {}) : la même commande ouvre et ferme".format(name, uid),
        "  {}:".format(cmd_toggle),
        '    url: "http://{}/command.xml?action=order&id={}&order=on"'.format(ip, uid),
        "    method: get",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
    ]
    tpl_cover = [
        "      # {} : portail (impulsion : ouvrir/fermer/stop identiques)".format(name),
        "      - name: {}".format(name),
        '        unique_id: "cover_{}"'.format(slug),
        "        open_cover:",
        "          - action: rest_command.{}".format(cmd_toggle),
        "        close_cover:",
        "          - action: rest_command.{}".format(cmd_toggle),
        "        stop_cover:",
        "          - action: rest_command.{}".format(cmd_toggle),
        "        icon: mdi:gate",
    ]
    return {"rest": rest, "sensors": [], "tpl_covers": tpl_cover}


def frag_switch(module):
    name, uid = module["name"], module["uid"]
    slug = module.get("slug") or slugify(name)
    on, off = "yokis_{}_on".format(slug), "yokis_{}_off".format(slug)
    ip, token = module["ip"], module["token"]

    rest = [
        "  # {} : interrupteur (UID {})".format(name, uid),
        "  {}:".format(on),
        '    url: "http://{}/command.xml?action=order&id={}&order=on"'.format(ip, uid),
        "    method: get",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
        "  {}:".format(off),
        '    url: "http://{}/command.xml?action=order&id={}&order=off"'.format(ip, uid),
        "    method: get",
        "    headers:",
        '      Authorization: "Basic {}"'.format(token),
    ]
    sensor = frag_sensor_rest(name, uid, ip, token, "Etat", "%", SCAN_INTERVAL["switch"])
    tpl_switch = [
        "      # {} : interrupteur".format(name),
        "      - name: {}".format(name),
        '        unique_id: "switch_{}"'.format(slug),
        "        turn_on:",
        "          - action: rest_command.{}".format(on),
        "        turn_off:",
        "          - action: rest_command.{}".format(off),
        "        state: >-",
        "          {{ " + states_of(sensor_name(module)) + " | int(0) == 100 }}",
        "        availability: >-",
        "          {{ " + states_of(sensor_name(module)) + " not in ['unavailable', 'unknown', None, ''] }}",
    ]
    return {"rest": rest, "sensors": sensor, "tpl_switches": tpl_switch}


BUILDERS = {"light": frag_light, "cover": frag_cover,
            "gate": frag_gate, "switch": frag_switch}


def dedupe_slugs(modules):
    """Rend chaque identifiant unique : suffixe _2, _3... en cas de collision."""
    seen = {}
    for module in modules:
        slug = slugify(module["name"])
        if slug in seen:
            seen[slug] += 1
            new_slug = "{}_{}".format(slug, seen[slug])
            print(c(C_WARN, "  [!] {} : identifiant déjà pris, ajusté en {}"
                  .format(module["name"], new_slug)))
            module["slug"] = new_slug
        else:
            seen[slug] = 1
            module["slug"] = slug
    return modules


def build_yaml(modules, ip, token):
    """Assemble un seul fichier à clés racine uniques."""
    rest, sensors = [], []
    tpl_lights, tpl_sensors, tpl_covers, tpl_switches = [], [], [], []

    for module in modules:
        parts = BUILDERS[module["type"]](module)
        rest.extend(parts["rest"])
        sensors.extend(parts.get("sensors", []))
        tpl_lights.extend(parts.get("tpl_lights", []))
        tpl_sensors.extend(parts.get("tpl_sensors", []))
        tpl_covers.extend(parts.get("tpl_covers", []))
        tpl_switches.extend(parts.get("tpl_switches", []))

    out = [
        "# YokisHub4HomeAssistant : blocs générés par l'assistant",
        "# Hub : {}".format(ip),
        "# Généré le : {}".format(datetime.date.today().isoformat()),
        "#",
        "# ATTENTION : ce fichier contient votre token (accès à vos équipements).",
        "# Ne le partagez pas, ne le versionnez pas dans un dépôt public.",
        "#",
        "# INTEGRATION (selon votre configuration.yaml) :",
        "#  • si vous n'avez PAS encore de clés rest_command:/sensor:/template:",
        "#    collez ce fichier ENTIER à la fin.",
        "#  • si vous les AVEZ DÉJÀ (c'est le cas si vous pilotez autre chose en REST) :",
        "#    ne recollez PAS ces clés. Fusionnez à la main, en déplaçant les entrées",
        "#    indentées de ce fichier SOUS vos clés existantes. Un YAML avec deux fois",
        "#    la même clé racine est refusé par Home Assistant.",
        "#",
        "# Puis : Paramètres > Outils de développement > Vérifier la configuration,",
        "# et redémarrez Home Assistant.",
        "",
        "# ============================================================",
        "# 1. Commandes REST vers le Hub",
        "# ============================================================",
        "rest_command:",
    ]
    out.extend(rest)

    if sensors:
        out += ["",
                "# ============================================================",
                "# 2. Capteurs REST (état lu sur server.xml)",
                "# ============================================================",
                "sensor:"]
        out.extend(sensors)

    template_groups = []
    if tpl_sensors:
        template_groups.append(["  - sensor:"] + tpl_sensors)
    if tpl_lights:
        template_groups.append(["  - light:"] + tpl_lights)
    if tpl_switches:
        template_groups.append(["  - switch:"] + tpl_switches)
    if tpl_covers:
        template_groups.append(["  - cover:"] + tpl_covers)
    if template_groups:
        out += ["",
                "# ============================================================",
                "# 3. Entités template (reprise + lampe/interrupteur/volet)",
                "# ============================================================",
                "template:"]
        for group in template_groups:
            out.extend(group)

    out.append("")
    return "\n".join(out)


def write_recap_page(modules, yaml_text, ip):
    """Page HTML récapitulative : le YAML complet + boutons Copier par module.

    Fichier local yokis_recap.html, à côté du YAML. Contient la même
    information que le fichier YAML (dont le token). Même consigne :
    ne pas partager, ne pas versionner.
    """
    import html as _html

    cards = []
    for module in modules:
        label = "{} : {} ({})".format(
            module["name"], TYPE_LABELS[module["type"]], module["uid"])
        parts = BUILDERS[module["type"]](module)
        block_lines = ["rest_command:"] + parts["rest"]
        if parts.get("sensors"):
            block_lines += ["", "sensor:"] + parts["sensors"]
        tpl_order = [("tpl_sensors", "sensor"), ("tpl_lights", "light"),
                     ("tpl_switches", "switch"), ("tpl_covers", "cover")]
        tpl_present = [pair for pair in tpl_order if parts.get(pair[0])]
        if tpl_present:
            block_lines.append("")
            block_lines.append("template:")
            for key, parent in tpl_present:
                block_lines += ["  - {}:".format(parent)] + parts[key]
        block = "\n".join(block_lines)
        cards.append(
            '<div class="card"><h2>✅ {}</h2>'
            '<pre>{}</pre>'
            '<button onclick="copyBlock(this)">Copier ce module</button></div>'
            .format(_html.escape(label), _html.escape(block)))

    page = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>YokisHub4HomeAssistant : récapitulatif</title>
<style>
  body {{ background: #0b0f14; color: #e8f0f7;
    font-family: "Segoe UI", system-ui, sans-serif; margin: 0; padding: 28px; }}
  .wrap {{ max-width: 880px; margin: 0 auto; }}
  h1 {{ font-size: 24px; }} h1 .ok {{ color: #2fd6b0; }}
  .card {{ background: #121822; border: 1px solid #1e2735; border-radius: 14px;
    padding: 16px; margin: 16px 0; }}
  .card h2 {{ font-size: 16px; margin: 0 0 10px; }}
  pre {{ background: #0a0f17; border: 1px solid #1e2735; border-radius: 10px;
    padding: 12px; overflow: auto; font-size: 12.5px; max-height: 320px; }}
  button {{ background: #ee2e31; color: #fff; border: none; border-radius: 8px;
    padding: 9px 14px; cursor: pointer; font-size: 13.5px; }}
  button.done {{ background: #2fd6b0; }}
  .steps {{ background: #121822; border: 1px solid #1e2735; border-radius: 14px;
    padding: 16px 20px; margin: 20px 0; line-height: 1.7; font-size: 14px; }}
  .warn {{ color: #ffb9bb; }}
</style>
</head>
<body>
<div class="wrap">
  <h1><span class="ok">✅ Réussi</span> : {n} module(s) connecté(s) au Hub {ip}</h1>
  <div class="steps">
    <strong>Marche à suivre :</strong><br>
    1. Copiez chaque bloc ci-dessous (bouton Copier).<br>
    2. Si vos clés <code>rest_command:</code> / <code>sensor:</code> / <code>template:</code>
       n'existent pas encore : collez le tout à la fin de <code>configuration.yaml</code>.<br>
    3. Si elles existent déjà : fusionnez les entrées <strong>sous</strong> vos clés
       existantes. Ne recollez jamais la clé racine.<br>
    4. Paramètres &gt; Outils de développement &gt; Vérifier la configuration,
       puis redémarrez Home Assistant.<br>
    <span class="warn">Cette page contient votre token : ne la partagez pas.</span>
  </div>
  {cards}
  <div class="card"><h2>📦 Tout-en-un (fichier complet)</h2>
  <pre id="all">{full}</pre>
  <button onclick="navigator.clipboard.writeText(document.getElementById('all').textContent).then(()=>{{this.textContent='Copié ✓';this.className='done';}})">Copier tout</button></div>
</div>
<script>
function copyBlock(btn) {{
  const txt = btn.previousElementSibling.textContent;
  navigator.clipboard.writeText(txt).then(() => {{
    btn.textContent = 'Copié ✓'; btn.className = 'done';
    setTimeout(() => {{ btn.textContent = 'Copier ce module'; btn.className = ''; }}, 1500);
  }});
}}
</script>
</body>
</html>""".format(n=len(modules), ip=_html.escape(ip),
                 cards="\n".join(cards),
                 full=_html.escape(yaml_text))

    recap_path = "yokis_recap.html"
    with open(recap_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(page)
    return __import__("os").path.abspath(recap_path)


# --------------------------------------------------------------------------
# Assistant interactif
# --------------------------------------------------------------------------

def read_credentials():
    """Saisie de secours, quand la capture automatique n'a rien donné.

    Accepte le token seul, l'en-tête `Authorization: Basic ...` ou la
    requête entière `.../command.xml?action=order&id=<UID>&...` : le token
    et l'UID du module sont extraits de ce qui est collé, donc un extrait
    de capture réseau (PCAPdroid) fonctionne tel quel.

    Renvoie (token, uid) : uid vaut None quand la requête n'en portait pas.
    """
    print("Collez votre token Base64, ou la requête interceptée entière")
    print("(voir README, section token) : le token et l'UID du module en")
    print("seront extraits.")
    raw = ask("  Token / requête : ").strip()
    if not raw:
        print("Rien collé.")
        raise SystemExit(1)
    token = token_from_text(raw)
    if not token:
        print("Aucun token lisible là-dedans.")
        raise SystemExit(1)
    return token, split_command_url(raw)


def split_auth_header(value):
    """Découpe un en-tête Authorization: Basic <base64>.

    Renvoie le token (partie après Basic), ou None si l'en-tête ne
    correspond pas. Le token lui-même n'est jamais affiché ni loggé
    en entier par l'assistant (voir mask_token).
    """
    if not value:
        return None
    parts = value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "basic" or not parts[1].strip():
        return None
    return parts[1].strip()


BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                   "abcdefghijklmnopqrstuvwxyz0123456789+/=")


def looks_like_token(value):
    """Un token HTTP Basic est du Base64 : alphabet restreint, longueur utile."""
    return len(value) >= 8 and set(value) <= BASE64_CHARS


def token_from_text(text):
    """Token lu dans un texte collé : en-tête Authorization, ou token seul.

    Un extrait de capture réseau contient les deux : la ligne de requête
    (d'où vient l'UID, voir split_command_url) et l'en-tête
    `Authorization: Basic ...` juste en dessous.
    """
    for line in (text or "").splitlines():
        candidate = line.strip()
        if candidate.lower().startswith("authorization"):
            candidate = candidate.split(":", 1)[-1].strip()
        token = split_auth_header(candidate)
        if not token and looks_like_token(candidate):
            token = candidate
        if token:
            return token
    return None


def split_command_url(text):
    """UID d'un `.../command.xml?action=order&id=<UID>&...`, URL ou extrait collé.

    Accepte une URL seule comme une ligne de requête capturée entière
    (`GET http://IP/command.xml?... HTTP/1.1`) : chaque morceau séparé par
    un espace est essayé comme une URL.
    """
    from urllib.parse import urlparse, parse_qs
    for chunk in (text or "").replace("\r", " ").split():
        try:
            ids = parse_qs(urlparse(chunk).query).get("id")
        except ValueError:
            continue
        if ids and ids[0]:
            return ids[0]
    return None


def default_route_ip():
    """Source IP de la route par défaut (ce que le téléphone doit viser).

    Un simple connect UDP vers un hôte public renvoie l'IP de sortie
    réelle : avec vEthernet/WSL/VPN, ce n'est pas le premier /24 listé.
    """
    for dest in ("1.1.1.1", "8.8.8.8", "9.9.9.9"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((dest, 1))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            pass
        finally:
            sock.close()
    return None


def local_pc_ip():
    """IP locale de ce PC sur le LAN (pour le réglage proxy du téléphone).

    Privilège la source de la route par défaut, puis 192.168.* (Wi‑Fi
    maison) : avec WSL/VPN, 172.16-31 ou 10.x peuvent apparaître en
    premier et le téléphone ne joindrait pas ce proxy.
    """
    preferred = default_route_ip()
    if preferred and is_private_lan(preferred):
        return preferred
    ips = local_ipv4s()
    private = [ip for ip in ips if is_private_lan(ip)]
    for ip in private:
        if ip.startswith("192.168."):
            return ip
    if private:
        return private[0]
    if preferred:
        return preferred
    if ips:
        return ips[0]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return "?"
    finally:
        sock.close()


def lan_prefixes():
    """Préfixes /24 de TOUTES les interfaces privées (clients acceptés)."""
    prefixes = []
    # Route par défaut d'abord : le préfixe du téléphone est souvent celui-là.
    preferred = default_route_ip()
    candidates = ([preferred] if preferred else []) + local_ipv4s()
    for ip in candidates:
        if ip and is_private_lan(ip):
            prefix = ip.rsplit(".", 1)[0]
            if prefix not in prefixes:
                prefixes.append(prefix)
    return prefixes


def lan_prefix():
    """Préfixe /24 principal du PC (compat : premier préfixe privé)."""
    prefixes = lan_prefixes()
    return prefixes[0] if prefixes else None


def pipe_both(client, upstream):
    """Recopie les octets dans les deux sens, jusqu'à fermeture (tunnel HTTPS)."""
    import threading

    def pump(src, dst):
        try:
            while True:
                chunk = src.recv(8192)
                if not chunk:
                    break
                dst.sendall(chunk)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    threading.Thread(target=pump, args=(client, upstream), daemon=True).start()
    pump(upstream, client)


class HubProxy:
    """Proxy HTTP local transparent : capte le token du Hub au passage.

    Le Hub n'accepte que du HTTP Basic, et le token circule en clair dans la
    requête que l'app Yokis lui envoie. En déclarant ce PC comme proxy du
    Wi-Fi du téléphone, cette requête passe par ici : on y lit l'en-tête
    Authorization, puis on la relaie sans y toucher, donc l'action aboutit
    normalement dans la maison.

    Le proxy est TRANSPARENT : il relaie tout ce que le téléphone envoie,
    HTTP vers n'importe quel hôte et HTTPS en tunnel (jamais déchiffré).
    C'est indispensable, l'app Yokis parle aussi à son cloud : un proxy qui
    ne relaierait que le Hub la ferait décrocher. Rien n'est écrit sur disque
    ni journalisé ; la seule requête lue est celle qui porte un ordre vers le
    Hub (command.xml), pour en extraire le token et l'UID du module.

    Il n'accepte que les clients du réseau local, et reste ouvert pendant
    toute la session : l'app doit continuer de fonctionner pendant que
    l'assistant écoute le Hub pour les modules suivants. C'est close_proxy
    qui le referme.
    """

    def __init__(self, ip, timeout=180):
        self.ip = ip
        self.timeout = timeout
        self.token = None
        self.uid = None
        self.announced = False
        self._httpd = None
        self._prefix = lan_prefix()
        self._prefixes = lan_prefixes()

    def client_allowed(self, address):
        """Boucle locale + clients des /24 privés de cette machine."""
        if address.startswith("::ffff:"):
            address = address[7:]
        if address in ("127.0.0.1", "::1"):
            return True
        if not is_private_lan(address):
            return False
        prefix = address.rsplit(".", 1)[0]
        if not self._prefixes:
            # Pas d'interface privée détectée : au moins un /24 deviné.
            if self._prefix:
                return prefix == self._prefix
            return False
        return prefix in self._prefixes

    def start(self, port=0):
        """Ouvre le proxy. Renvoie le port retenu, ou None si c'est impossible."""
        import threading
        from http.client import HTTPConnection
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        proxy = self

        class ProxyHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def handle_one_request(self):
                """Un client qui coupe la connexion (app qui passe à autre chose)
                ne doit pas faire sortir de traceback dans la console."""
                try:
                    BaseHTTPRequestHandler.handle_one_request(self)
                except OSError:
                    self.close_connection = True

            def _reply(self, code, message):
                """Réponse courte en texte brut (refus, erreur de relais)."""
                body = (message + "\n").encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def _target(self):
                """(hôte, chemin) : URL absolue si le client utilise le proxy,
                sinon chemin brut + en-tête Host (client direct)."""
                from urllib.parse import urlsplit
                if self.path.lower().startswith(("http://", "https://")):
                    parts = urlsplit(self.path)
                    query = "?" + parts.query if parts.query else ""
                    return parts.netloc, parts.path + query
                return self.headers.get("Host", ""), self.path

            def _capture(self, path):
                """Token et UID, lus dans une requête d'ordre vers le Hub."""
                if proxy.token is not None or "command.xml" not in path.lower():
                    return
                token = split_auth_header(self.headers.get("Authorization"))
                if token:
                    proxy.token = token
                    proxy.uid = split_command_url(path)

            def _relay(self):
                if not proxy.client_allowed(self.client_address[0]):
                    self._reply(403, "YokisHub4HomeAssistant : proxy réservé "
                                     "au réseau local")
                    return
                host, path = self._target()
                server, _, port = host.partition(":")
                if not server:
                    self._reply(400, "YokisHub4HomeAssistant : hôte inconnu")
                    return
                # Capture AVANT le relais : le token et l'UID sont acquis
                # même si le Hub ne répond pas à cet ordre.
                self._capture(path)
                length = int(self.headers.get("Content-Length") or 0)
                if length > 64 * 1024 * 1024:
                    self._reply(413, "YokisHub4HomeAssistant : corps trop gros "
                                     "pour le proxy")
                    return
                body = self.rfile.read(length) if length else None
                headers = {}
                for key, value in self.headers.items():
                    if key.lower() in ("host", "content-length", "connection",
                                       "keep-alive", "proxy-connection",
                                       "proxy-authorization", "upgrade",
                                       "transfer-encoding"):
                        continue
                    headers[key] = value
                headers["Connection"] = "close"
                try:
                    upstream = HTTPConnection(server, int(port or 80), timeout=20)
                except ValueError:
                    self._reply(400, "YokisHub4HomeAssistant : port illisible")
                    return
                try:
                    upstream.request(self.command, path, body=body,
                                     headers=headers)
                    response = upstream.getresponse()
                    self.send_response(response.status, response.reason)
                    for key, value in response.getheaders():
                        if key.lower() in ("content-length", "connection",
                                           "transfer-encoding"):
                            continue
                        self.send_header(key, value)
                    declared = response.getheader("Content-Length")
                    if declared:
                        self.send_header("Content-Length", declared)
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    # Relais en flux : pas de gros fichier en mémoire.
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                except Exception as exc:
                    self._reply(502, "Hôte injoignable : {}".format(exc))
                finally:
                    upstream.close()

            def do_CONNECT(self):
                """HTTPS : tunnel brut, jamais déchiffré (l'app en a besoin)."""
                if not proxy.client_allowed(self.client_address[0]):
                    self._reply(403, "YokisHub4HomeAssistant : proxy réservé "
                                     "au réseau local")
                    return
                server, _, port = self.path.partition(":")
                try:
                    upstream = socket.create_connection(
                        (server, int(port or 443)), timeout=20)
                except (OSError, ValueError) as exc:
                    self._reply(502, "Tunnel impossible : {}".format(exc))
                    return
                self.close_connection = True
                self.send_response(200, "Connection established")
                self.end_headers()
                try:
                    pipe_both(self.connection, upstream)
                finally:
                    upstream.close()

            do_GET = _relay
            do_POST = _relay
            do_PUT = _relay
            do_HEAD = _relay
            do_PATCH = _relay

        try:
            self._httpd = ThreadingHTTPServer(("0.0.0.0", port), ProxyHandler)
        except OSError as exc:
            print("Proxy impossible à ouvrir : {}".format(exc))
            return None
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        return self._httpd.server_address[1]

    def announce(self, port):
        """Explique le réglage proxy à faire sur le téléphone."""
        self.announced = True
        host = local_pc_ip()
        others = [ip for ip in local_ipv4s()
                  if is_private_lan(ip) and ip != host]
        print(c(C_TITLE, "\n=== Token : capture automatique ==="))
        print("Le Hub n'accepte que du HTTP Basic, et le token circule en clair")
        print("dans la requête que l'app Yokis lui envoie : elle passera par ici.")
        print("")
        print("  Sur votre téléphone (même Wi-Fi que ce PC) :")
        print("  1. Wi-Fi > réseau actuel > Proxy : Manuel")
        print("     Nom d'hôte : {}    Port : {}".format(host, port))
        if others:
            print(c(C_DIM, "  (si ça ne marche pas, essayer aussi : {})"
                  .format(", ".join(others))))
        print("  2. Dans l'app Yokis, agissez sur l'équipement à connecter")
        print("     (baissez le volet, allumez la lampe...).")
        print("  3. Revenez ici : la capture se fait toute seule.")
        print("")
        print(c(C_DIM, "  (le proxy relaie tout ce que votre téléphone envoie, comme"))
        print(c(C_DIM, "   n'importe quel proxy : l'app et ses accès internet continuent"))
        print(c(C_DIM, "   de marcher, rien n'est enregistré. Seule la requête d'ordre"))
        print(c(C_DIM, "   vers le Hub est lue, pour le token et l'UID du module.)"))

    def wait_for_token(self):
        """Attend la requête de l'app. Renvoie (token, uid), ou (None, None)."""
        print(c(C_WARN, "\nEn écoute sur le proxy... ({} s max, Entrée = abandonner)"
              .format(self.timeout)))

        def captured():
            return self.token is not None

        wait_enter_or(captured, self.timeout, step=1)
        # True = Entrée (abandon) ; False = capture ; None = délai écoulé
        print("")
        if not self.token:
            return None, None
        print(c(C_OK, "  ✅ Requête interceptée : token capturé, module {} !"
              .format(self.uid or "(UID illisible)")))
        self.check_token()
        return self.token, self.uid

    def check_token(self):
        """Vérifie le token capturé contre le Hub (une lecture, aucun ordre).

        Un token d'un autre Hub, ou tronqué à la copie, se voit tout de
        suite ici plutôt que trois écrans plus loin.
        """
        try:
            fetch_table(self.ip, self.token)
        except HubError as exc:
            print(c(C_WARN, "  (le Hub {} refuse ce token : {})"
                  .format(self.ip, exc)))
            return
        print(c(C_DIM, "  (token accepté par le Hub {})".format(self.ip)))

    def stop(self):
        """Referme le proxy (sans effet s'il n'a jamais été ouvert)."""
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None


def close_proxy(proxy):
    """Referme le proxy et rappelle de retirer le réglage sur le téléphone."""
    if proxy is None:
        return
    announced = proxy.announced
    proxy.stop()
    if announced:
        print("")
        print(c(C_WARN, "Rappel : dans le Wi-Fi de votre téléphone, remettez "
              "Proxy sur Aucun."))


def read_hub_ip(token=None):
    print(c(C_TITLE, "\n=== Adresse du Hub ==="))
    print("  1. je la connais déjà (ex : 192.168.0.156)")
    print("  2. scanner le réseau local (~254 adresses, quelques secondes)")
    choice = ask("Votre choix (1/2) [2] : ").strip() or "2"
    if choice == "1":
        return ask("  IP du Hub : ").strip()
    print("Scan du réseau local (toutes les interfaces, cache ARP d'abord)...")
    found = scan_lan(token)
    if not found:
        explain_scan_failure()
        return ask("  IP du Hub : ").strip()
    if len(found) == 1:
        single_ip, single_count = found[0]
        if single_count is not None:
            print("Hub trouvé : {} ({} modules).".format(single_ip, single_count))
        return single_ip
    print("Plusieurs Hubs répondent :")
    for index, (hub_ip, count) in enumerate(found, 1):
        extra = " ({} modules)".format(count) if count is not None else ""
        print("  {}) {}{}".format(index, hub_ip, extra))
    pick = ask_int("Lequel", 1, len(found), 1)
    return found[pick - 1][0]


def print_table(table):
    print("\n{:<12} {:<7} {:<6} {:<6}".format("UID", "vivant", "var", "data"))
    print("-" * 38)
    for entry in table:
        print("{:<12} {:<7} {:<6} {:<6}".format(
            entry.get("uid", "?"),
            "oui" if entry.get("alive") else "non",
            entry.get("var", "?"),
            entry.get("data", "?"),
        ))


def name_modules(table, ip, token, uid_hint=None):
    modules = []
    print(c(C_TITLE, "\n=== Vos équipements ==="))
    if uid_hint:
        # Le module a déjà été actionné pendant la capture (ou collé) : on
        # demande de quel équipement il s'agissait, pas ce qu'on veut faire.
        print("Quel équipement venez-vous d'actionner ?")
    else:
        print("Quel équipement voulez-vous connecter ?")
    print("  1) Lumière  2) Volet roulant  3) Portail / porte de garage  4) Interrupteur")
    pick = ask_int("Votre choix", 1, 4, 2)
    etype = {1: "light", 2: "cover", 3: "gate", 4: "switch"}[pick]
    print("\n→ {} sélectionné.".format(TYPE_LABELS[etype]))
    raw_name = ask("Nom pour cet équipement (ex : Lumière Terrasse / Volet Chambre) : ").strip()
    name = raw_name or {"light": "Lumière", "cover": "Volet",
                        "gate": "Portail", "switch": "Interrupteur"}[etype]

    uid = None
    if uid_hint:
        confirm = ask('Le module détecté pendant la capture est {} : le garder ? (O/n) : '
                      .format(uid_hint)).strip().lower()
        if confirm in ("", "o", "oui", "y", "yes"):
            uid = uid_hint
    if uid is None:
        print("Agissez sur l'équipement avec l'application Yokis (allumez une lumière,")
        print("faites bouger un volet, donnez une impulsion au portail).")
        uid = listen_for_action(ip, token, etype)
    if uid is None:
        print("\nAucune action détectée. Rien à générer pour cet équipement.")
    else:
        modules.append({"name": name, "uid": uid, "type": etype,
                        "ip": ip, "token": token})
        print(c(C_OK, '\n✅ Trouvé : {} ({}) : "{}"'.format(name, uid, TYPE_LABELS[etype])))

    while True:
        more = ask("\nConnecter un autre équipement ? (o/N) : ").strip().lower()
        if more != "o":
            break
        extra = name_modules(table, ip, token)
        modules.extend(extra)
    return modules


def listen_for_action(ip, token, etype, timeout=120):
    """Écoute le Hub et renvoie l'UID du module que l'utilisateur actionne.

    Protocole : l'utilisateur agit sur l'équipement depuis l'app Yokis
    (ou l'interrupteur mural) pendant que le Hub est interrogé toutes les
    2 s. Le premier module dont var/data change est celui qu'on vient
    d'actionner : détection immédiate, pas d'attente supplémentaire.
    Entrée (ou délai dépassé) = abandon. Si plusieurs modules ont bougé
    entre deux lectures, on demande lequel est le bon.
    """
    print(c(C_WARN, "\nEn attente de votre action... ({} s max, Entrée = abandonner)"
          .format(timeout)))

    try:
        before = snapshot_table(ip, token)
    except HubError as exc:
        print("Lecture impossible : {}".format(exc))
        return None

    found = []
    elapsed = 0
    step = 2
    try:
        while elapsed < timeout:
            line = stdin_typed_line()
            if line is not None:
                print("")
                return None
            time.sleep(step)
            elapsed += step
            try:
                after = snapshot_table(ip, token)
            except HubError:
                continue
            for uid in diff_snapshots(before, after):
                if uid not in found:
                    found.append(uid)
                    print(c(C_OK, "  ✅ {} : module {} a bougé !".format(
                        time.strftime("%H:%M:%S"), uid)))
            before = after
            if found:
                break
        print("")
    except KeyboardInterrupt:
        print("")
        return None

    if not found:
        return None
    if len(found) == 1:
        return found[0]
    print("Plusieurs modules ont bougé :")
    for index, uid in enumerate(found, 1):
        print("  {}) {}".format(index, uid))
    pick = ask_int("Lequel est le vôtre", 1, len(found), 1)
    return found[pick - 1]


def run_wizard(args):
    clear_screen()
    print(c(C_TITLE, "=" * 62
          + "\n YokisHub4HomeAssistant : assistant de configuration"
          + "\n Découverte des modules + génération du YAML Home Assistant"
          + "\n" + "=" * 62))

    ip = args.ip or read_hub_ip()
    if not ip:
        print("Pas d'IP : arrêt.")
        raise SystemExit(1)

    if not hub_fingerprint(ip):
        print("Ce n'est pas un Yokis Hub (pas de 401 Basic Protected) : arrêt.")
        raise SystemExit(1)
    print(c(C_OK, "\n[OK] Yokis Hub confirmé : {}".format(ip)))

    token, uid_hint, proxy = acquire_token(ip, args)
    try:
        run_session(args, ip, token, uid_hint)
    finally:
        close_proxy(proxy)


def acquire_token(ip, args):
    """Token du Hub : capture automatique d'abord, saisie collée en secours.

    Renvoie (token, uid_hint, proxy). Le proxy reste ouvert pendant toute
    la session : l'app Yokis doit continuer de fonctionner pendant que
    l'assistant écoute le Hub (sinon l'action suivante échouerait), et
    c'est close_proxy qui le referme à la fin.
    """
    if args.token:
        print("Token fourni : {}".format(mask_token(args.token)))
        return args.token, None, None

    proxy_timeout = 180
    try:
        if not sys.stdin.isatty():
            proxy_timeout = 8
    except Exception:
        proxy_timeout = 8
    proxy = HubProxy(ip, timeout=proxy_timeout)
    port = proxy.start()
    if port:
        proxy.announce(port)
        token, uid = proxy.wait_for_token()
        if token:
            print("Token capturé : {}".format(mask_token(token)))
            return token, uid, proxy
        print("Aucune requête interceptée.")
    else:
        proxy = None
        print("Capture automatique indisponible.")

    retry = ask("Coller le token à la main ? (o/N) : ").strip().lower()
    if retry != "o":
        close_proxy(proxy)
        raise SystemExit(1)
    token, uid = read_credentials()
    return token, uid, proxy


def run_session(args, ip, token, uid_hint):
    """Table du Hub, nommage des équipements, YAML et page récapitulative."""

    try:
        table = fetch_table(ip, token)
    except HubError as exc:
        print("Échec : {}".format(exc))
        raise SystemExit(1)

    print(c(C_OK, "\n[OK] Hub {} joignable : {} modules dans la table."
          .format(ip, len(table))))

    modules = name_modules(table, ip, token, uid_hint)
    if not modules:
        print("\nAucun module nommé : rien à générer.")
        return

    print(c(C_TITLE, "\n=== Récapitulatif ==="))
    for module in modules:
        print("  {:<28} {}  ({})".format(
            module["name"], TYPE_LABELS[module["type"]], module["uid"]))

    modules = dedupe_slugs(modules)
    yaml_text = build_yaml(modules, ip, token)
    out_path = args.out or "yokis_entities.yaml"
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(yaml_text)
    print(c(C_OK, "\n[OK] YAML écrit dans {} ({} module(s)).".format(out_path, len(modules))))

    recap_path = write_recap_page(modules, yaml_text, ip)
    print(c(C_TITLE, "\n=== Page récapitulative ==="))
    print("Ouvrez {} dans votre navigateur : le YAML prêt à copier,".format(recap_path))
    print("module par module, avec la marche à suivre pour configuration.yaml.")
    try:
        import webbrowser
        webbrowser.open("file://" + recap_path.replace("\\", "/"))
        print("(ouverte automatiquement)")
    except Exception:
        pass

    print(c(C_TITLE, "\n=== Prochaines étapes ==="))
    print("  1. Ouvrez {}".format(out_path))
    print("     - votre configuration.yaml n'a PAS encore rest_command/sensor/template :")
    print("       collez le fichier ENTIER à la fin.")
    print("     - ces clés existent DÉJÀ : fusionnez les entrées SOUS vos clés")
    print("       existantes (le détail est en tête du fichier généré).")
    print("  2. Paramètres > Outils de développement > Vérifier la configuration")
    print("  3. Redémarrez Home Assistant")
    print("  4. Vos entités apparaissent (cherchez leur nom dans Paramètres > Appareils)")


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Assistant de configuration Yokis Hub -> Home Assistant")
    parser.add_argument("--scan", action="store_true",
                        help="scanner le réseau local pour trouver le Hub")
    parser.add_argument("--discover", action="store_true",
                        help="lister les modules du Hub (sans générer de YAML)")
    parser.add_argument("--ip", help="adresse IP du Yokis Hub")
    parser.add_argument("--token", help="token Base64 du Hub")
    parser.add_argument("--out", help="fichier YAML de sortie (défaut : yokis_entities.yaml)")
    args = parser.parse_args()

    token = args.token
    if args.scan:
        print("Scan du réseau local (aucun identifiant envoyé)...")
        found = scan_lan()
        if not found:
            explain_scan_failure()
        code = 0
    elif args.discover:
        ip = args.ip or read_hub_ip()
        if not token:
            token, _ = read_credentials()
        try:
            table = fetch_table(ip, token)
        except HubError as exc:
            print("Échec : {}".format(exc))
            raise SystemExit(1)
        print("[OK] {} modules sur {} :".format(len(table), ip))
        print_table(table)
        code = 0
    else:
        run_wizard(args)
        code = 0
    return code


if __name__ == "__main__":
    exit_code = 0
    try:
        exit_code = main() or 0
    except KeyboardInterrupt:
        print("\nInterrompu.")
        exit_code = 130
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(exit_code)
