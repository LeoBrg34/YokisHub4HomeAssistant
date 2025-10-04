# 🔐 Récupérer le token HTTP Basic (Android, PCAPdroid)

Ce guide explique comment **extraire le token HTTP Basic** utilisé par l’app **Yokis YnO** pour piloter votre Hub, afin de le réutiliser dans **Home Assistant**.

> 📸 Captures d’écran **Android**. L’interface peut légèrement varier selon la version.  
> 🛡️ Ne partagez pas ce token publiquement : il donne accès à vos équipements sur le réseau local.

---

## ✅ Prérequis

- Un smartphone **Android**
- L’application **PCAPdroid** installée
- L’application **Yokis YnO** installée et **connectée** à votre compte
- Être sur le **même Wi-Fi** que le Yokis Hub

---

## 🪄 Étapes détaillées (PCAPdroid + YnO)

1) **Ouvrez PCAPdroid** et configurez la capture  
– Mode de capture : **HTTP Server**  
– **Target app** : sélectionnez **Yokis YnO**  
<p><img src="./howto/module-id/img1.jpeg" alt="PCAPdroid : configuration HTTP Server + Target app" width="320"></p>

2) **Démarrez la capture** dans PCAPdroid (bouton Start/Play)  
<p><img src="./howto/module-id/img2.jpeg" alt="PCAPdroid : lancer la capture" width="320"></p>

3) **Basculez dans l’app Yokis YnO** et **faites une action réelle**
– Par exemple : **allumer une lumière**, **ouvrir/fermer** un volet
– Objectif : **générer la requête HTTP** que l’on veut reproduire
<p><img src="./howto/module-id/img3.jpeg" alt="Action dans YnO pour générer la requête" width="320"></p>

4) **Revenez dans PCAPdroid** → ouvrez **Connections** (icône en haut à droite)  
– Cherchez une entrée qui ressemble à :  
192.168.0.X/command.xml?action=order&id=A12345BC&order=on&ext1=100
– **Souvent, c’est la première en partant du bas**  
<p><img src="./howto/module-id/img4.jpeg" alt="PCAPdroid : onglet Connections, sélectionner la trame /command.xml" width="320"></p>

5) **Ouvrez la connexion** et vérifiez l’onglet **Overview** pour confirmer la requête  
<p><img src="./howto/module-id/img5.jpeg" alt="PCAPdroid : Overview de la trame" width="320"></p>

6) Passez à l’onglet **HTTP** (ou **Headers**) pour récupérer le token  
– Repérez la ligne :  Authorization: Basic xxxxxxxxxxxxxxxxxxxxx
– **Copiez la partie après `Basic`** → c’est votre **TOKEN_BASE64** ✅  
<p><img src="./howto/module-id/img6.jpeg" alt="PCAPdroid : onglet HTTP, en-tête Authorization: Basic <token>" width="320"></p>

> 📝 Exemple de requête typique
> ```
> http://192.168.0.156/command.xml?action=order&id=CA1D4066&order=on&ext1=100
> Header: Authorization: Basic QWxhZGRpbjpPcGVuU2VzYW1l <---------TOKEN
> ```

---
