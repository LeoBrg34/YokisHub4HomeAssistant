# 🆔 Récupérer l’UID d’un module Yokis

Ce guide explique comment identifier l’UID (identifiant unique) d’un module Yokis à partir d’une requête HTTP interceptée, par exemple avec l'application PCAPdroid.

> Note : Les captures d’écran ci-dessous ont été réalisées sur Android. L’interface peut légèrement différer sur iOS.

---

## Avant de commencer

- Avoir déjà intercepté une requête HTTP envoyée par l’application YNO vers votre Hub (consultez le guide sur la récupération du Token si besoin).
- Être connecté au même réseau Wi-Fi que le Hub.

---

## Extraction de l'UID depuis l'application de capture

1. Dans votre outil de capture réseau (par exemple PCAPdroid, dans l'onglet **Connections**), ouvrez la trame HTTP qui correspond à une action que vous venez d'effectuer sur votre module (allumer, éteindre, ouvrir, fermer).
2. Accédez à la section qui affiche l’URL complète de la requête (souvent nommée Overview ou HTTP).
3. Repérez l’URL qui ressemble à ceci :
   `http://192.168.0.x/command.xml?action=order&id=xxxxxxxx&order=off&ext1=0`

L’UID de votre module correspond à la valeur placée juste après `id=`.

<p>
  <img src="./howto/module-name/img5.jpeg" alt="Trouver l’UID dans l’URL (paramètre id=...)" width="360">
</p>

---

## Exemple concret

Si la requête capturée est la suivante :
`http://192.168.0.156/command.xml?action=order&id=C84315B9&order=off&ext1=0`

Alors l'UID de ce module est : **`C84315B9`**

---

## Intégration dans Home Assistant

Cet UID doit être renseigné dans vos blocs YAML (comme `sensor` et `rest_command`) pour que Home Assistant sache quel module piloter et interroger :

```yaml
# Commande REST (exemple pour un volet)
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
    resource: "http://192.168.0.156/server.xml?gettable&update=1"
    method: GET
    headers:
      Authorization: "Basic VOTRE_TOKEN_BASE64_ICI"
    # Utilisez le template proposé dans la documentation principale pour value_template
    unit_of_measurement: "%"
