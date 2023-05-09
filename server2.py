import os, shutil, sys, Ice
import random
import string
import uuid
from flask import Flask, jsonify
from pymongo import MongoClient
import boto3
import requests
import Demo2
import glob
import vlc
from bson.objectid import ObjectId

# Global variable used for project

MONGODB_URI = ""

client = MongoClient(MONGODB_URI)
db = client['Music']  # Remplacez 'db_name' par le nom de votre base de données
musique_collection = db['content']  # Remplacez 'musique' par le nom de votre collection

UPLOAD_FOLDER = 'uploads2'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''
AWS_REGION = ''

S3_BUCKET_NAME = ''
CLOUDFRONT_DOMAIN = ''

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)


# Fonction d'upload vers le bucket S3
def upload_to_s3(file, s3_key):
    with open(file, "rb") as f:
        s3_client.upload_fileobj(f, S3_BUCKET_NAME, s3_key)
    return f"https://{CLOUDFRONT_DOMAIN}/{s3_key}"


# Fonction d'upload vers la base de données MongoDB
def upload_files(pochetteName, sonName):
    pochette = os.path.join(os.getcwd(), UPLOAD_FOLDER, pochetteName)
    son = os.path.join(os.getcwd(), UPLOAD_FOLDER, sonName)
    print(sonName, pochetteName)

    if not pochette or not son:
        print('Les fichiers pochette et son sont requis')
        return 'Les fichiers pochette et son sont requis'

    try:
        # Générer un identifiant unique pour chaque fichier
        unique_id = str(uuid.uuid4())

        # Upload de la pochette sur Amazon S3
        pochette_s3_key = f'pochettes/{unique_id}.' + pochetteName.split('.')[1]
        pochette_url = upload_to_s3(pochette, pochette_s3_key)

        # Upload du fichier son sur Amazon S3
        son_s3_key = f'sons/{unique_id}.mp3'
        son_url = upload_to_s3(son, son_s3_key)

        # Ajouter les URL à MongoDB
        new_music = {
            'pochette_url': pochette_url,
            'son_url': son_url,
            'state': 1,
            'name': sonName,
            'current_provider': 'self'
        }
        result = musique_collection.insert_one(new_music) # Insertion dans la BDD

        # print(musique)
        path_son = UPLOAD_FOLDER + "/" + sonName
        # newPath_son = "uploads2/" + result.inserted_id + "_" + sonName
        newPath_son = UPLOAD_FOLDER + "/" + str(result.inserted_id) + "_" + sonName

        path = UPLOAD_FOLDER + "/" + pochetteName
        # newPath = "uploads2/" + result.inserted_id + "_" + pochetteName
        newPath = UPLOAD_FOLDER + "/" + str(result.inserted_id) + "_pochette.jpg"

        if os.path.exists(path):
            # musique_collection.update_one({'_id': result.inserted_id},{"$set": {'name': str(result.inserted_id) + '_' + new_music['name']}})
            musique_collection.update_one({'_id': result.inserted_id}, {"$set": {'name': new_music["name"]}})
            os.rename(path, newPath)
            os.rename(path_son, newPath_son)
            print("Fichier " + path + " à été renommé en " + newPath)
            print("Fichier " + path_son + " à été renommé en " + newPath_son)
            return 1

        return 0

    except Exception as e:
        return str(e)

# Fonction de récupération des musiques
# Cette dernière compare les musiques locale à celles de la BDD et ne récupère que celle présente en ligne
def scanMusic():
    # On récupère les musiques de la BDD
    musiques = list(musique_collection.find({}))
    rsltMusiques = []

    for musique in musiques: # On parcour l'ensemble des musiques récupéré puis on les formates à notre convenance
        musique['_id'] = str(musique['_id'])  # Convertir l'ID en chaîne de caractères
        pochette_url = musique['pochette_url']
        pochette_path = os.path.join(UPLOAD_FOLDER, f"{musique['_id']}_pochette.jpg")
        son_path = os.path.join(UPLOAD_FOLDER, f"{musique['_id']}_{musique['name']}")

        # Lier l'URL locale de la pochette à la musique
        musique['pochette_url'] = pochette_url
        musique['pochette_path'] = pochette_path
        musique['son_path'] = son_path

        if os.path.exists(son_path):
            rsltMusiques.append(musique) # Si la musique existe en locale on la rajoute à la liste des musiques retournées
    return rsltMusiques

# Class représentant l'interface Printer de Ice
class PrinterI(Demo2.Printer):
    # Variable globale utilisé pour l'import des musiques
    numberOfFile = 0
    oldFileName = ''
    fileType = 0

    def __init__(self): # Constructeur avec instrantiation de VLC
        self.player = vlc.Instance()
        self.media_player = self.player.media_player_new()
        self.index = 0
        self.uploadingFiles = {}
        self.musiques = scanMusic()
        self.pauseStatus = 0
        for musique in self.musiques:
            print(musique)

    # Fonction de test et débuggage
    def printString(self, s, current=None):
        print(s)

    # Fonction servant à renommer un fichier
    def renameFile(self, fileId, newName, current=None):
        newName = string.capwords(newName.lower()) # On formate la string reçu
        musique = musique_collection.find_one({"_id": ObjectId(fileId)}) # On cherche la musique correspondant sur la BDD

        if musique:
            # On set les path (old et new) afin de modifier le nom du fichier
            path = UPLOAD_FOLDER + "/" + str(musique.get('_id')) + "_" + musique.get('name')
            newPath = UPLOAD_FOLDER + "/" + str(musique.get('_id')) + "_" + newName + ".mp3"

        if os.path.exists(path):
            # On rename sur la BDD avant de faire de même en locale
            musique_collection.update_one({'_id': ObjectId(fileId)}, {"$set": {'name': newName + '.mp3'}})
            os.rename(path, newPath)
            print("Fichier " + path + " à été renommé en " + newPath)
            self.musiques = scanMusic() # On actualise les musiques en mémoire
            return 1
        print("Le fichier " + path + " n'existe pas.")
        return 0

    # Fonction servant à supprimer un fichier
    def deleteFile(self, filename, current=None):
        self.musiques = scanMusic()
        toBeDeleted = filename.split('_')[0] # On récupère l'ID

        # On set les path pour la suppression
        path = UPLOAD_FOLDER + "/" + filename
        imgPath = UPLOAD_FOLDER + "/" + toBeDeleted + "_pochette.jpg"

        if (os.path.exists(imgPath)):
            os.remove(imgPath)

        if (os.path.exists(path)):
            # On supprime en local puis sur la BDD
            os.remove(path)
            musique_collection.delete_one({'_id': ObjectId(toBeDeleted)})
            self.musiques = scanMusic()
            print("Fichier " + filename + " supprimé.")
            return 1
        print("Le fichier " + path + " n'existe pas.")
        return 0

    # Fonction servant à rechercher un fichier
    def findFile(self, filename, current=None):
        print(filename)
        orig_dir = os.getcwd()
        # Change le répertoire courant pour celui des musiques
        os.chdir(UPLOAD_FOLDER)

        musicList = []
        # On récupère l'ensemble des fichiers de type .mp3 du répertoire
        for file in glob.glob("*" + filename + "*.mp3"):
            # On ajoute l'Id afin de servir en ca de suppréssion ou changement de nom
            musicList.append("Id: " + file.rsplit('_', 1)[0] + " | Name: " + file.rsplit('.mp3', 1)[0].rsplit('_')[1])

        os.chdir(orig_dir)
        return musicList

    # Fonction servant à récupérer le nom complet d'un fichier en fonction de son Id
    def getFullFileName(self, id, current=None):
        orig_dir = os.getcwd()
        # Change le répertoire courant pour celui des musiques
        os.chdir(UPLOAD_FOLDER)

        music = ''
        # On récupère l'ensemble des fichiers de type .mp3 du répertoire
        for file in glob.glob(id + "*.mp3"):
            # On ajoute l'Id afin de servir en ca de suppréssion ou changement de nom
            music = file

        os.chdir(orig_dir)
        return music

    # Fonction servant principallement pour le projet architecture distribué.
    # Elle permet de renvoyer toutes les musiques locales dans une String formatté pour être compréhensible par l'app mobile
    def scanFolder(self, current=None):
        self.musiques = scanMusic()
        musicList = []
        ids = set([])
        folder = UPLOAD_FOLDER

        for filename in os.listdir(folder):
            expl = filename.split('_')
            ids.add(expl[0])
            print(filename, ids)

        scanned = set([])

        for objId in ids:
            for musique in self.musiques:
                if str(musique['_id']) == objId and objId not in scanned:
                    scanned.add(objId)
                    musicList.append(musique['name'][:-4] + "|" + musique['pochette_url'] + "|" + musique['_id'])

        print(musicList)
        return musicList

    # Fonction servant à lancer une musique à partir de son titre uniquement
    def playFile(self, filename, current=None):
        self.musiques = scanMusic() # On met à jour les musiques en mémoire

        # Si une musique est déjà en cour de lecture ou si un musique est sur pause
        # On arrête la musique actuel avant de lancer à nouveau la fonction
        if self.media_player.is_playing() or self.pauseStatus == 1:
            self.media_player.stop()
            self.pauseStatus = 0
            return self.playFile(filename)

        # On recherche parmis l'ensemble des musique une possédant le même nom
        for musique in self.musiques:
            if musique['name'].split('.')[0].lower() == filename:
                filename = musique['_id'] + '_' + musique['name']
        print(filename)

        file = UPLOAD_FOLDER + "/" + filename # On set le path
        print("FIchier existe: ")
        print(os.path.exists(file))
        if os.path.exists(file) != True: return False # Si le path ne correspond pas on interromp l'exécution
        # On configure l'ensemble des options du player afin de pouvoir lancer le stream
        self.media = self.player.media_new(file) # Affecation du fichier à lire

        # Setting media options to cast it
        self.media.add_option("sout=#rtp{mux=ts,ttl=10,port=5000,sdp=rtsp://127.0.0.1:5000/music}") # Configuration réseau
        self.media.add_option("--no-sout-all")
        self.media.add_option("--sout-keep")
        self.media.get_mrl()

        self.media_player = self.player.media_player_new()
        self.media_player.set_media(self.media)

        self.media_player.play() # Lancement de la musique
        return True

    # Fonction servant à lancer une musique à partir d'un artiste
    def playFileFromArtiste(self, filename, current=None):
        print(self.media_player.is_playing())
        musiqueSelected = list()
        numberOfSongs = 0
        self.musiques = scanMusic()

        if self.media_player.is_playing() or self.pauseStatus == 1:
            self.media_player.stop()
            self.pauseStatus = 0
            return self.playFileFromArtiste(filename)

        # Ici on ajoutera l'ensemble des musiques de l'artiste
        for musique in self.musiques:
            print(musique)
            if bool(musique.get('artiste')):
                if musique['artiste'].lower() == filename:
                    musiqueSelected.append(musique['_id'] + "_" + musique['name'])
                    numberOfSongs += 1

        if numberOfSongs == 0: return False

        print(musiqueSelected)

        filename = random.choice(musiqueSelected) # On choisi une musique au hasard parmis celles sélectionnées

        print(filename)

        file = UPLOAD_FOLDER + "/" + filename
        print("FIchier existe: ")
        print(os.path.exists(file))
        if os.path.exists(file) != True: return False
        self.media = self.player.media_new(file)

        # Setting media options to cast it
        self.media.add_option("sout=#rtp{mux=ts,ttl=10,port=5000,sdp=rtsp://127.0.0.1:5000/music}")
        self.media.add_option("--no-sout-all")
        self.media.add_option("--sout-keep")
        self.media.get_mrl()

        self.media_player = self.player.media_player_new()
        self.media_player.set_media(self.media)

        print(self.media_player.is_playing())
        self.media_player.play()
        return True

    # Fonction servant à lancer une musique à partir d'un artiste et du titre de la chanson
    # Elle fonctionne sur le même principe que playFileFromArtiste avec comme seul changement un vérification
    # supplémentaire sur le titre
    def playFileFromSongAndArtiste(self, artiste, son, current=None):
        print(self.media_player.is_playing())
        self.musiques = scanMusic()

        if self.media_player.is_playing() or self.pauseStatus == 1:
            self.media_player.stop()
            self.pauseStatus = 0
            return self.playFileFromSongAndArtiste(artiste, son)

        for musique in self.musiques:
            if bool(musique.get('artiste')):
                if musique['name'].split('.')[0].lower() == son and musique['artiste'].lower() == artiste:
                    filename = musique['_id'] + '_' + musique['name']
        print(filename)

        file = UPLOAD_FOLDER + "/" + filename
        print("FIchier existe: ")
        print(os.path.exists(file))
        if os.path.exists(file) != True: return False
        self.media = self.player.media_new(file)

        # Setting media options to cast it
        self.media.add_option("sout=#rtp{mux=ts,ttl=10,port=5000,sdp=rtsp://127.0.0.1:5000/music}")
        self.media.add_option("--no-sout-all")
        self.media.add_option("--sout-keep")
        self.media.get_mrl()

        self.media_player = self.player.media_player_new()
        self.media_player.set_media(self.media)

        print(self.media_player.is_playing())
        self.media_player.play()
        return True

    # Fonction servant à arrêter la lecture
    def stopFile(self, current=None):
        self.media_player.stop()

    # Fonction servant à mettre en pause la lecture
    def pause(self, current=None):
        self.media_player.set_pause(1)

    # Fonction servant à reprendre la lecture
    def resume(self, current=None):
        self.media_player.set_pause(0)

    # Fonction servant à récupérer paquet par paquet un fichier en cour d'upload
    def uploadPart(self, id, part, current=None):
        if id not in self.uploadingFiles: self.uploadingFiles[id] = b""
        self.uploadingFiles[id] += part
        return 0

    # Fonction servant à envoyer les fichier récupérer sur la BDD
    def uploadFile(self, id, filename, current=None):
        self.numberOfFile += 1 # On incrémente cette variable afin de savoir si on a bien récupéré les deux fichiers
        result = 0

        # On écris le fichier récupérer grâce à upload parts dans le répertoire des musiques
        file = open(UPLOAD_FOLDER + "/" + filename, "wb")
        file.write(self.uploadingFiles[id])
        file.close()

        # Si les deux fichiers ont bien été récupéré, on appel la fonction d'upload vers la BDD
        if (self.numberOfFile == 2):
            # Le type d'appel change en fonction de l'ordre de réception des fichiers (jpg, mp3 ou mp3, jpg)
            if self.fileType == 0:
                # mp3, jpg
                result = upload_files(filename, string.capwords(self.oldFileName.lower()))
                self.musiques = scanMusic() # On met à jour les musiques en mémoires
            else:
                # jpg, mp3
                result = upload_files(self.oldFileName, string.capwords(filename.lower()))
                self.musiques = scanMusic() # On met à jour les musiques en mémoires
            # On reinitialise la fonciton à son état initiale
            self.numberOfFile = 0
            self.oldFileName = ''

            return result
        else:
            # On détermine le type d'appel à effectué en fonction du premier fichier reçu et on enregistre son nom
            self.oldFileName = filename
            if filename[-3:] == 'mp3':
                self.fileType = 0
            else:
                self.fileType = 1
        return result

    # Fonction servant à générer un nouvel inde pour l'upload des fichiers afin de ne pas écrire sur un fichier déjà existant
    def getNewIndex(self, current=None):
        index = self.index
        self.index += 1
        return index

    # Fonction servant à connaitre l'état de lecture du player VLC
    def isPlaying(self, current=None):
        return self.media_player.is_playing()


with Ice.initialize(sys.argv) as communicator:
    # print(get_musiques())
    adapter = communicator.createObjectAdapterWithEndpoints("SimplePrinterAdapter", "default -p 10001")
    object = PrinterI()
    adapter.add(object, communicator.stringToIdentity("SimplePrinter"))
    adapter.activate()
    # adapter = communicator.createObjectAdapterWithEndpoints("FileServiceAdapter", "default -p 10000")
    # adapter.add(FileServiceI(), communicator.stringToIdentity("FileService"))
    # adapter.activate()
    communicator.waitForShutdown()
