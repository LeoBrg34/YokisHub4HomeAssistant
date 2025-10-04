# 🔎 Trouver l’IP locale de votre Yokis Hub

Ce guide vous montre comment **trouver l’adresse IP locale** de votre Yokis Hub depuis l’application **YNO**.

> 📸 Les captures d’écran ci-dessous proviennent d’**Android**. L’interface iOS peut différer légèrement.

---

## ✅ Prérequis
- Être **connecté au même réseau Wi-Fi** que votre Yokis Hub
- Avoir l’**application YNO** installée et **connectée à votre compte**

---

## 🪄 Étapes (méthode YNO)

1) **Connectez-vous à votre Yokis Hub** via l’app **YNO** (avec votre compte).
   
   ![Connexion au Hub depuis YNO](./howto/findip/img1.jpeg)

2) Ouvrez **Paramètres** → **Modifier les informations**.
3) Faites défiler la page : **l’adresse IP locale** du Hub apparaît en **bas de page**.

   ![IP visible en bas de la page d’informations](./howto/findip/img2.jpeg)

> ✨ Note : L’adresse IP est au format `192.168.x.x` ou `10.x.x.x`.

---

## 💡 Astuces (si l’app ne montre pas l’IP)

- **Routeur / Box Internet**  
  Ouvrez l’interface de votre box, rubrique **Appareils connectés** / **DHCP**, puis cherchez un appareil nommé *Yokis Hub*, *Yokis*, ou similaire.  
  Vous y verrez l’IP attribuée (ex. `192.168.0.156`).

- **Depuis un ordinateur (même réseau)**  
  - **Windows (PowerShell)** :
    ```powershell
    arp -a
    ```
  - **macOS / Linux (Terminal)** :
    ```bash
    arp -a
    ```
  Recherchez la ligne correspondant au **nom / adresse MAC** du Hub (souvent indiqué sur l’étiquette du produit ou visible dans votre routeur).

---

## 🛡️ Recommandé : réserver l’IP (DHCP)

Pour éviter que l’IP du Hub change (et casse vos commandes Home Assistant), créez une **réservation DHCP** dans votre routeur/box :
- Associez l’**adresse MAC** du Hub à une **IP fixe** (ex. `192.168.0.156`).
- Sauvegardez puis **redémarrez** au besoin.

---

## ✅ Résumé
- Méthode la plus simple : **YNO → Paramètres → Modifier les informations → IP en bas de page**.  
- Alternative : **Routeur/Box** (appareils connectés) ou **`arp -a`** depuis un PC sur le même réseau.  
- Pensez à **réserver l’IP** pour des intégrations Home Assistant stables.

---

