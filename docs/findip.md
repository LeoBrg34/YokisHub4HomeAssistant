# 🛜 Trouver l’IP locale de votre Yokis Hub

Ce guide explique comment récupérer l’adresse IP locale de votre Yokis Hub, principalement via l’application officielle YNO.

> Note : Les captures d’écran ci-dessous ont été réalisées sur Android. L’interface peut légèrement différer sur iOS.

---

## Avant de commencer

- Assurez-vous d'être connecté au même réseau Wi-Fi que votre Yokis Hub.
- Vérifiez que l’application YNO est installée et que vous êtes connecté à votre compte.

---

## Méthode avec l'application YNO

1. Connectez-vous à votre Yokis Hub depuis l’application YNO.

<p>
  <img src="./howto/findip/img1.jpeg" alt="Connexion au Hub depuis YNO" width="320">
</p>

2. Accédez aux **Paramètres**, puis sélectionnez **Modifier les informations**.  
3. Faites défiler l'écran vers le bas : **l’adresse IP locale** de votre Hub y est affichée.

<p>
  <img src="./howto/findip/img2.jpeg" alt="IP visible en bas de la page d’informations" width="320">
</p>

> Pour information, une adresse IP locale ressemble généralement à `192.168.x.x` ou `10.x.x.x`.

---

## Méthodes alternatives (si l'IP n'apparaît pas)

**Option A : Depuis l'interface de votre box internet ou routeur**  

- Connectez-vous à l'interface d'administration de votre box.  
- Consultez la rubrique des **Appareils connectés** ou la section **DHCP**.  
- Recherchez un équipement nommé *Yokis Hub*, *Yokis* ou similaire.  
- Notez l'adresse IP qui lui est attribuée (par exemple : `192.168.0.156`).

**Option B : Depuis un ordinateur (sur le même réseau)**  

- **Sous Windows (Invite de commandes ou PowerShell) :**
  Tapez la commande suivante pour lister les appareils connectés à votre réseau :
  ```powershell
  arp -a
Vous verrez apparaître une liste d'adresses IP. Vous pourrez identifier celle du Hub en la croisant avec son adresse MAC (généralement inscrite sur une étiquette sous le boîtier Yokis).
