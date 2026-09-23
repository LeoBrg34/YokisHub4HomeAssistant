<div align="center">
  <img src="docs/banner.png" alt="YokisHub4HomeAssistant" width="820">
</div>

# YokisHub4HomeAssistant

**Connecteur non officiel entre le Yokis Hub et Home Assistant.**
Volets, lumières, interrupteurs et portails via du REST YAML. Sans HACS, sans add-on.

[![Licence : MIT](https://img.shields.io/github/license/LeoBrg34/YokisHub4HomeAssistant?style=flat-square&label=licence)](LICENSE)
[![Dernier commit](https://img.shields.io/github/last-commit/LeoBrg34/YokisHub4HomeAssistant?style=flat-square&label=dernier%20commit)](https://github.com/LeoBrg34/YokisHub4HomeAssistant/commits/main)
[![Plateformes](https://img.shields.io/badge/plateformes-Windows%20%7C%20macOS%20%7C%20Linux-8aa0b5?style=flat-square)](#démarrage-rapide)
[![Python : 3.8+](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)

---

## Démarrage rapide

```bash
git clone https://github.com/LeoBrg34/YokisHub4HomeAssistant.git
cd YokisHub4HomeAssistant
python yokis_setup.py
```

1. **Hub** : IP fournie ou scan LAN (~10 s).
2. **Token** : proxy local sur le PC, action dans l'app Yokis, capturé automatiquement.
3. **Module** : nommez le type (lampe, volet, portail, interrupteur) ; les suivants sont détectés en agissant dessus.
4. **YAML** : page de recap, copiez dans `configuration.yaml`, vérifiez, redémarrez.
5. **Proxy** : remettez le Wi‑Fi du téléphone sur **Aucun** à la fin.

<div align="center"><img src="docs/demo.gif" alt="Démo assistant" width="640"></div>

## Fonctionnalités

- Scan LAN, capture du token, génération YAML, page de recap prête à copier.
- 4 types : lampe, volet (position), interrupteur (état), portail (impulsion).
- Capteurs REST + template pour un retour d'état fiable.
- Python 3.8+ seul, zéro dépendance, tout reste sur le LAN.

## Le token

Le Hub exige un en-tête HTTP Basic (Base64 de `email:mot_de_passe`), envoyé en clair : l'assistant le capture via un proxy local transparent (HTTP + tunnel HTTPS).

- Téléphone et PC sur le même Wi‑Fi → **Proxy manuel** = IP du PC + port affiché.
- Une action réelle dans l'app Yokis suffit ; l'UID du module est lu en même temps.
- Si la capture échoue : collez la requête ou le token dans l'assistant.

**Ne partagez jamais le token, ne le versionnez pas.**

## Installation manuelle

| Élément | Où le trouver |
|---|---|
| IP du Hub | scan de l'assistant |
| Token HTTP Basic | [Le token](#le-token) |
| UID des modules | liste automatique de l'assistant |

Générez le YAML avec l'assistant, collez (ou fusionnez sous vos clés existantes), vérifiez la configuration, redémarrez.

## Vos données restent locales

Aucune requête externe, aucun compte, aucune télémétrie. Le proxy ne journalise rien et n'accepte que le LAN. Le YAML contient votre token : gardez-le.

## Contribuer

Issues ouvertes : bug, module non reconnu, amélioration.

```bash
python tests/selftest.py
```

Test hors ligne (faux Hub + faux cloud) : 29 vérifications, aucun Hub réel touché.

## Licence

MIT © 2026 LeoBrg34. Voir [LICENSE](LICENSE).

> **Avertissement** : intégration non officielle issue d'une ingénierie inverse. Non affiliée à Yokis. Utilisation à vos risques. Yokis est une marque déposée.

---

<p align="center">
  <a href="https://fr.tipeee.com/yokishub4homeassistant/" target="_blank">
    <img src="docs/tipeee.png" alt="Soutenir sur Tipeee" width="180">
  </a>
</p>
