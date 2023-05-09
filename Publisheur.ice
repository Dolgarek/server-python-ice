#pragma once

module Notifier
{
    interface Request
    {
        void newFile(string time);
        void renameFile(string id, string oldName, string fileName);
    }
}