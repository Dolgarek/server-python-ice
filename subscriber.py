import os, shutil
import signal
import sys
import Ice
import IceStorm
import getopt
from pymongo import MongoClient
import requests
from bson.objectid import ObjectId

MONGODB_URI = ""

client = MongoClient(MONGODB_URI)
db = client['Music']  # Remplacez 'db_name' par le nom de votre base de données
musique_collection = db['content']  # Remplacez 'musique' par le nom de votre collection

UPLOAD_FOLDER = 'uploads2'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def download_file(url, local_path):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def get_musiques():
    folder = UPLOAD_FOLDER
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
    musiques = list(musique_collection.find({}))
    for musique in musiques:
        musique['_id'] = str(musique['_id'])  # Convertir l'ID en chaîne de caractères
        pochette_url = musique['pochette_url']
        pochette_path = os.path.join(UPLOAD_FOLDER, f"{musique['_id']}_pochette.jpg")
        son_path = os.path.join(UPLOAD_FOLDER, f"{musique['_id']}_{musique['name']}")

        # Télécharger la pochette si elle n'existe pas déjà
        if not os.path.exists(pochette_path):
            try:
                download_file(pochette_url, pochette_path)
            except Exception as e:
                return str(e)

        if not os.path.exists(son_path):
            try:
                download_file(musique['son_url'], son_path)
            except Exception as e:
                return str(e)

        # Lier l'URL locale de la pochette à la musique
        musique['pochette_url'] = pochette_url
        musique['pochette_path'] = pochette_path
        musique['son_path'] = son_path
        print(musique)


Ice.loadSlice('Publisheur.ice')
import Notifier


class ClockI(Notifier.Request):
    def newFile(self, date, current):
        get_musiques()
        print(date)

    def renameFile(self, fileId, oldName, newName, current):
        print('helloWorld')
        # print(fileId, newName)
        i = 0
        splitId = fileId.split(',')
        splitOld = oldName.split(',')
        splitNew = newName.split(',')
        while i < len(splitId):
            musique = musique_collection.find_one({"_id": ObjectId(splitId[i])})
            # print(musique)
            if musique:
                # print(musique)
                path = UPLOAD_FOLDER + "/" + str(musique.get('_id')) + "_" + splitOld[i]
                newPath = UPLOAD_FOLDER + "/" + str(musique.get('_id')) + "_" + splitNew[i]

            if os.path.exists(path):
                musique_collection.update_one({'_id': ObjectId(splitId[i])}, {"$set": {'name': splitNew[i]}})
                os.rename(path, newPath)
                print("Fichier " + path + " à été renommé en " + newPath)
            else:
                print("Le fichier " + path + " n'existe pas.")
            i += 1


def usage():
    print("Usage: " + sys.argv[0] +
          " [--batch] [--datagram|--twoway|--ordered|--oneway] [--retryCount count] [--id id] [topic]")


def run(communicator):
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['datagram', 'twoway', 'oneway', 'ordered', 'batch',
                                                      'retryCount=', 'id='])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    batch = False
    option = "None"
    topicName = "time"
    id = ""
    retryCount = ""

    for o, a in opts:
        oldoption = option
        if o == "--datagram":
            option = "Datagram"
        elif o == "--twoway":
            option = "Twoway"
        elif o == "--ordered":
            option = "Ordered"
        elif o == "--oneway":
            option = "Oneway"
        elif o == "--batch":
            batch = True
        elif o == "--id":
            id = a
        elif o == "--retryCount":
            retryCount = a
        if oldoption != option and oldoption != "None":
            usage()
            sys.exit(1)

    if len(args) > 1:
        usage()
        sys.exit(1)

    if len(args) > 0:
        topicName = args[0]

    if batch and (option in ("Twoway", "Ordered")):
        print(sys.argv[0] + ": batch can only be set with oneway or datagram")
        sys.exit(1)

    manager = IceStorm.TopicManagerPrx.checkedCast(communicator.propertyToProxy('TopicManager.Proxy'))
    if not manager:
        print(args[0] + ": invalid proxy")
        sys.exit(1)

    #
    # Retrieve the topic.
    #
    try:
        topic = manager.retrieve(topicName)
    except IceStorm.NoSuchTopic as e:
        try:
            topic = manager.create(topicName)
        except IceStorm.TopicExists as ex:
            print(sys.argv[0] + ": temporary error. try again")
            sys.exit(1)

    adapter = communicator.createObjectAdapter("Clock.Subscriber")

    #
    # Add a servant for the Ice object. If --id is used the identity
    # comes from the command line, otherwise a UUID is used.
    #
    # id is not directly altered since it is used below to detect
    # whether subscribeAndGetPublisher can raise AlreadySubscribed.
    #

    subId = Ice.Identity()
    subId.name = id
    if len(subId.name) == 0:
        subId.name = Ice.generateUUID()
    subscriber = adapter.add(ClockI(), subId)

    #
    # Activate the object adapter before subscribing.
    #
    adapter.activate()

    qos = {}
    if len(retryCount) > 0:
        qos["retryCount"] = retryCount

    #
    # Set up the proxy.
    #
    if option == "Datagram":
        if batch:
            subscriber = subscriber.ice_batchDatagram()
        else:
            subscriber = subscriber.ice_datagram()
    elif option == "Twoway":
        # Do nothing to the subscriber proxy. Its already twoway.
        pass
    elif option == "Ordered":
        # Do nothing to the subscriber proxy. Its already twoway.
        qos["reliability"] = "ordered"
    elif option == "Oneway" or option == "None":
        if batch:
            subscriber = subscriber.ice_batchOneway()
        else:
            subscriber = subscriber.ice_oneway()

    try:
        topic.subscribeAndGetPublisher(qos, subscriber)
    except IceStorm.AlreadySubscribed:
        # This should never occur when subscribing with an UUID
        assert (id)
        print("reactivating persistent subscriber")

    communicator.waitForShutdown()

    #
    # Unsubscribe all subscribed objects.
    #
    topic.unsubscribe(subscriber)


#
# Ice.initialize returns an initialized Ice communicator,
# the communicator is destroyed once it goes out of scope.
#
with Ice.initialize(sys.argv, "config.sub") as communicator:
    #
    # Install a signal handler to shutdown the communicator on Ctrl-C
    #
    signal.signal(signal.SIGINT, lambda signum, frame: communicator.shutdown())
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, lambda signum, frame: communicator.shutdown())
    status = run(communicator)
