module Demo2
{
//    struct ListData
//    {
//        string nom;
//        string pochette;
//    }
//
//    sequence<ListData> musicList;

    sequence<string> strList;
    sequence<byte> byteSeq;
    interface Printer
    {
        void printString(string s);
        bool renameFile(string filename, string newName);
        bool deleteFile(string filename);
        int getNewIndex();
        strList findFile(string filename);
        string getFullFileName(string id);
        bool playFile(string filename);
        bool playFileFromArtiste(string artiste);
        bool playFileFromSongAndArtiste(string artiste, string son);
        void stopFile();
        void pause();
        void resume();
        bool uploadPart(int id, byteSeq part);
        bool uploadFile(int id, string filename);
        strList scanFolder();
        bool isPlaying();
    };
};