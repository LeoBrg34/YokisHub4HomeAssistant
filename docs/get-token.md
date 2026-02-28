# 🔐 Récupérer le token HTTP Basic (Android, PCAPdroid)

Ce guide explique comment extraire le token HTTP Basic utilisé par l’application Yokis YNO pour piloter votre Hub. Ce token est indispensable pour autoriser Home Assistant à envoyer des commandes.

> Note : Les captures d’écran ci-dessous ont été réalisées sur Android. L’interface peut légèrement différer selon la version.  
> Avertissement de sécurité : Ne partagez jamais ce token publiquement, car il donne un accès direct à vos équipements sur votre réseau local.

---

## Avant de commencer

- Un smartphone sous Android.
- L’application PCAPdroid installée.
- L’application Yokis YNO installée et connectée à votre compte.
- Être connecté au même réseau Wi-Fi que le Yokis Hub.

---

## Procédure de capture réseau

1. Ouvrez PCAPdroid et configurez la capture :  
   - Mode de capture : **HTTP Server**  
   - Application cible (Target app) : sélectionnez **Yokis YNO**  
<p><img src="./howto/token/img1.jpeg" alt="PCAPdroid : configuration HTTP Server + Target app" width="320"></p>

2. Démarrez la capture dans PCAPdroid en appuyant sur le bouton Start (ou Play).  
<p><img src="./howto/token/img2.jpeg" alt="PCAPdroid : lancer la capture" width="320"></p>

3. Basculez dans l’application Yokis YNO et effectuez une action réelle sur l'un de vos équipements (par exemple, allumer une lumière ou ouvrir un volet). L'objectif est de générer la requête HTTP que nous voulons intercepter.  
<p><img src="./howto/token/img3.jpeg" alt="Action dans YnO pour générer la requête" width="320"></p>

4. Revenez dans PCAPdroid et ouvrez les **Connections** (via l'icône en haut à droite). Cherchez une ligne contenant l'URL `192.168.0.X/command.xml?action=order&...`. Il s'agit souvent de la première ligne en partant du bas.  
<p><img src="./howto/token/img4.jpeg" alt="PCAPdroid : onglet Connections, sélectionner la trame /command.xml" width="320"></p>

5. Ouvrez cette connexion et vérifiez l’onglet **Overview** pour confirmer qu'il s'agit bien de la bonne requête vers votre Hub.  
<p><img src="./howto/token/img5.jpeg" alt="PCAPdroid : Overview de la trame" width="320"></p>

6. Passez à l’onglet **HTTP** (ou **Headers**) pour récupérer le token. Repérez la ligne `Authorization: Basic xxxxxxxxxxxxxxxxxxxxx`.  
   **Copiez uniquement la partie située après le mot `Basic`** : c’est votre Token encodé en Base64.  
<p><img src="./howto/token/img6.jpeg" alt="PCAPdroid : onglet HTTP, en-tête Authorization: Basic <token>" width="320"></p>

---

## Exemple de requête interceptée

Voici à quoi ressemble généralement l'information que vous allez trouver :

```text
URL : http://192.168.0.156/command.xml?action=order&id=CA1D4066&order=on&ext1=100
En-tête : Authorization: Basic QWxhZGRpbjpPcGVuU2VzYW1l
