#!/usr/bin/env python3

from __future__ import absolute_import
from System import *
from System.Diagnostics import *
from System.IO import *

from Deadline.Plugins import DeadlinePlugin, PluginType
from Deadline.Scripting import RepositoryUtils, SystemUtils, FileUtils, StringUtils

import sys

def GetDeadlinePlugin():
    return BlenderScriptPlugin()

def CleanupDeadlinePlugin( deadlinePlugin ):
    deadlinePlugin.Cleanup()

class BlenderScriptPlugin(DeadlinePlugin):
    def __init__(self):
        if sys.version_info.major == 3:
            super().__init__()
        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument

    def Cleanup(self):
        for stdoutHandler in self.StdoutHandlers:
            del stdoutHandler.HandleCallback

        del self.InitializeProcessCallback
        del self.RenderExecutableCallback
        del self.RenderArgumentCallback

    def InitializeProcess(self):
        #Std out handlers
        self.AddStdoutHandlerCallback(".*Saved:.*").HandleCallback += self.HandleStdoutSaved
        #self.AddStdoutHandlerCallback(".*Error.*").HandleCallback += self.HandleStdoutError
        self.AddStdoutHandlerCallback("Unable to open.*").HandleCallback += self.HandleStdoutFailed
        self.AddStdoutHandlerCallback("Failed to read blend file.*").HandleCallback += self.HandleStdoutFailed

    def RenderExecutable(self):
        ### Get Version ##
        blVersion = self.GetPluginInfoEntryWithDefault("Version", "").lower()

        try:
            return self.GetRenderExecutable("Blender_%s_RenderExecutable" % (blVersion), "Blender")
        except:
            return self.GetRenderExecutable("Blender_RenderExecutable", "Blender")

    def ScriptsFolder(self):
        return self.GetConfigEntry("Blender_ScriptsFolder")

    def RenderArgument(self):
        sceneFile = self.GetPluginInfoEntryWithDefault( "SceneFile", self.GetDataFilename() )
        sceneFile = RepositoryUtils.CheckPathMapping( sceneFile )
        if SystemUtils.IsRunningOnWindows():
            sceneFile = sceneFile.replace( "/", "\\" )
            if sceneFile.startswith( "\\" ) and not sceneFile.startswith( "\\\\" ):
                sceneFile = "\\" + sceneFile
        else:
            sceneFile = sceneFile.replace( "\\", "/" )

        Scripts = " -b \"" + sceneFile + "\""

        scriptName = self.GetPluginInfoEntryWithDefault( "ScriptName", None )
        if scriptName:
            scriptPath = f"{scriptName}.py" if not scriptName.endswith('.py') else scriptName
            scriptsFolder = self.ScriptsFolder()
            if not scriptsFolder:
                self.FailRender(
                    "scriptsFolder is empty. Python script can not be added to job. "
                    "Please fill Scripts Folder data from corresponding Plugin Info."
                )
            scriptsFolder = self.ConvertPathsForSystem(
                self.AddSlashesIfMissing(scriptsFolder)
            )
            Scripts += f" -P {scriptsFolder}{scriptPath}"

        ScriptArguments = self.GetPluginInfoEntryWithDefault("ScriptArguments", None)
        if ScriptArguments:
            Scripts += " -- " + ScriptArguments

        return Scripts

    def AddSlashesIfMissing(self, path):
        return path if (path.endswith('/') or path.endswith('\\')) else f"{path}/"

    def ConvertPathsForSystem(self, path):
        return path.replace('/', '\\') if SystemUtils.IsRunningOnWindows() else path.replace('\\', '/')

    def PreScriptTasks(self):
        self.LogInfo( "Blender job starting..." )

    def PostScriptTasks(self):
        self.LogInfo( "Blender job finished." )

    def HandleStdoutSaved(self):
        self.SetStatusMessage( "Task complete." )
    def HandleStdoutError(self):
        self.FailRender( self.GetRegexMatch(0) )

    def HandleStdoutFailed(self):
        self.FailRender( self.GetRegexMatch(0) )
