import os, shutil
import glob
import signal
import sys
import time
import Ice
import IceStorm
import getopt
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests

MONGODB_URI = ""

client = MongoClient(MONGODB_URI)
db = client['Music']  # Remplacez 'db_name' par le nom de votre base de données
musique_collection = db['content']  # Remplacez 'musique' par le nom de votre collection

UPLOAD_FOLDER = 'uploads2'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

Ice.loadSlice('Publisheur.ice')
import Notifier

class musiqueLocal():
    def __init__(self, identifiant, fileName):
        self.id = str(identifiant)
        self.fileName = fileName


def getLocalData():
    arr = []
    orig_dir = os.getcwd()
    # Check in the musics directory
    os.chdir('uploads2')
    for file in glob.glob("*.mp3"):
        strFile = file.split('_')
        if len(strFile) > 0:
            arr.append(musiqueLocal(strFile[0], strFile[1]))
    os.chdir(orig_dir)
    return arr

def usage():
    print("Usage: " + sys.argv[0] + " [--datagram|--twoway|--oneway] [topic]")


def run(communicator):
    initialState = musique_collection.find({})
    initialStateId = []
    initialStateDocument = []
    initialStateDocument = getLocalData()
    for index, document in enumerate(initialState):
        initialStateId.append(document.get('_id'))
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['datagram', 'twoway', 'oneway'])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    datagram = False
    twoway = False
    optsSet = 0
    topicName = "time"
    for o, a in opts:
        if o == "--datagram":
            datagram = True
            optsSet = optsSet + 1
        elif o == "--twoway":
            twoway = True
            optsSet = optsSet + 1
        elif o == "--oneway":
            optsSet = optsSet + 1

    if optsSet > 1:
        usage()
        sys.exit(1)

    if len(args) > 0:
        topicName = args[0]

    manager = IceStorm.TopicManagerPrx.checkedCast(communicator.propertyToProxy('TopicManager.Proxy'))
    if not manager:
        print(args[0] + ": invalid proxy")
        sys.exit(1)

    #
    # Retrieve the topic.
    #
    try:
        topic = manager.retrieve(topicName)
    except IceStorm.NoSuchTopic:
        try:
            topic = manager.create(topicName)
        except IceStorm.TopicExists:
            print(sys.argv[0] + ": temporary error. try again")
            sys.exit(1)

    #
    # Get the topic's publisher object, and create a Clock proxy with
    # the mode specified as an argument of this application.
    #
    publisher = topic.getPublisher()
    if datagram:
        publisher = publisher.ice_datagram()
    elif twoway:
        # Do nothing.
        pass
    else:  # if(oneway)
        publisher = publisher.ice_oneway()
    clock = Notifier.RequestPrx.uncheckedCast(publisher)

    print("publishing tick events. Press ^C to terminate the application.")
    try:
        while 1:
            time.sleep(20)
            newState = musique_collection.find({})
            newStateId = []
            renamedFilesId = ""
            oldNames = ""
            newNames = ""

            for document in newState:
                for localData in getLocalData():
                    isEqual = document.get('name') == localData.fileName
                    if str(document.get('_id')) == localData.id and document.get('name') != localData.fileName:
                        print("Doc name = " + document.get('name') + " | " + localData.fileName)
                        renamedFilesId += str(document.get('_id')) + ","
                        oldNames += localData.fileName + ","
                        newNames += document.get('name') + ","
                        #clock.renameFile(str(document.get('_id')), localData.fileName, document.get('name'))
                        print("Nom de fichier modifié pour " + str(document.get('_id')))
                newStateId.append(str(document.get('_id')))

            if len(renamedFilesId) > 0:
                renamedFilesId = renamedFilesId[:-1]
                oldNames = oldNames[:-1]
                newNames = newNames[:-1]
                clock.renameFile(renamedFilesId, oldNames, newNames)

            idSet = set([])
            for localId in getLocalData():
                idSet.add(localId.id)
            if len(newStateId) < len(idSet):
                diff = list(set(idSet) - set(newStateId))
                strResult = ''
                for value in diff:
                    strResult += value
                    strResult += ','
                strResult = strResult[:-1]
                strResult = "Delete|" + strResult
                print(strResult)
                clock.newFile(strResult)

            if len(newStateId) > len(idSet):
                diff = list(set(newStateId) - set(idSet))
                strResult = ''
                for value in diff:
                    strResult += value
                    strResult += ','
                strResult = strResult[:-1]
                strResult = "Download|" + strResult
                print(strResult)
                clock.newFile(strResult)

            initialStateDocument = getLocalData()
            initialStateId = newStateId
            print('loop done')

            # clock.newFile(time.strftime("%m/%d/%Y %H:%M:%S"))
    except IOError:
        # Ignore
        pass
    except Ice.CommunicatorDestroyedException:
        # Ignore
        pass


#
# Ice.initialize returns an initialized Ice communicator,
# the communicator is destroyed once it goes out of scope.
#
with Ice.initialize(sys.argv, 'config.pub') as communicator:
    signal.signal(signal.SIGINT, lambda signum, frame: communicator.destroy())
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, lambda signum, frame: communicator.destroy())
    status = run(communicator)