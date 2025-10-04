<p align="center">
  <img src="docs/banner.png" alt="Yokis Hub Connect Banner" width="200">
</p>

# 🏠 YokisHub4HomeAssistant

**Connecteur non officiel entre le Yokis Hub et Home Assistant.**  
Pilotez vos **volets**, **lumières** et **interrupteurs** via de simples **commandes REST**, avec des capteurs qui lisent l’état depuis `server.xml`.  
Exemples prêts à coller dans `configuration.yaml` + guides pas-à-pas pour récupérer **token** et **UID module**.

---

## Fonctionnalités

- ✅ Commandes REST pour volets (covers), lumières et interrupteurs  
- Exemples complets à insérer dans `configuration.yaml`  
- Générateur YAML interactif  
- Documentation claire et accessible

> Les captures d’écran des guides ont été prises sur **Android**. Une version iOS est envisagée pour une prochaine release.

---

## Mise en route rapide — Étapes détaillées

### Étape 1 — Récupérer vos informations de connexion

Avant toute configuration, récupérez :
- **IP locale** de votre Yokis Hub (ex. `192.168.0.156`)  
  <div align="left" style="margin: 8px 0 12px;">
    <a href="./docs/findip.md">
      <img src="https://img.shields.io/badge/Trouver_l’IP_du_Hub-F59E0B?style=for-the-badge" alt="Trouver l’IP du Yokis Hub">
    </a>
  </div>

- **Token HTTP Basic** encodé en Base64  
  <div align="left" style="margin: 8px 0 12px;">
    <a href="./docs/get-token.md">
      <img src="https://img.shields.io/badge/R%C3%A9cup%C3%A9rer_le_token-34C759?style=for-the-badge" alt="Récupérer le token">
    </a>
  </div>

- **UID** de vos modules Yokis  
  <div align="left" style="margin: 8px 0 0;">
    <a href="./docs/get-module-id.md">
      <img src="https://img.shields.io/badge/R%C3%A9cup%C3%A9rer_l'ID_du_module-0A84FF?style=for-the-badge" alt="Récupérer l'ID du module">
    </a>
  </div>

> ⚠️ Ces trois éléments sont indispensables pour que les commandes REST fonctionnent correctement.

---

### Étape 2 — Ouvrir votre fichier `configuration.yaml`

1. Allez dans l'extension File Editor ou par connexion SSH afin d'accèder au configuration.yaml de votre Home Assistant.  
2. Ouvrez le fichier `configuration.yaml` avec l’éditeur intégré ou VS Code.  
3. **Sauvegardez une copie** du fichier avant toute modification.

---

### Étape 3 — Copier les blocs YAML

Copiez les sections souhaitées puis collez-les dans `configuration.yaml` :

- `rest_command` → commandes Yokis  
- `sensor` → lecture de l’état via `server.xml`  
- `light`, `cover`, `switch` → création des entités Home Assistant  
- `input_number`, `template` → sliders & états fiables

> ⚠️ Collez les blocs à la **fin du fichier**, et respectez bien l’indentation YAML.

---

### Étape 4 — Modifier les valeurs importantes

| Élément à remplacer   | Exemple                     | Où le trouver                   |
|-----------------------|-----------------------------|----------------------------------|
| `<IP_DU_HUB>`         | `192.168.0.156`             | Guide IP Hub / routeur          |
| `<UID_MODULE>`        | `C84315B9`                  | Dans `server.xml` / guide UID   |
| `<TOKEN_BASE64>`      | `QWxhZGRpbjpPcGVuU2VzYW1l`  | Sniff réseau / guide Token      |

> 💡 Le token doit **toujours** être précédé de `Basic` dans le header `Authorization`.

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

### Étape 5 — Redémarrer Home Assistant

1. Ouvrez **Outils De Développement --> Redémarrer**.  
2. Patientez.

> En cas d’erreur, vérifiez les indentations YAML et guillemets.

---

### Étape 6 — Tester les entités

- Allez dans **Paramètres → Appareils & Services → Entités**  
- Recherchez vos entités `volet_`, `light_`, `switch_`  
- Essayez une commande pour vérifier le bon fonctionnement

---

> ⚠️ **Avertissement**
> 
> Ce projet est une **intégration non officielle**, basée sur du **reverse engineering** du protocole HTTP Yokis.
> Il n’est **pas affilié à Yokis**.
> **Utilisation à vos risques et périls.**
> Yokis est une marque déposée appartenant à ses propriétaires respectifs.


📄 Licence
MIT © 2025 LeoBrg34
