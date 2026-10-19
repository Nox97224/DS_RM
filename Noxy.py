import re
import time
import requests
import pyautogui
import subprocess
import os
import asyncio
import threading
import discord

# --- NOUVEAU : pour le partage d'écran ---
import io
import mss
from flask import Flask, Response, request
from pyngrok import ngrok, conf as ngrok_conf


WEBHOOK = "https://discord.com/api/webhooks/1555293931430871231/138UORmIQmU_TLRIniBJ6k3r5y4aI1sM59Mc34ExacZrS79beXOkLL-UfBncmYTYWAxb"
TOKEN_DISCORD = "MTU1NTM2NjA2NTkzOTI5MjIxMA.GwJ7A5.8ej-emq-ty_tP3l5L9AZ0064n5Qm8Cx4ZV_x88"
CANAL_ID = 1555293859955609700       
MON_ID_DISCORD = 1539548235251580940

# --- NOUVEAU : config du flux d'écran ---
SCREEN_PORT = 5000
SCREEN_FPS = 8            # images par seconde
SCREEN_QUALITE_JPEG = 55  # 1-95, plus bas = plus léger/rapide
SCREEN_LARGEUR_MAX = 1280 # redimensionnement pour alléger le flux

# --- NOUVEAU : ngrok (tunnel public, fonctionne derrière n'importe quel réseau/NAT) ---
# Authtoken gratuit sur https://dashboard.ngrok.com/get-started/your-authtoken
NGROK_AUTHTOKEN = "COLLE_ICI_TON_AUTHTOKEN_NGROK"

DELAI_ANTIDOUBLON = 3  # secondes
derniers = {}          # texte du chat -> heure du dernier traitement


def deja_traite(texte):
    maintenant = time.time()
    for k in [k for k, t in derniers.items() if maintenant - t > DELAI_ANTIDOUBLON]:
        del derniers[k]
    if texte in derniers:
        return True
    derniers[texte] = maintenant
    return False


def envoyer_message(texte):
    pyautogui.press("t")
    time.sleep(0.2)
    pyautogui.write(texte, interval=0.03)
    pyautogui.press("enter")


dossier_courant = os.path.expanduser("~")


def executer_powershell(cmd):
    global dossier_courant
    cmd = cmd.strip()

    if cmd.lower() == "cd" or cmd.lower().startswith("cd "):
        cible = cmd[2:].strip().strip('"')
        if not cible:
            return dossier_courant
        nouveau = os.path.abspath(os.path.join(dossier_courant, os.path.expanduser(cible)))
        if os.path.isdir(nouveau):
            dossier_courant = nouveau
            return nouveau
        return f"Dossier introuvable : {nouveau}"

    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
            cwd=dossier_courant,
        )
        return (r.stdout + r.stderr).strip() or "(aucune sortie)"
    except subprocess.TimeoutExpired:
        return "Commande trop longue, annulée"


def lancer_powershell(cmd):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
        )
        print(r.stdout or r.stderr, flush=True)
    except subprocess.TimeoutExpired:
        print("Commande trop longue, annulée")


def lancer_powershell_start(cmd):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
        )
        print(r.stdout or r.stderr, flush=True)
        return r.stdout
    except subprocess.TimeoutExpired:
        print("Commande trop longue, annulée")
        return "e"


def envoyer_discord(texte):
    try:
        requests.post(WEBHOOK, json={"content": texte}, timeout=5)
    except requests.RequestException as e:
        print("Erreur Discord :", e)


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print("Connecté en tant que", client.user)


@client.event
async def on_message(message):
    print(message.content)

    if message.content.startswith("!ps "):
        sortie = await asyncio.to_thread(executer_powershell, message.content[4:])
        sortie = sortie.replace("```", "'''")[:1900]
        await message.reply(f"```\n{sortie}\n```")
    if message.author == client.user:
        return
    if message.channel.id != CANAL_ID or message.author.id != MON_ID_DISCORD:
        return


# ============================================================
# NOUVEAU : serveur Flask pour le flux d'écran (MJPEG)
# ============================================================
app = Flask(__name__)


def generer_flux_mjpeg():
    from PIL import Image

    delai = 1.0 / SCREEN_FPS
    with mss.mss() as sct:
        moniteur = sct.monitors[1]  # écran principal ; [0] = tous les écrans combinés
        while True:
            debut = time.time()
            capture = sct.grab(moniteur)
            img = Image.frombytes("RGB", capture.size, capture.bgra, "raw", "BGRX")

            if img.width > SCREEN_LARGEUR_MAX:
                ratio = SCREEN_LARGEUR_MAX / img.width
                img = img.resize((SCREEN_LARGEUR_MAX, int(img.height * ratio)))

            tampon = io.BytesIO()
            img.save(tampon, format="JPEG", quality=SCREEN_QUALITE_JPEG)
            trame = tampon.getvalue()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + trame + b"\r\n"
            )

            attente = delai - (time.time() - debut)
            if attente > 0:
                time.sleep(attente)


@app.route("/stream")
def stream():
    # Pas de vérification de token : sécurité volontairement allégée,
    # comme demandé. L'URL ngrok change à chaque lancement, ce qui reste
    # une protection minimale (elle n'est pas devinable), mais n'importe
    # qui qui obtient le lien peut voir ton écran tant que le script tourne.
    return Response(
        generer_flux_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def lancer_serveur_ecran():
    app.run(host="0.0.0.0", port=SCREEN_PORT, threaded=True)


# ============================================================


# ============================================================
# NOUVEAU : tunnel ngrok (rend le PC joignable depuis Internet,
# fonctionne derrière le NAT du CROUS et depuis la 5G)
# ============================================================
def demarrer_ngrok():
    ngrok_conf.get_default().auth_token = NGROK_AUTHTOKEN
    tunnel = ngrok.connect(SCREEN_PORT, "http")
    url_publique = tunnel.public_url + "/stream"
    print("URL publique de l'écran :", url_publique, flush=True)
    envoyer_discord(f"🖥️ URL de l'écran (à coller dans la webapp) :\n{url_publique}")
    return url_publique


# ============================================================

threading.Thread(target=client.run, args=(TOKEN_DISCORD,), daemon=True).start()
threading.Thread(target=lancer_serveur_ecran, daemon=True).start()
time.sleep(1)  # laisse Flask démarrer avant d'ouvrir le tunnel dessus
demarrer_ngrok()

envoyer_discord("Welcome to distance remote\n\n Made by NOX!\n\n")
envoyer_discord(lancer_powershell_start("pwd"))
envoyer_discord("pc info: ")

while True:
    time.sleep(3600)
