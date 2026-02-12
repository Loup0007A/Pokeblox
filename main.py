import discord
import random
from discord.ext import commands
from discord import app_commands
import json
import os
import chess
from discord.ext import tasks

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

###########################################################################################################
# Définition des noms de fichiers
FILE_MORPION = "morpion_scores.json"
FILE_P4 = "puissance4_stats.json"
FILE_CHESS = "chess_stats.json"

def get_stats(filename):
    """Charge les données d'un fichier spécifique."""
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_stats(filename, stats):
    """Sauvegarde dans un fichier spécifique."""
    with open(filename, "w") as f:
        json.dump(stats, f, indent=4)

def update_score(user_id, opponent_id, opponent_name, result, filename):
    stats = get_stats(filename)
    uid = str(user_id)
    oid = str(opponent_id)

    # Initialisation du joueur si nouveau
    if uid not in stats:
        stats[uid] = {"wins": 0, "losses": 0, "draws": 0, "current_streak": 0, "max_streak": 0, "rivals": {}}
    
    player = stats[uid]

    # Initialisation du rival si nouveau duel
    if oid not in player["rivals"]:
        player["rivals"][oid] = {"name": opponent_name, "wins": 0, "losses": 0, "draws": 0}

    # Mise à jour des stats globales et duels
    if result == 'win':
        player["wins"] += 1
        player["rivals"][oid]["wins"] += 1
        player["current_streak"] += 1
        # Record de la plus longue série
        if player["current_streak"] > player["max_streak"]:
            player["max_streak"] = player["current_streak"]
            
    elif result == 'loss':
        player["losses"] += 1
        player["rivals"][oid]["losses"] += 1
        player["current_streak"] = 0 # La série s'arrête
        
    elif result == 'draw':
        player["draws"] += 1
        player["rivals"][oid]["draws"] += 1
        # Optionnel : un nul casse-t-il la série ? Ici on décide que non, elle stagne.

    save_stats(filename, stats)

###################################################################################################""
# --- CLOSE TICKET VIEW ---
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("Le ticket va être archivé...")
            # Locking prevents further messages, archiving hides it.
            await interaction.channel.edit(archived=True, locked=True)
        else:
            await interaction.response.send_message("Cette commande ne peut être utilisée que dans un fil.", ephemeral=True)

# --- OPEN TICKET VIEW ---
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ouvrir un Ticket", style=discord.ButtonStyle.success, custom_id="open_ticket_thread")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message("Impossible de créer un fil ici.", ephemeral=True)

        try:
            # NOTE: Private threads require Community enabled or certain Boost levels.
            # Using public_thread is a safer fallback if private fails.
            thread = await interaction.channel.create_thread(
                name=f"ticket-{interaction.user.name}",
                type=discord.ChannelType.private_thread, 
                auto_archive_duration=1440,
                reason=f"Ticket ouvert par {interaction.user.display_name}"
            )

            await thread.add_user(interaction.user)
            await interaction.response.send_message(f"Ton ticket a été créé : {thread.mention}", ephemeral=True)
            
            embed = discord.Embed(
                title="Support",
                description=f"Bonjour {interaction.user.mention} !\nPosez votre question ici. Un membre du staff vous répondra dès que possible.",
                color=discord.Color.green()
            )
            await thread.send(embed=embed, view=CloseTicketView())

        except discord.Forbidden:
            await interaction.response.send_message("Le bot n'a pas la permission 'Gérer les fils' ou 'Fils privés' !", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Erreur : Les fils privés nécessitent peut-être un niveau de boost plus élevé. {e}", ephemeral=True)

# --- BOT CONFIGURATION ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Persistence ensures buttons work after bot restart
        self.add_view(TicketView())
        self.add_view(CloseTicketView())

bot = MyBot()

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot opérationnel : {bot.user}")

# --- COMMANDS ---
@bot.tree.command(name="setup_ticket", description="Installe le système de ticket")
@app_commands.checks.has_permissions(manage_threads=True)
async def setup_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Centre d'assistance",
        description="Besoin d'aide ? Cliquez sur le bouton ci-dessous pour ouvrir un ticket privé.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.tree.command(name="dice_roll", description="Lance un dé")
async def dice_roll(interaction: discord.Interaction, nombre_de_faces: int = 6):
    result = random.randint(1, nombre_de_faces) # Corrected reference
    embed = discord.Embed(
        title="🎲 Lancer de dé",
        description=f"Le résultat est : **{result}**",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed) # Removed TicketView here

@bot.tree.command(name="ban_pseudo", description="Bannir quelqu'un du serveur avec son pseudo")
@app_commands.checks.has_permissions(ban_members=True)
async def banguy(interaction: discord.Interaction, member: discord.Member, reason: str):
    await member.ban()
    await interaction.response.send_message(f"Vous avez banni {member} avec succès", ephemeral=True)
    await member.send(f"Vous avez été banni du serveur pour la raison : {reason}")

@bot.tree.command(name="unban_pseudo", description="Débannir un utilisateur via son pseudo")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_pseudo(interaction: discord.Interaction, name: str):
    # 1. Récupérer la liste des bannissements (c'est une liste d'objets BanEntry)
    bans = [entry async for entry in interaction.guild.bans()]
    
    # 2. Chercher l'utilisateur dans la liste
    user_to_unban = None
    for ban_entry in bans:
        user = ban_entry.user
        # On compare avec le pseudo actuel (ex: "loup") 
        # ou l'ancien format (ex: "Loup#1234")
        if user.name.lower() == name.lower() or str(user).lower() == name.lower():
            user_to_unban = user
            break

    # 3. Agir en fonction du résultat
    if user_to_unban:
        await interaction.guild.unban(user_to_unban)
        channel = interaction.channel
        reinvite = await channel.create_invite(
            max_age=0, 
            max_uses= 1,
            unique=True
        )
        await user_to_unban.send(f"Vous avez été débanni, pour revenir sur le serveur utilisez ce lien : {reinvite.url}")
        await interaction.response.send_message(f"✅ **{user_to_unban.name}** a été débanni.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Impossible de trouver **{name}** dans la liste des bannis.", ephemeral=True)

@bot.tree.command(name="ban_numéro_de_compte", description="Bannir quelqu'un du serveur via son ID")
@app_commands.checks.has_permissions(ban_members=True)
async def banguy(interaction: discord.Interaction, user_id: str, reason: str):
    try:
        # 1. On récupère l'utilisateur via son ID (même s'il n'est pas sur le serveur)
        user = await bot.fetch_user(int(user_id))
        
        # 2. On tente d'envoyer un DM AVANT le ban
        try:
            await user.send(f"Vous avez été banni du serveur pour la raison : {reason}")
        except:
            # Si l'utilisateur a fermé ses MPs, on ignore l'erreur pour continuer le ban
            pass

        # 3. On bannit l'utilisateur du serveur (guild)
        await interaction.guild.ban(user, reason=reason)
        
        # 4. Confirmation à l'admin
        await interaction.response.send_message(f"✅ {user.name} (ID: {user_id}) a été banni avec succès.", ephemeral=True)

    except ValueError:
        await interaction.response.send_message("❌ L'ID fourni n'est pas valide (doit être des chiffres).", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur est survenue : {e}", ephemeral=True)

@bot.tree.command(name="unban_id", description="Débannir un utilisateur via son ID")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_id(interaction: discord.Interaction, user_id: str):
    try:
        # 1. Convertir l'ID et récupérer l'utilisateur
        # Il faut bien mettre (await ...), et on ne met pas .lower ici
        user = await bot.fetch_user(int(user_id))
        
        # 2. Débannir directement (Discord comprend l'objet User ou l'ID)
        await interaction.guild.unban(user)

        # 3. Créer l'invitation
        reinvite = await interaction.channel.create_invite(
            max_age=0, 
            max_uses=1, 
            unique=True
        )

        # 4. Tenter d'envoyer le MP
        try:
            await user.send(f"Vous avez été débanni ! Voici votre lien de retour : {reinvite.url}")
        except:
            pass # L'utilisateur a peut-être bloqué ses MPs

        await interaction.response.send_message(f"✅ **{user.name}** a été débanni.", ephemeral=True)

    except ValueError:
        await interaction.response.send_message("❌ L'ID fourni n'est pas un nombre valide.", ephemeral=True)
    except discord.NotFound:
        await interaction.response.send_message("❌ Cet utilisateur n'est pas dans la liste des bannis.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

################################################################################################################

class CoinFlipView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60) # Le jeu s'arrête après 60s d'inactivité

    @discord.ui.button(label="Pile", style=discord.ButtonStyle.primary)
    async def pile(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultat = random.choice(["Pile", "Face"])
        if resultat == "Pile":
            await interaction.response.send_message("Gagné ! C'était Pile.")
        else:
            await interaction.response.send_message("Perdu ! C'était Face.")
        self.stop() # Arrête d'écouter les boutons après le jeu

    @discord.ui.button(label="Face", style=discord.ButtonStyle.secondary)
    async def face(self, interaction: discord.Interaction, button: discord.ui.Button):
        resultat = random.choice(["Pile", "Face"])
        if resultat == "Face":
            await interaction.response.send_message("Gagné ! C'était Face.")
        else:
            await interaction.response.send_message("Perdu ! C'était Pile.")
        self.stop()

@bot.tree.command(name="pile_ou_face", description="Lance une pièce !")
async def flip(interaction: discord.Interaction):
    view = CoinFlipView()
    await interaction.response.send_message("Choisissez votre camp :", view=view)

#############################################################################################################

import discord
from discord import app_commands
from discord.ext import commands

# On crée une classe pour le Bouton (la case du morpion)
class CaseButton(discord.ui.Button):
    def __init__(self, x, y):
        # On initialise le bouton (gris par défaut, vide)
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        # Cette fonction remplace ta fonction 'pion(y,x)'
        view: MorpionGame = self.view
        
        # Vérification du joueur (C'est le tour de qui ?)
        joueur_actuel = view.player1 if view.turn == 1 else view.player2
        if interaction.user != joueur_actuel:
            return await interaction.response.send_message("Ce n'est pas votre tour !", ephemeral=True)

        # Logique de jeu (équivalent à ton code 'if not morpion[y][x]')
        if view.board[self.y][self.x] == 0:
            view.board[self.y][self.x] = view.turn
            
            # Mise à jour visuelle du bouton
            if view.turn == 1:
                self.label = "X"
                self.style = discord.ButtonStyle.danger # Rouge
            else:
                self.label = "O"
                self.style = discord.ButtonStyle.success # Vert
            
            self.disabled = True # On désactive le bouton cliqué

            # Vérification Victoire (appel de ta logique adaptée)
            if view.check_victory():
                # On désactive le plateau
                for child in view.children: 
                    child.disabled = True
                
                # Le gagnant est 'joueur_actuel'
                winner = joueur_actuel
                # Le perdant est l'autre
                loser = view.player2 if winner == view.player1 else view.player1

                # ON SAUVEGARDE LES SCORES
                # Victoire
                # Dans le cas où Player1 gagne contre Player2 :
                update_score(winner.id, loser.id, loser.name, 'win', FILE_MORPION)
                update_score(loser.id, winner.id, winner.name, 'loss', FILE_MORPION)

                await interaction.response.edit_message(content=f"🏆 **Victoire de {winner.mention} !**", view=view)
                view.stop()

            # --- MODIFICATION ICI : Vérification Match Nul ---
            elif view.check_draw():
                # ON SAUVEGARDE LES NULS POUR LES DEUX
                # Match Nul
                # Dans le cas où Player1 gagne contre Player2 :
                # Le joueur 1 fait nul contre le joueur 2
                update_score(view.player1.id, view.player2.id, view.player2.name, 'draw', FILE_MORPION)

                # Le joueur 2 fait nul contre le joueur 1
                update_score(view.player2.id, view.player1.id, view.player1.name, 'draw', FILE_MORPION)

                await interaction.response.edit_message(content="🤝 **Match Nul !** Personne n'a gagné.", view=view)
                view.stop()
            
            # --- Sinon, on continue ---
            else:
                view.turn = 2 if view.turn == 1 else 1
                next_player = view.player2 if view.turn == 2 else view.player1
                await interaction.response.edit_message(content=f"C'est au tour de {next_player.mention} ({'O' if view.turn == 2 else 'X'})", view=view)

# On crée la Vue (l'interface globale qui remplace ta fenêtre Tkinter)
class MorpionGame(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=180)
        # On mélange les joueurs dans une liste
        joueurs = [p1, p2]
        random.shuffle(joueurs) 
        # Le premier de la liste sera le Joueur 1 (X) et commencera
        self.player1 = joueurs[0] # Il aura les X
        self.player2 = joueurs[1] # Il aura les O
        
        self.current_player = self.player1
        self.turn = 1 # 1 commence toujours (X)
        # Ta grille morpion (stockée dans l'objet, pas en global)
        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0]
        ]

        # Création des 9 boutons (comme tes a, aa, aaa...)
        for y in range(3):
            for x in range(3):
                self.add_item(CaseButton(x, y))

    # Ta fonction verify_victory adaptée
    def check_victory(self):
        # Vérifie pour le joueur 1 puis le 2
        for i in range(1, 3):
            # Lignes
            for row in range(3):
                if self.board[row][0] == i and self.board[row][1] == i and self.board[row][2] == i:
                    return True
            # Colonnes
            for col in range(3):
                if self.board[0][col] == i and self.board[1][col] == i and self.board[2][col] == i:
                    return True
            # Diagonales
            if self.board[0][0] == i and self.board[1][1] == i and self.board[2][2] == i:
                return True
            if self.board[0][2] == i and self.board[1][1] == i and self.board[2][0] == i:
                return True
        return False

    # Ta fonction verify_nulle adaptée
    def check_draw(self):
        for row in self.board:
            for cell in row:
                if cell == 0:
                    return False
        return True

# La commande pour lancer le jeu
@bot.tree.command(name="morpion_start", description="Lancer un morpion avec l'adversaire de ton choix !")
async def morpion_start(interaction: discord.Interaction, adversaire: discord.Member):
    if adversaire.bot or adversaire == interaction.user:
        return await interaction.response.send_message("Adversaire invalide.", ephemeral=True)
    
    # On crée la vue
    game_view = MorpionGame(interaction.user, adversaire)
    
    # On annonce qui commence grâce à la variable définie dans le __init__
    await interaction.response.send_message(
        f"**Morpion** : {interaction.user.mention} vs {adversaire.mention}\n"
        f"**{game_view.current_player.mention}** commence !", 
        view=game_view
    )

######################################################################################################
# On définit une fonction de tri qui calcule les "points" (1 pour win, 0.5 pour nul)
def calcul_performance(item):
    data = item[1]
    # Formule : Victoires + (Nuls * 0.5)
    return data['wins'] + (data['draws'] * 0.5)

@bot.tree.command(name="classement_score", description="Affiche le tableau des scores d'un jeu")
@app_commands.choices(jeu=[
    app_commands.Choice(name="Echecs", value=3),
    app_commands.Choice(name="Puissance 4", value=2),
    app_commands.Choice(name="Morpion", value=1),
])
async def classement(interaction: discord.Interaction,jeu: app_commands.Choice[int]):
    if jeu.value == 1:
        stats = get_stats("morpion_scores.json")
        titre_de_embed = "Morpion"
    elif jeu.value == 2:
        stats = get_stats("puissance4_stats.json")
        titre_de_embed = "Puissance 4"
    elif jeu.value == 3:
        stats = get_stats("chess_stats.json")
        titre_de_embed = "Echecs"
    else : 
        return await interaction.response.send_message("Ce jeu n'existe pas", ephemeral=True)
    if not stats:
        return await interaction.response.send_message("Aucune partie n'a encore été jouée !", ephemeral=True)

    # Création de l'Embed (Jolie boîte d'affichage)
    embed = discord.Embed(title=f"🏆 Tableau des Scores - {titre_de_embed}", color=discord.Color.gold())
    
    # On trie les joueurs par nombre de victoires (décroissant)
    # item[1]['wins'] signifie : regarde la valeur 'wins' dans les données du joueur
    sorted_players = sorted(stats.items(), key=calcul_performance, reverse=True)
    classement_text = ""
    for index, (user_id, data) in enumerate(sorted_players[:10]): # Top 10 seulement
        wins = data['wins']
        losses = data['losses']
        draws = data['draws']
        total_games = wins + losses + draws

        # Calcul du pourcentage (éviter la division par zéro)
        # --- CALCUL AJUSTÉ ---
        # On calcule les "points" : 1 par victoire, 0.5 par nul
        points = wins + (draws * 0.5)
        
        if total_games > 0:
            # Le winrate prend maintenant en compte les nuls à 50%
            win_rate = (points / total_games) * 100
        else:
            win_rate = 0
        # ---------------------
        
        # On essaie de récupérer le nom, sinon on met l'ID
        """
        user = interaction.guild.get_member(int(user_id))
        nom = user.name if user else f"Utilisateur {user_id}"
        """
        # À l'intérieur de ta boucle for dans la commande classement :

        # 1. On tente de récupérer dans le cache (très rapide, pas de requête)
        user = interaction.guild.get_member(int(user_id))

        if user:
            nom = user.name
        else:
            # 2. Si pas dans le cache, on tente une seule fois l'API
            try:
                user = await bot.fetch_user(int(user_id))
                nom = user.name
            except:
                # 3. Si l'ID est invalide ou l'utilisateur introuvable
                nom = f"Utilisateur inconnu ({user_id})"
        # Médailles pour le top 3
        medaille = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else f"#{index+1}"

        classement_text += (
            f"**{medaille} {nom}**\n"
            f"└─ Victoires: {wins} | Défaites: {losses} | Nuls: {draws}\n"
            f"└─ Winrate: **{win_rate:.1f}%**\n"
            f"└─ Score: **{points} points**\n\n"
        )

    embed.description = classement_text
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="classement_winrate", description="Classement par pourcentage de victoire d'un jeu (min. 10 parties)")
@app_commands.choices(jeu=[
    app_commands.Choice(name="Echecs", value=3),
    app_commands.Choice(name="Puissance 4", value=2),
    app_commands.Choice(name="Morpion", value=1),
])
async def classement_pro(interaction: discord.Interaction, jeu: app_commands.Choice[int]):
    # 1. Sélection du fichier
    if jeu.value == 1:
        stats = get_stats("morpion_scores.json")
        titre_de_embed = "Morpion"
    elif jeu.value == 2:
        stats = get_stats("puissance4_stats.json")
        titre_de_embed = "Puissance 4"
    elif jeu.value == 3:
        stats = get_stats("chess_stats.json")
        titre_de_embed = "Echecs"
    else : 
        return await interaction.response.send_message("Ce jeu n'existe pas", ephemeral=True)

    if not stats:
        return await interaction.response.send_message("Aucune donnée enregistrée.", ephemeral=True)

    # 2. FILTRAGE : On ne garde que ceux qui ont AU MOINS 10 parties
    # Cela évite qu'un joueur avec 1 victoire et 0 défaite (100%) ne vole la 1ère place
    filtered_stats = [
        (user_id, data) for user_id, data in stats.items() 
        if (data['wins'] + data['losses'] + data['draws']) >= 10
    ]

    if not filtered_stats:
        return await interaction.response.send_message("Aucun joueur n'a encore atteint les 10 parties requises pour figurer ici.", ephemeral=True)

    # 3. Fonction de tri
    def calculate_sort_metrics(item):
        data = item[1]
        wins = data['wins']
        draws = data['draws']
        total = wins + data['losses'] + draws
        winrate = ((wins + (draws * 0.5)) / total) if total > 0 else 0
        return (winrate, wins)

    # 4. Tri des joueurs filtrés
    sorted_players = sorted(filtered_stats, key=calculate_sort_metrics, reverse=True)

    embed = discord.Embed(
        title=f"🏆 Top Winrate - {titre_de_embed}", 
        description="*Seuls les joueurs avec au moins 10 parties sont affichés.*\n\n",
        color=discord.Color.purple()
    )
    
    description_text = ""
    for index, (user_id, data) in enumerate(sorted_players[:10]):
        wins = data['wins']
        draws = data['draws']
        total = wins + data['losses'] + draws
        winrate = ((wins + (draws * 0.5)) / total * 100)
        
        try:
            user = await bot.fetch_user(int(user_id))
            nom = user.name
        except:
            nom = f"Joueur {user_id}"

        medaille = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else f"#{index+1}"
        
        description_text += (
            f"**{medaille} {nom}**\n"
            f"└─ **{winrate:.1f}%** de réussite ({wins} victoires et {draws} nulles sur {total} matchs)\n\n"
        )

    embed.description += description_text
    await interaction.response.send_message(embed=embed)

def get_title(wins, total):
    if total == 0: return "Nouveau venu"
    if wins >= 100: return "👑 Légende du Morpion"
    if wins >= 50: return "🔥 Grand Maître"
    if wins >= 20 : return "⚔️ Guerrier"
    if total >= 10: return "🛡️ Apprenti"
    return "🌱 Novice"

@bot.tree.command(name="profil", description="Profil d'une personne pour un jeu")
@app_commands.choices(jeu=[
    app_commands.Choice(name="Echecs", value=3),
    app_commands.Choice(name="Puissance 4", value=2),
    app_commands.Choice(name="Morpion", value=1),
])
async def profil(interaction: discord.Interaction, jeu: app_commands.Choice[int], membre: discord.Member = None):
    user = membre or interaction.user
    if jeu.value == 1:
        stats = get_stats("morpion_scores.json")
        titre_de_embed = "Morpion"
    elif jeu.value == 2:
        stats = get_stats("puissance4_stats.json")
        titre_de_embed = "Puissance 4"
    elif jeu.value == 3:
        stats = get_stats("chess_stats.json")
        titre_de_embed = "Echecs"
    else : 
        return await interaction.response.send_message("Ce jeu n'existe pas", ephemeral=True)
    uid = str(user.id)

    if uid not in stats:
        return await interaction.response.send_message("Ce joueur n'a pas encore de statistiques.", ephemeral=True)

    data = stats[uid]
    wins, losses, draws = data['wins'], data['losses'], data['draws']
    total = wins + losses + draws
    
    # --- CALCUL DES CLASSEMENTS ---
    
    # 1. Classement par SCORE (Points : Win=1, Draw=0.5)
    sorted_by_score = sorted(
        stats.items(), 
        key=lambda x: x[1]['wins'] + (x[1]['draws'] * 0.5), 
        reverse=True
    )
    rank_score = next(i for i, (id, _) in enumerate(sorted_by_score) if id == uid) + 1

    # 2. Classement par WINRATE (Qualité de jeu)
    # On ne compte que ceux qui ont joué au moins 3 parties pour éviter les 100% chanceux
    sorted_by_rate = sorted(
        stats.items(), 
        key=lambda x: ((x[1]['wins'] + (x[1]['draws'] * 0.5)) / (x[1]['wins'] + x[1]['losses'] + x[1]['draws'])) if (x[1]['wins'] + x[1]['losses'] + x[1]['draws']) > 0 else 0, 
        reverse=True
    )
    rank_rate = next(i for i, (id, _) in enumerate(sorted_by_rate) if id == uid) + 1

    # --- PRÉPARATION DE L'EMBED ---
    winrate_val = ((wins + (draws * 0.5)) / total * 100) if total > 0 else 0
    titre = get_title(wins, total)

    embed = discord.Embed(
        title=f"Profil de {user.name}", 
        description=f"**Titre :** `{titre}`", 
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    # Section Stats
    embed.add_field(
        name="📊 Statistiques", 
        value=f"Victoires : **{wins}**\n Défaites : **{losses}**\n Nuls : **{draws}**", 
        inline=True
    )
    if not wins+losses+draws >= 10 :
        rank_rate = "Non classé"
        
    # Section Rangs
    embed.add_field(
        name="🏆 Classements", 
        value=f"Rang Score : **#{rank_score}**\n Rang Winrate : **#{rank_rate}**", 
        inline=True
    )

    # Barre de progression visuelle (Optionnel mais stylé)
    progress = int((winrate_val / 100) * 10)
    barre = "🟦" * progress + "⬜" * (10 - progress)
    embed.add_field(name=f"📈 Taux de réussite : {winrate_val:.1f}%", value=barre, inline=False)

    #SYSTEME RAJOUTE (BUg FIX)

    rival_text = "Aucun rival pour le moment."
    if data["rivals"]:
        # On trouve le rival avec le plus de matchs totaux contre nous
        nemesis_id = max(data["rivals"], key=lambda k: data["rivals"][k]["wins"] + data["rivals"][k]["losses"] + data["rivals"][k]["draws"])
        n_data = data["rivals"][nemesis_id]
        n_total = n_data["wins"] + n_data["losses"] + n_data["draws"]
        rival_text = f"**{n_data['name']}** ({n_total} matchs)\n└─ Victoires: {n_data['wins']} | Défaites: {n_data['losses']} | Nulles: {n_data['draws']}"

    # --- Création de l'Embed ---

    embed.add_field(name="🔥 Séries (Streak)", 
                    value=f"Actuelle : **{data.get('current_streak', 0)}**\nRecord : **{data.get('max_streak', 0)}**", inline=True)
    
    embed.add_field(name="⚔️ Plus grand Rival", value=rival_text, inline=False)
    await interaction.response.send_message(embed=embed)
######################################################################################################

import discord
from discord import app_commands
import random

# --- Constantes Visuelles ---
VIDE = "⚫"
ROUGE = "🔴" # Joueur 1
JAUNE = "🟡" # Joueur 2
COLONNES = 7
LIGNES = 6

class Connect4Button(discord.ui.Button):
    def __init__(self, col_index):
        # On crée un bouton pour chaque colonne (1 à 7)
        super().__init__(style=discord.ButtonStyle.secondary, label=str(col_index + 1), row=0 if col_index < 4 else 1)
        self.col = col_index

    async def callback(self, interaction: discord.Interaction):
        view: Connect4Game = self.view
        
        # 1. Vérification du tour
        joueur_actuel = view.player1 if view.turn == 1 else view.player2
        if interaction.user != joueur_actuel:
            return await interaction.response.send_message("Pas touche ! Ce n'est pas ton tour.", ephemeral=True)

        # 2. Placer le jeton (Gravité)
        ligne_jouee = view.drop_piece(self.col, view.turn)
        
        if ligne_jouee == -1:
            return await interaction.response.send_message("Cette colonne est pleine !", ephemeral=True)

        # 3. Vérifier Victoire / Nul
        if view.check_winner(view.turn):
            winner = joueur_actuel
            loser = view.player2 if winner == view.player1 else view.player1
            
            # --- SAUVEGARDE DES SCORES (Ton système JSON) ---
            try:
                # Victoire
                # On met à jour le gagnant (il gagne contre le perdant)
                update_score(winner.id, loser.id, loser.name, 'win', FILE_P4)

                # On met à jour le perdant (il perd contre le gagnant)
                update_score(loser.id, winner.id, winner.name, 'loss', FILE_P4)
            except Exception as e:
                print(f"Erreur de sauvegarde: {e}")

            view.disable_all()
            await interaction.response.edit_message(content=f"🏆 **Victoire de {winner.mention} !**\n\n{view.get_board_str()}", view=view)
            view.stop()

        elif view.is_full():
            # Match Nul
            # Le joueur 1 fait nul contre le joueur 2
            update_score(view.player1.id, view.player2.id, view.player2.name, 'draw', FILE_P4)

            # Le joueur 2 fait nul contre le joueur 1
            update_score(view.player2.id, view.player1.id, view.player1.name, 'draw', FILE_P4)
            
            view.disable_all()
            await interaction.response.edit_message(content=f"🤝 **Match Nul !** La grille est pleine.\n\n{view.get_board_str()}", view=view)
            view.stop()

        else:
            # 4. Tour suivant
            view.turn = 2 if view.turn == 1 else 1
            next_player = view.player2 if view.turn == 2 else view.player1
            pion = JAUNE if view.turn == 2 else ROUGE
            
            # Mise à jour visuelle
            await interaction.response.edit_message(
                content=f"Au tour de {next_player.mention} ({pion})\n\n{view.get_board_str()}", 
                view=view
            )

class Connect4Game(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=300) # 5 minutes max sans jouer

        # 1. Tirage au sort immédiat
        joueurs = [p1, p2]
        random.shuffle(joueurs)
        
        # 2. Attribution des rôles
        # player1 sera toujours ROUGE et commencera
        self.player1 = joueurs[0] 
        self.player2 = joueurs[1]
        
        # 3. Initialisation (Le tour 1 correspond à self.player1)
        self.turn = 1

        # Grille 6 lignes x 7 colonnes remplie de 0
        self.board = [[0 for _ in range(COLONNES)] for _ in range(LIGNES)]

        # Ajouter les boutons (1 à 7)
        for i in range(COLONNES):
            self.add_item(Connect4Button(i))

    def drop_piece(self, col, player):
        """Fait tomber une pièce dans la colonne. Retourne la ligne ou -1 si plein."""
        # On parcourt de bas (5) en haut (0)
        for row in range(LIGNES - 1, -1, -1):
            if self.board[row][col] == 0:
                self.board[row][col] = player
                return row
        return -1

    def get_board_str(self):
        """Convertit la matrice en string d'emojis"""
        display = ""
        for row in self.board:
            for cell in row:
                if cell == 0: display += VIDE
                elif cell == 1: display += ROUGE
                elif cell == 2: display += JAUNE
            display += "\n"
        # Ajout des numéros en bas
        display += "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣" 
        return display

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    def is_full(self):
        # Si la ligne du haut (0) ne contient aucun 0, c'est plein
        return all(self.board[0][c] != 0 for c in range(COLONNES))

    def check_winner(self, player):
        # Vérification Horizontale, Verticale et Diagonales
        # 1. Horizontal
        for c in range(COLONNES - 3):
            for r in range(LIGNES):
                if self.board[r][c] == player and self.board[r][c+1] == player and self.board[r][c+2] == player and self.board[r][c+3] == player:
                    return True

        # 2. Vertical
        for c in range(COLONNES):
            for r in range(LIGNES - 3):
                if self.board[r][c] == player and self.board[r+1][c] == player and self.board[r+2][c] == player and self.board[r+3][c] == player:
                    return True

        # 3. Diagonale positive (/)
        for c in range(COLONNES - 3):
            for r in range(3, LIGNES):
                if self.board[r][c] == player and self.board[r-1][c+1] == player and self.board[r-2][c+2] == player and self.board[r-3][c+3] == player:
                    return True

        # 4. Diagonale négative (\)
        for c in range(COLONNES - 3):
            for r in range(LIGNES - 3):
                if self.board[r][c] == player and self.board[r+1][c+1] == player and self.board[r+2][c+2] == player and self.board[r+3][c+3] == player:
                    return True
        return False

@bot.tree.command(name="puissance4", description="Défier quelqu'un au Puissance 4")
async def puissance4(interaction: discord.Interaction, adversaire: discord.Member):
    if adversaire.bot:
        return await interaction.response.send_message("Les robots sont trop forts au Puissance 4...", ephemeral=True)
    if adversaire == interaction.user:
        return await interaction.response.send_message("Tu ne peux pas jouer contre toi-même.", ephemeral=True)

    view = Connect4Game(interaction.user, adversaire)
    
    # On récupère qui commence
    first_player = view.player1
    pion = ROUGE # Le joueur 1 a toujours les rouges
    
    await interaction.response.send_message(
        f"🔵 **Puissance 4** : {interaction.user.mention} VS {adversaire.mention}\n"
        f"C'est parti ! **{first_player.mention}** commence ({pion})\n\n"
        f"{view.get_board_str()}",
        view=view
    )
import chess
import chess.svg
from io import BytesIO

# -------------------------------------------------------------------------
#   _____ _    _ ______  _____  _____ 
#  / ____| |  | |  ____|/ ____|/ ____|
# | |    | |__| | |__  | (___ | (___  
# | |    |  __  |  __|  \___ \ \___ \ 
# | |____| |  | | |____ ____) |____) |
#  \_____|_|  |_|______|_____/|_____/ 
#
# >>> SYSTÈME D'ÉCHECS INTERACTIF <<<
# -------------------------------------------------------------------------
os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + r'C:\Users\LOUP.RAINGEARD\AppData\Local\Programs\Python\Python314\Lib\site-packages\cairo'
# -------------------------------------------------------------------------
#   _____ _    _ ______  _____  _____ 
#  / ____| |  | |  ____|/ ____|/ ____|
# | |    | |__| | |__  | (___ | (___  
# | |    |  __  |  __|  \___ \ \___ \ 
# | |____| |  | | |____ ____) |____) |
#  \_____|_|  |_|______|_____/|_____/ 
#
# >>> SYSTÈME D'ÉCHECS INTERACTIF (MENUS) <<<
# -------------------------------------------------------------------------
import time

class ChessGame(discord.ui.View):
    def __init__(self, white_player, black_player, timer_minutes):
        super().__init__(timeout=None)
        self.board = chess.Board()
        self.white = white_player
        self.black = black_player
        self.board_theme = "green"
        
        # On stockera les deux messages ici
        self.board_message = None 
        self.timer_message = None
        
        # Gestion du Timer
        self.timer_minutes = timer_minutes
        self.timer_started = False
        self.last_move_timestamp = None
        
        self.selected_type = None    
        self.selected_square = None  
        
        # Init du Timer
        if self.timer_minutes > 0:
            self.time_left = {
                chess.WHITE: timer_minutes * 60,
                chess.BLACK: timer_minutes * 60
            }
            # On lance la tâche unique pour cette partie
            self.timer_task = tasks.loop(seconds=5)(self.timer_callback)
            self.timer_task.start()
        else:
            self.time_left = None
            self.timer_task = None

        self.create_menus()
    # --- 1. LA BOUCLE DE FOND (Met à jour le temps et l'image toutes les 5s) ---
class ChessGame(discord.ui.View):
    def __init__(self, white_player, black_player, timer_minutes):
        super().__init__(timeout=None)
        self.board = chess.Board()
        self.white = white_player
        self.black = black_player
        self.board_theme = "green"
        
        # On stockera les deux messages ici
        self.board_message = None 
        self.timer_message = None
        
        # Gestion du Timer
        self.timer_minutes = timer_minutes
        self.timer_started = False
        self.last_move_timestamp = None
        
        self.selected_type = None    
        self.selected_square = None  
        
        # Init du Timer
        if self.timer_minutes > 0:
            self.time_left = {
                chess.WHITE: timer_minutes * 60,
                chess.BLACK: timer_minutes * 60
            }
            # On lance la tâche unique pour cette partie
            self.timer_task = tasks.loop(seconds=5)(self.timer_callback)
            self.timer_task.start()
        else:
            self.time_left = None
            self.timer_task = None

        self.create_menus()

    # --- BOUCLE DE TIMER (Ne touche qu'au message du haut) ---
    async def timer_callback(self):
        if not self.timer_message or not self.timer_started:
            return

        now = time.time()
        elapsed = now - self.last_move_timestamp
        current_turn = self.board.turn
        
        self.time_left[current_turn] -= elapsed
        self.last_move_timestamp = now
        
        # Vérification défaite
        if self.time_left[current_turn] <= 0:
            self.time_left[current_turn] = 0
            self.stop_all()
            
            winner = self.black if current_turn == chess.WHITE else self.white
            loser = self.white if current_turn == chess.WHITE else self.black
            
            # Mise à jour du message du haut (Timer) pour annoncer la fin
            await self.timer_message.edit(content=f"⏰ **FIN DU TEMPS !** Victoire de {winner.mention}")
            
            # Désactivation du plateau
            await self.end_game_visuals(winner, loser, "temps")
            return

        # MISE À JOUR DU TEXTE (Pas d'image ici !)
        def format_time(seconds):
            mins, secs = divmod(int(max(0, seconds)), 60)
            return f"{mins:02d}:{secs:02d}"

        # On crée une belle barre de temps
        t_blanc = format_time(self.time_left[chess.WHITE])
        t_noir = format_time(self.time_left[chess.BLACK])
        
        # Indicateur visuel de qui joue (🔴 pour le tour en cours)
        icon_w = "🔴" if self.board.turn == chess.WHITE else "⚪"
        icon_b = "🔴" if self.board.turn == chess.BLACK else "⚫"
        
        msg_content = (
            f"⏱️ **CHRONO**\n"
            f"{icon_w} **Blancs** ({self.white.display_name}) : `{t_blanc}`\n"
            f"{icon_b} **Noirs** ({self.black.display_name}) : `{t_noir}`"
        )
        
        try:
            await self.timer_message.edit(content=msg_content)
        except:
            pass

    # --- MISE À JOUR DU JEU (Appelée quand on joue un coup) ---
    async def update_message(self, interaction):
        now = time.time()
        
        # Logique de calcul précise (identique à avant)
        if self.timer_minutes > 0:
            if not self.timer_started:
                if len(self.board.move_stack) >= 2:
                    self.timer_started = True
                    self.last_move_timestamp = now
                    # On force une mise à jour immédiate du texte du timer
                    await self.timer_message.edit(content="🏁 **Le timer vient de démarrer !**")
            else:
                if self.last_move_timestamp is not None:
                    elapsed = now - self.last_move_timestamp
                    previous_turn = not self.board.turn
                    self.time_left[previous_turn] -= elapsed
                    self.last_move_timestamp = now
                    
                    if self.time_left[previous_turn] <= 0:
                        winner = self.black if previous_turn == chess.WHITE else self.white
                        await self.timer_message.edit(content=f"⏰ **FIN DU TEMPS !** Victoire de {winner.mention}")
                        return await self.end_game_visuals(winner, interaction.user, "temps")

        # Mise à jour du PLATEAU (Embed)
        image_url = get_chess_board_image(self.board, self.board_theme) + f"&t={int(now)}"
        embed = interaction.message.embeds[0] # On récupère l'embed du message cliqué
        embed.set_image(url=image_url)
        
        tour_nom = self.white.display_name if self.board.turn == chess.WHITE else self.black.display_name
        couleur = "Blancs" if self.board.turn == chess.WHITE else "Noirs"
        embed.description = f"Trait aux **{couleur}** ({tour_nom})"

        # Vérification Mat / Nul
        if self.board.is_checkmate():
            gagnant = self.black if self.board.turn == chess.WHITE else self.white
            perdant = self.white if gagnant == self.black else self.black
            await self.timer_message.edit(content=f"🏆 **VICTOIRE** de {gagnant.mention} par échec et mat !")
            await self.end_game_visuals(gagnant, perdant, "mat")
            
        elif self.board.is_game_over():
            await self.timer_message.edit(content="🤝 **MATCH NUL**")
            await self.end_game_visuals(None, None, "nul")
            
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    # --- GESTION DE FIN VISUELLE ---
    async def end_game_visuals(self, winner, loser, reason):
        self.stop_all()
        
        # On met à jour l'embed du plateau une dernière fois
        embed = self.board_message.embeds[0]
        if reason == "mat":
            embed.color = discord.Color.gold()
            embed.description = "🏁 **ÉCHEC ET MAT**"
        elif reason == "temps":
            embed.color = discord.Color.orange()
            embed.description = "⏰ **TEMPS ÉCOULÉ**"
        elif reason == "abandon":
            embed.color = discord.Color.red()
            embed.description = "🏳️ **ABANDON**"
        
        # Update Stats (si tu as la fonction)
        if winner and loser:
            update_chess_stats(winner.id, loser.id, loser.name, 'win')
            update_chess_stats(loser.id, winner.id, winner.name, 'loss')

        try:
            await self.board_message.edit(embed=embed, view=None)
        except:
            pass

    async def resign_callback(self, interaction: discord.Interaction):
        if interaction.user not in [self.white, self.black]:
            return await interaction.response.send_message("Tu ne joues pas !", ephemeral=True)
        
        winner = self.black if interaction.user == self.white else self.white
        await self.timer_message.edit(content=f"🏳️ **ABANDON** de {interaction.user.mention}. Victoire de {winner.mention}")
        await self.end_game_visuals(winner, interaction.user, "abandon")

    def stop_all(self):
        if hasattr(self, 'timer_task') and self.timer_task and self.timer_task.is_running():
            self.timer_task.stop()
        
    def create_menus(self):
        self.clear_items()
        
        # 1. MENU TYPE DE PIÈCE (Toujours plein au début)
        type_select = discord.ui.Select(placeholder="1. Quel type de pièce ?", custom_id="type_select")
        available_types = set()
        for move in self.board.legal_moves:
            piece = self.board.piece_at(move.from_square)
            available_types.add(piece.piece_type)
        
        for p_type in sorted(list(available_types)):
            type_select.add_option(
                label=self.get_piece_name(p_type), 
                value=str(p_type), 
                default=(self.selected_type == p_type)
            )
        type_select.callback = self.type_callback
        self.add_item(type_select)

        # 2. MENU PIÈCE PRÉCISE
        piece_select = discord.ui.Select(placeholder="2. Laquelle précisément ?", disabled=(self.selected_type is None))
        if self.selected_type:
            squares = [s for s in chess.SQUARES if self.board.piece_at(s) and 
                       self.board.piece_at(s).piece_type == self.selected_type and
                       self.board.piece_at(s).color == self.board.turn]
            for s in squares:
                if any(m.from_square == s for m in self.board.legal_moves):
                    piece_select.add_option(label=f"Position {chess.square_name(s)}", value=str(s), default=(self.selected_square == s))
        else:
            # L'astuce est ici : on ajoute une option invisible pour éviter l'erreur 400
            piece_select.add_option(label="En attente de l'étape 1...", value="none")
        
        piece_select.callback = self.piece_callback
        self.add_item(piece_select)

        # 3. MENU DESTINATION
        dest_select = discord.ui.Select(placeholder="3. Où aller ?", disabled=(self.selected_square is None))
        if self.selected_square is not None:
            for move in self.board.legal_moves:
                if move.from_square == self.selected_square:
                    dest_select.add_option(label=f"Vers {chess.square_name(move.to_square)}", value=move.uci())
        else:
            # Même astuce ici
            dest_select.add_option(label="En attente de l'étape 2...", value="none")
        
        dest_select.callback = self.dest_callback
        self.add_item(dest_select)
        cancel_btn = discord.ui.Button(label="Réinitialiser", style=discord.ButtonStyle.secondary, disabled=(self.selected_type is None))
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

        # 5. NOUVEAU : BOUTON ABANDONNER
        resign_btn = discord.ui.Button(label="Abandonner", style=discord.ButtonStyle.danger, emoji="🏳️")
        resign_btn.callback = self.resign_callback
        self.add_item(resign_btn)
        # (Le reste du code pour les boutons reste identique)

    # --- CALLBACKS ---
    def check_turn(self, interaction):
        return interaction.user == (self.white if self.board.turn == chess.WHITE else self.black)

    async def type_callback(self, interaction: discord.Interaction):
        if not self.check_turn(interaction): return await interaction.response.send_message("Pas votre tour !", ephemeral=True)
        self.selected_type = int(interaction.data['values'][0])
        self.selected_square = None 
        self.create_menus()
        await interaction.response.edit_message(view=self)

    async def piece_callback(self, interaction: discord.Interaction):
        if not self.check_turn(interaction): return
        self.selected_square = int(interaction.data['values'][0])
        self.create_menus()
        await interaction.response.edit_message(view=self)

    async def cancel_callback(self, interaction: discord.Interaction):
        if not self.check_turn(interaction): return
        self.selected_type = None
        self.selected_square = None
        self.create_menus()
        await interaction.response.edit_message(view=self)

    async def dest_callback(self, interaction: discord.Interaction):
        if not self.check_turn(interaction): return
        move = chess.Move.from_uci(interaction.data['values'][0])
        
        # Promotion auto Reine
        if self.board.piece_at(move.from_square).piece_type == chess.PAWN:
            if chess.square_rank(move.to_square) in [0, 7]:
                move.promotion = chess.QUEEN

        self.board.push(move)
        self.selected_type = None
        self.selected_square = None
        self.create_menus()
        await self.update_message(interaction)



    async def end_game_logic(self, interaction, winner, loser, reason):
        embed = interaction.message.embeds[0]
        if reason == "temps":
            embed.description = f"⏰ **TEMPS ÉCOULÉ !**\n{loser.mention} a manqué de temps. Victoire de {winner.mention} !"
            embed.color = discord.Color.orange()
            update_chess_stats(winner.id, loser.id, loser.name, 'win')
            update_chess_stats(loser.id, winner.id, winner.name, 'loss')
            self.stop_all()
        if reason == "mat":
            embed.description = f"🏁 **ÉCHEC ET MAT !**\nVictoire de {winner.mention} !"
            embed.color = discord.Color.gold()
            update_chess_stats(winner.id, loser.id, loser.name, 'win')
            update_chess_stats(loser.id, winner.id, winner.name, 'loss')
        elif reason == "abandon":
            embed.description = f"🏳️ **ABANDON**\n{loser.mention} a quitté. Victoire de {winner.mention} !"
            update_chess_stats(winner.id, loser.id, loser.name, 'win')
            update_chess_stats(loser.id, winner.id, winner.name, 'loss')
        else:
            embed.description = "🤝 **MATCH NUL !**"
            update_chess_stats(self.white.id, self.black.id, self.black.name, 'draw')
            update_chess_stats(self.black.id, self.white.id, self.white.name, 'draw')

        await interaction.response.edit_message(embed=embed, view=None)

    def get_piece_name(self, p_type):
        return {chess.PAWN: "Pion", chess.KNIGHT: "Cavalier", chess.BISHOP: "Fou", 
                chess.ROOK: "Tour", chess.QUEEN: "Dame", chess.KING: "Roi"}[p_type]

class MoveModal(discord.ui.Modal, title="Votre coup (ex: e2e4)"):
    move_input = discord.ui.TextInput(label="Coup en notation LAN", placeholder="e2e4, g1f3...")

    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view

    async def on_submit(self, interaction: discord.Interaction):
        move_str = self.move_input.value.lower()
        try:
            move = chess.Move.from_uci(move_str)
            if move in self.game_view.board.legal_moves:
                self.game_view.board.push(move)
                
                # On change de tour
                self.game_view.turn = self.game_view.black if self.game_view.turn == self.game_view.white else self.game_view.white
                
                await interaction.response.defer()
                await self.game_view.update_message(interaction)
                
                # Vérification fin de partie
                if self.game_view.board.is_game_over():
                    await interaction.followup.send(f"Partie terminée ! Résultat : {self.game_view.board.result()}")
            else:
                await interaction.response.send_message("Coup illégal !", ephemeral=True)
        except:
            await interaction.response.send_message("Format invalide (utilisez e2e4).", ephemeral=True)
# Fichier : chess_stats.json
def update_chess_stats(user_id, opponent_id, opponent_name, result):
    stats = get_stats("chess_stats.json")
    uid, oid = str(user_id), str(opponent_id)

    if uid not in stats:
        stats[uid] = {"wins": 0, "losses": 0, "draws": 0, "current_streak": 0, "max_streak": 0, "rivals": {}}
    
    player = stats[uid]
    if oid not in player["rivals"]:
        player["rivals"][oid] = {"name": opponent_name, "wins": 0, "losses": 0, "draws": 0}

    if result == 'win':
        player["wins"] += 1
        player["rivals"][oid]["wins"] += 1
        player["current_streak"] += 1
        if player["current_streak"] > player["max_streak"]: player["max_streak"] = player["current_streak"]
    elif result == 'loss':
        player["losses"] += 1
        player["rivals"][oid]["losses"] += 1
        player["current_streak"] = 0
    elif result == 'draw':
        player["draws"] += 1
        player["rivals"][oid]["draws"] += 1

    save_stats("chess_stats.json", stats)

import chess
import urllib.parse


def get_chess_board_image(board, chess_board_color="green"):
    fen = board.fen()
    fen_position = fen.split(" ")[0]
    # On ajoute &coordinates=true pour afficher les lettres et les chiffres
    # On peut aussi changer le style (board=blue, brown, green...)
    image_url = f"https://www.chess.com/dynboard?fen={fen_position}&size=2&board={chess_board_color}&piece=neo&coordinates=true"
    
    return image_url

# --- LA COMMANDE DE LANCEMENT ---
@bot.tree.command(name="echecs", description="Lancer une partie d'échecs avec stats")
@app_commands.choices(couleur_du_plateau=[
    app_commands.Choice(name="Vert", value="green"),
    app_commands.Choice(name="Marron", value="brown"),
    app_commands.Choice(name="Bleu", value="blue"),
])
async def echecs(interaction: discord.Interaction, adversaire: discord.Member, couleur_du_plateau: app_commands.Choice[str]= None, timer: int = 0):
    if adversaire.bot or adversaire == interaction.user:
        return await interaction.response.send_message("Cible invalide !", ephemeral=True)

    await interaction.response.defer()
    
    couleur_plateau = couleur_du_plateau.value if couleur_du_plateau else "green"
    joueurs = [interaction.user, adversaire]
    random.shuffle(joueurs)
    blanc, noir = joueurs[0], joueurs[1]

    # 1. Création de la View
    view = ChessGame(white_player=blanc, black_player=noir, timer_minutes=timer)
    view.board_theme = couleur_plateau 
    
    # 2. MESSAGE 1 : LE TIMER (Envoyé en réponse à la commande)
    # On prépare le texte initial
    if timer > 0:
        txt_timer = f"⏱️ **CHRONO**\n⚪ Blancs: `{timer}:00`\n⚫ Noirs: `{timer}:00`\n*En attente du démarrage...*"
    else:
        txt_timer = f"♾️ **PARTIE AMICALE** (Pas de temps)\n⚪ {blanc.mention} vs ⚫ {noir.mention}"

    # On envoie le message du Timer
    msg_timer = await interaction.followup.send(content=txt_timer, wait=True)
    
    # 3. MESSAGE 2 : LE PLATEAU (Envoyé juste après dans le canal)
    image_url = get_chess_board_image(view.board, couleur_plateau)
    embed = discord.Embed(title="♟️ Match d'Échecs", color=0x2b2d31)
    embed.description = f"Trait aux **Blancs** ({blanc.display_name})"
    embed.set_image(url=image_url)
    # Plus besoin de Fields pour le temps dans l'embed !
    
    # On envoie le message du Plateau avec les boutons
    msg_board = await interaction.channel.send(embed=embed, view=view)
    
    # 4. On lie les messages à la View
    view.timer_message = msg_timer
    view.board_message = msg_board
# -------------------------------------------------------------------------
#  _____ _    _ _____ _______ ______ 
# / ____| |  | |_   _|__   __|  ____|
# \__  \| |  | | | |    | |  | |__   
#  ___  \ |  | | | |    | |  |  __|  
#  ____) | |__| |_| |_   | |  | |____ 
# |_____/ \____/|_____|  |_|  |______|
#
# -------------------------------------------------------------------------
prive = str(os.getenv('PRIVATE_KEY'))
keep_alive()
bot.run(prive)

