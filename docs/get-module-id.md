# 🆔 Récupérer l’UID d’un module Yokis

Ce guide explique comment **identifier l’UID (identifiant unique)** d’un module Yokis à partir d’une requête HTTP capturée (ex. via PCAPdroid).

> 📸 Capture Android. L’interface peut varier selon la version.

---

## ✅ Prérequis

- Avoir déjà **capturé une requête HTTP** envoyée par l’app **Yokis YnO** vers votre Hub (voir le guide Token si besoin).
- Être sur le **même réseau** que le Hub.

---

## 🪄 Étapes

1) Depuis votre outil de capture (ex. **PCAPdroid → Connections**), **ouvrez la trame HTTP** correspondant à une action sur votre module (allumer/éteindre, ouvrir/fermer, etc.).

2) Allez dans l’onglet qui affiche l’**URL complète** de la requête (Overview / HTTP).

3) **Repérez l’URL** de type :
http://192.168.0.x/command.xml?action=order&id=xxxxxxxx&order=off&ext1=0


L’**UID du module** est la valeur du paramètre **`id`**.

<p>
  <img src="./howto/module-name/img5.jpeg" alt="Trouver l’UID dans l’URL (paramètre id=...)" width="360">
</p>

---

## 🧪 Exemple

- **Requête** :
http://192.168.0.156/command.xml?action=order&id=C84315B9&order=off&ext1=0


- **UID** : `C84315B9`

---

## 🔧 Utilisation dans Home Assistant

Utilisez cet UID dans vos blocs YAML (ex. `sensor` et `rest_command`) :

```yaml
# Commande REST (ex. volet)
rest_command:
  yokis_set_position_exemple:
    url: "http://192.168.0.156/command.xml?action=order&id=C84315B9&order=varX&ext1=<POSITION>"
    method: get
    headers:
      Authorization: "Basic VOTRE_TOKEN_BASE64_ICI"

# Capteur REST lisant l'état via server.xml (même UID)
sensor:
  - platform: rest
    name: Volet Chambre Brut
    resource: http://192.168.0.156/server.xml?gettable&update=1
    method: GET
    headers:
      Authorization: "Basic VOTRE_TOKEN_BASE64_ICI"
    # value_template: utilisez le template proposé dans docs/configuration.md
    unit_of_measurement: "%"
✅ Résumé

Ouvrez la trame capturée correspondant à l’action sur votre module.

Cherchez l’URL avec command.xml?action=order&....

L’UID est la valeur après id= (ex. id=CA1D4066).

Réutilisez cet UID dans vos commandes et capteurs Home Assistant.
