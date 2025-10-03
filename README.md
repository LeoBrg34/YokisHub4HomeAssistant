<p align="center">
  <img src="docs/banner.png" alt="Yokis Hub Connect Banner" width="200">
</p>

# 🧰 YokisHub4HomeAssistant

**Connecteur non officiel entre le Yokis Hub et Home Assistant.**  
Pilotez vos **volets**, **lumières** et **interrupteurs** via de simples **commandes REST**, avec des capteurs qui lisent l’état depuis `server.xml`.  
Exemples prêts à coller dans `configuration.yaml` + guides pas-à-pas pour récupérer **token** et **UID module**.

---

## ✨ Fonctionnalités

- ✅ Commandes REST pour volets (covers), lumières et interrupteurs  
- 📡 Lecture périodique de l’état via `server.xml`  
- 🧭 Exemples complets à insérer dans `configuration.yaml`  
- 🖼️ Captures d’écran + guides pour récupérer **token** et **UID**  
- 🧪 Générateur YAML interactif pour créer vos commandes rapidement  
- 📘 Documentation claire et accessible

---

## 🔎 Récupérer le token & l’ID du module

<div align="center">
  <a href="./docs/get-token.md">
    <img src="https://img.shields.io/badge/R%C3%A9cup%C3%A9rer_le_token-34C759?style=for-the-badge" alt="Récupérer le token">
  </a>
  &nbsp;
  <a href="./docs/get-module-id.md">
    <img src="https://img.shields.io/badge/R%C3%A9cup%C3%A9rer_l'ID_du_module-0A84FF?style=for-the-badge" alt="Récupérer l'ID du module">
  </a>
</div>

- Le guide **Token** explique comment sniffer la requête HTTP Basic Auth et récupérer le header encodé en Base64.  
- Le guide **ID module** montre comment trouver l’UID dans `server.xml` ou via analyse réseau, avec captures d’écran détaillées.

> 📸 **Toutes les captures d’écran ont été prises sur Android**.  
> Une version iOS est envisagée pour une prochaine release.

---

## 🧪 Générer vos blocs YAML automatiquement

➡️ Ouvrez le **[Constructeur de commande YAML](https://leobrg34.github.io/YokisHub4HomeAssistant/docs/generator.html)**, renseignez :
- L’adresse IP de votre **Yokis Hub**
- Le **token Base64** récupéré
- L’**UID** du module
- Le type d’équipement (Lampe ou Volet)
- Le nom et la fréquence d’actualisation

👉 Cliquez ensuite sur **Générer** puis sur **Copier** pour insérer directement les blocs YAML dans `configuration.yaml`.

---

## 🚀 Mise en route rapide — Étapes détaillées

### 🪄 Étape 1 — Récupérer vos informations de connexion

Avant toute configuration, récupérez :
- 🧭 **IP locale** de votre Yokis Hub (ex. `192.168.0.156`)  
- 🔑 **Token HTTP Basic** encodé en Base64 → [Guide Token](./docs/get-token.md)  
- 🆔 **UID** de vos modules Yokis → [Guide UID](./docs/get-module-id.md)

> ⚠️ Ces trois éléments sont indispensables pour que les commandes REST fonctionnent correctement.

---

### 📝 Étape 2 — Ouvrir votre fichier `configuration.yaml`

1. Allez dans **Paramètres → Système → Répertoire de configuration** dans Home Assistant.  
2. Ouvrez le fichier `configuration.yaml` avec l’éditeur intégré ou VS Code.  
3. **Sauvegardez une copie** du fichier avant toute modification.

---

### 📋 Étape 3 — Copier les blocs YAML

Rendez-vous dans la [documentation complète](./docs/configuration.md).  
Copiez les sections souhaitées puis collez-les dans `configuration.yaml` :

- `rest_command` → commandes Yokis  
- `sensor` → lecture de l’état via `server.xml`  
- `light`, `cover`, `switch` → création des entités Home Assistant  
- `input_number`, `template` → sliders & états fiables

> ⚠️ Collez les blocs à la **fin du fichier**, et respectez bien l’indentation YAML.

---

### ✍️ Étape 4 — Modifier les valeurs importantes

| Élément à remplacer   | Exemple                   | Où le trouver               |
|------------------------|----------------------------|-----------------------------|
| `<IP_DU_HUB>`          | `192.168.0.156`           | IP locale du Yokis Hub      |
| `<UID_MODULE>`         | `C84315B9`                | Dans `server.xml` ou guide UID |
| `<TOKEN_BASE64>`       | `QWxhZGRpbjpPcGVuU2VzYW1l` | Via sniff réseau / guide Token |

> 💡 Le token doit **toujours** être précédé de `Basic` dans le header `Authorization`.

---

### 🔄 Étape 5 — Redémarrer Home Assistant

1. Ouvrez **Paramètres → Système → Contrôle du serveur**.  
2. Cliquez sur **Vérifier la configuration** ✅  
3. Si tout est correct, cliquez sur **Redémarrer** 🔁

> 🧠 En cas d’erreur, vérifiez les indentations YAML et guillemets.

---

### 🧪 Étape 6 — Tester les entités

- Allez dans **Paramètres → Appareils & Services → Entités**  
- Recherchez vos entités `volet_`, `light_`, `switch_`  
- Essayez une commande pour vérifier le bon fonctionnement 🎉

---

## 🧩 Exemple minimal

```yaml
# --- Commande REST : fixer la position d'un volet (0-100)
rest_command:
  yokis_set_position_exemple:
    url: "http://192.168.0.156/command.xml?action=order&id=C84315B9&order=varX&ext1={{ position }}"
    method: get
    headers:
      Authorization: "Basic VOTRE_TOKEN_BASE64_ICI"

# --- Capteur REST : lecture de la position depuis server.xml
sensor:
  - platform: rest
    name: Volet Chambre Brut
    resource: http://192.168.0.156/server.xml?gettable&update=1
    method: GET
    headers:
      Authorization: "Basic VOTRE_TOKEN_BASE64_ICI"
    value_template: >-
      {% set volet = value_json.data.table | selectattr("uid", "equalto", "C84315B9") | list | first %}
      {{ volet.var | default(0) }}
    unit_of_measurement: "%"

# --- Volet Home Assistant basé sur le capteur REST
cover:
  - platform: template
    covers:
      volet_chambre:
        friendly_name: "Volet Chambre"
        position_template: "{{ states('sensor.volet_chambre_brut') | int(0) }}"
        set_cover_position:
          service: rest_command.yokis_set_position_exemple
          data:
            position: "{{ position }}"
