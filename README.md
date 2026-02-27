<p align="center">
  <img src="docs/banner.png" alt="Yokis Hub Connect Banner" width="200">
</p>

# 🏠 YokisHub4HomeAssistant

**Connecteur non officiel entre le Yokis Hub et Home Assistant.**  
Pilotez vos **volets**, **lumières** et **interrupteurs** via de simples **commandes REST**, avec des capteurs qui lisent l’état depuis `configuration.yaml`.  
Vous trouverez ici des exemples prêts à coller dans `configuration.yaml` ainsi que des guides pas-à-pas pour récupérer votre **token** et l'**UID de vos modules**.

---

## Fonctionnalités principales

- Contrôle de l'ensemble des modules : volets (covers), lumières et interrupteurs.
- Code YAML structuré, prêt à être copié dans votre configuration.
- Un générateur de code interactif pour simplifier la création des entités.
- Une documentation détaillée.

> Note : Les guides actuels sont basés sur des captures d'écran **Android**. Une version iOS sera proposée lors d'une prochaine mise à jour.

---

## Guide d'installation rapide

### 1. Rassembler les identifiants du Yokis Hub

Avant de modifier votre configuration, vous devez réunir trois éléments essentiels :

- **L'adresse IP locale** de votre Yokis Hub sur votre réseau (par exemple : `192.168.0.156`).
  <div align="left" style="margin: 8px 0 12px;">
    <a href="./docs/findip.md">
      <img src="https://img.shields.io/badge/Trouver_l’IP_du_Hub-F59E0B?style=for-the-badge" alt="Trouver l’IP du Yokis Hub">
    </a>
  </div>

- **Le Token HTTP Basic**, encodé au format Base64.
  <div align="left" style="margin: 8px 0 12px;">
    <a href="./docs/get-token.md">
      <img src="https://img.shields.io/badge/R%C3%A9cup%C3%A9rer_le_token-34C759?style=for-the-badge" alt="Récupérer le token">
    </a>
  </div>

- **L'UID** correspondant à chaque module Yokis que vous souhaitez contrôler.
  <div align="left" style="margin: 8px 0 0;">
    <a href="./docs/get-module-id.md">
      <img src="https://img.shields.io/badge/R%C3%A9cup%C3%A9rer_l'ID_du_module-0A84FF?style=for-the-badge" alt="Récupérer l'ID du module">
    </a>
  </div>

> ⚠️ Le fonctionnement des commandes REST dépend entièrement de l'exactitude de ces trois informations.

---

### 2. Préparer le fichier de configuration

1. Accédez aux fichiers de votre installation Home Assistant (via l'extension File Editor ou par connexion SSH).  
2. Ouvrez le fichier `configuration.yaml`.  
3. **Important** : Créez une sauvegarde de ce fichier avant d'effectuer des modifications.

---

### 3. Intégrer le code YAML

Copiez les sections correspondant à vos besoins et collez-les à la fin de votre fichier `configuration.yaml`. Vous trouverez des exemples pour :

- `rest_command` : pour définir les actions vers le Hub Yokis.
- `sensor` : pour interroger l'état de vos modules.
- `light`, `cover`, `switch` : pour créer les entités correspondantes dans l'interface Home Assistant.
- `input_number`, `template` : pour assurer un retour d'état fiable et gérer les curseurs (sliders).

> ⚠️ Assurez-vous de bien respecter l'indentation YAML lors du collage.

---

### 4. Personnaliser les variables

Dans le code copié, remplacez les valeurs d'exemple par vos propres informations :

| Élément à remplacer       | Exemple de valeur           | Source de l'information              |
|---------------------------|-----------------------------|---------------------------------------|
| `<IP_DU_HUB>`             | `192.168.0.156`             | Voir le guide sur l'IP du Hub        |
| `<UID_MODULE>`            | `C84315B9`                  | Voir le guide sur l'UID du module    |
| `<TOKEN_BASE64>`          | `QWxhZGRpbjpPcGVuU2VzYW1l`  | Voir le guide sur le Token           |

> ⚠️ Dans l'en-tête de la requête HTTP, le mot `Basic` doit **toujours** précéder votre token encodé.

**Pour générer le code plus facilement, utilisez notre outil interactif :**

<div align="left" style="margin: 10px 0 0;">
  <a href="https://leobrg34.github.io/YokisHub4HomeAssistant/generator.html">
    <img src="https://img.shields.io/badge/Ouvrir_le_g%C3%A9n%C3%A9rateur_(Pages)-8B5CF6?style=for-the-badge" alt="Ouvrir le générateur (GitHub Pages)">
  </a>
  &nbsp;
  <a href="https://github.com/LeoBrg34/YokisHub4HomeAssistant/blob/main/docs/generator.html">
    <img src="https://img.shields.io/badge/Voir_le_code_source-6B7280?style=for-the-badge" alt="Voir le code source du générateur">
  </a>
</div>

---

### 5. Redémarrer Home Assistant

1. Dans l'interface Home Assistant, naviguez vers **Paramètres** → **Outils de développement**.  
2. Cliquez sur **Redémarrer** et patientez pendant le redémarrage du système.

> Si une erreur empêche le redémarrage, vérifiez l'alignement de votre code YAML et la présence éventuelle de caractères manquants (comme des guillemets).

---

### 6. Vérifier le fonctionnement

- Rendez-vous dans **Paramètres → Appareils et services → Entités**.  
- Recherchez les nouvelles entités créées (généralement préfixées par `volet_`, `light_` ou `switch_`).  
- Testez les commandes pour vous assurer que les modules réagissent correctement.

---

<p align="center">
  <a href="https://fr.tipeee.com/yokishub4homeassistant/" target="_blank">
    <img src="docs/tipeee.png" alt="Soutenir sur Tipeee" width="200">
  </a>
</p>

<p align="center" style="margin-top: 5px; font-size:14px;">
  Votre soutien permet de financer le développement de la documentation pour les appareils iOS 🚀
</p>

> ⚠️ **Avertissement**
> 
> Cette intégration n'est pas officielle. Elle résulte d'une ingénierie inverse (reverse engineering) du protocole HTTP utilisé par le Yokis Hub.
> Ce projet n'est en aucun cas affilié à la société Yokis. L'utilisation de ce code se fait sous votre propre responsabilité.
> Yokis est une marque déposée.

📄 Licence  
MIT © 2026 LeoBrg34
