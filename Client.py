import Ice
#Ice.loadSlice("Printer.ice")
import Demo2
import glob
import vlc
#import readline
import os

class ClientPlayer:

    def __init__(self):
        self.vlcInstance = vlc.Instance()
        self.player = self.vlcInstance.media_player_new()
        self.player.set_mrl("rtsp://127.0.0.1:5000/music")
        self.musicList = printer.findFile("")
        #readline.set_completer(self.complete)
        #readline.parse_and_bind('tab: complete')

    def pause(self):
        self.player.pause()

    def play(self):
        self.player.play()

    def stop(self):
        self.player.stop()

    def printMusicList(self):
        if self.musicList == []: print("\033[91mAucun fichier trouvé")
        for music in self.musicList:
            print("\033[94m" + music)

    def complete(self, text, state):
        if state == 0:  # on first trigger, build possible matches
            if text:  # cache matches (entries that start with entered text)
                self.matches = [s for s in self.musicList
                                if s and s.startswith(text)]
            else:  # no text entered, all matches possible
                self.matches = self.musicList[:]

        # return match indexed by state
        try:
            return self.matches[state]
        except IndexError:
            return None

with Ice.initialize() as communicator:
    base = communicator.stringToProxy("SimplePrinter:default -p 10001")
    printer = Demo2.PrinterPrx.checkedCast(base)

    if not printer:
        raise RuntimeError("Invalid proxy")

    clientPlayer = ClientPlayer()
    print("Entrez help pour lister toutes les commandes")

    # Loop waiting for commands of the list

    while True:
        command = input("\033[92mVeuillez entrer une commande :\n")
        if command == "play":
            name = input("\033[92mQuelle musique ? Taper '*' pour lister toutes les musiques\n")
            while name == "*":
                clientPlayer.musicList = printer.findFile(name)
                clientPlayer.printMusicList()
                name = input("\033[92mQuelle musique ? Taper '*' pour lister toutes les musiques\n")
            result = printer.playFile(name.lower())
            if result == True:
                waintMsg = 0
                while not printer.isPlaying():
                    if waintMsg == 0:
                        print("En attente du serveur ...")
                        waintMsg += 1
                clientPlayer.play()
            else:
                print("\033[91mFichier introuvable vous pouvez chercher une musique avec la commande 'find'")

        elif command == "artist":
            name = input("\033[92mQuelle artiste ?\n")
            result = printer.playFileFromArtiste(name.lower())
            if result == True:
                waintMsg = 0
                while not printer.isPlaying():
                    if waintMsg == 0:
                        print("En attente du serveur ...")
                        waintMsg += 1
                clientPlayer.play()
            else:
                print("\033[91mFichier introuvable vous pouvez chercher une musique avec la commande 'find'")

        elif command == "resume":
            clientPlayer.play()

        elif command == "pause":
            clientPlayer.pause()

        elif command == "stop":
            clientPlayer.stop()
            printer.stopFile()

        elif command == "find":
            name = input("\033[92mEntrer le nom d'une musique:\n")
            clientPlayer.musicList = printer.findFile(name)
            clientPlayer.printMusicList()

        elif command == "rename":
            oldName = input("\033[92mSaisissez l'id de la musique à renommer:\n")
            newName = input("\033[92mSaisissez son nouveau nom:\n")
            result = printer.renameFile(oldName, newName)
            if result == True:
                print("\033[92mFichier renommé avec succès")
            else:
                print("\033[91mFichier introuvable")
            clientPlayer.musicList = printer.findFile("")

        elif command == "delete":
            print("\033[94mListe des musiques et couverture d'album détecté:")
            clientPlayer.musicList = printer.findFile("*")
            clientPlayer.printMusicList()
            name = input("\033[92mEntrer l'Id de la musique à supprimer:\n")
            fname = printer.getFullFileName(name)
            if len(fname) != 0:
                result = printer.deleteFile(fname)
            else:
                result = False
            if result == True:
                print("\033[92mFichier supprimé")
            else:
                print("\033[91mFichier introuvable")

        elif command == "upload":
            orig_dir = os.getcwd()
            os.chdir('toBeUploaded')
            print("\033[94mListe des musiques et couverture d'album détecté:")
            for fileListed in glob.glob("*"):
                print("\033[94m" + fileListed)

            filename = input("\033[92mVeuillez saisir la musique à uploader:\n")
            filename = filename + ".mp3"

            imgName = input("\033[92mVeuillez saisir la couverture à lier:\n")
            imgName = imgName + ".jpg"


            if os.path.exists(filename) != True:
                print("\033[91mMusique introuvable")
                os.chdir(orig_dir)
                continue

            if os.path.exists(imgName) != True:
                print("\033[91mCouverture introuvable")
                os.chdir(orig_dir)
                continue

            # Upload mp3
            file = open(filename, "rb")
            fileSize = os.stat(filename).st_size
            quotient, remainder = divmod(fileSize, 102400)  # 100kB max = 102400 Bytes

            id = printer.getNewIndex()

            for i in range(quotient):
                part = file.read(102400)
                printer.uploadPart(id, part)

            part = file.read(remainder)
            printer.uploadPart(id, part)

            file.close()

            printer.uploadFile(id, filename)
            print("\033[92mMusique correctement téléchargé")

            # Upload jpg
            file = open(imgName, "rb")
            fileSize = os.stat(imgName).st_size
            quotient, remainder = divmod(fileSize, 102400)  # 100kB max = 102400 Bytes

            id = printer.getNewIndex()

            for i in range(quotient):
                part = file.read(102400)
                printer.uploadPart(id, part)

            part = file.read(remainder)
            printer.uploadPart(id, part)

            file.close()

            printer.uploadFile(id, imgName)
            print("\033[92mCouverture correctement téléchargé")

            os.chdir(orig_dir)

        elif command == "help":
            print("""\033[94m
        play    # Joue une musique à sélectionner
        artist  # Joue une musique aléatoire d'un artiste
        resume  # Reprend le stream
        pause   # Met en pause le stream
        stop    # Arrête le stream
        find    # Trouve toutes les musiques contenant la chaine spécifié
        rename  # Renomme une musique
        delete  # Supprime une musique
        upload  # Ajoutez vos propres musiques
        help    # Affiche un menu d'aide pour les commandes du client
        quit    # Quitte l'application
            """)


        elif command == "quit":
            print("\033[91mFermeture de l'application... A bientot !")
            quit()

        else:
            print("\033[91mCommande inconnue")