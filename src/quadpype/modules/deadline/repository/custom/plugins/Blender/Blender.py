#!/usr/bin/env python3

from __future__ import absolute_import
from System import *
from System.Diagnostics import *
from System.IO import *

from Deadline.Plugins import DeadlinePlugin, PluginType
from Deadline.Scripting import RepositoryUtils, SystemUtils, FileUtils, StringUtils

import sys

def GetDeadlinePlugin():
    return BlenderPlugin()

def CleanupDeadlinePlugin( deadlinePlugin ):
    deadlinePlugin.Cleanup()

class BlenderPlugin(DeadlinePlugin):
    frameCount = 0
    finishedFrameCount = 0

    def __init__(self):
        if sys.version_info.major == 3:
            super().__init__()
        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument
        self.PreRenderTasksCallback += self.PreRenderTasks
        self.PostRenderTasksCallback += self.PostRenderTasks

    def Cleanup(self):
        for stdoutHandler in self.StdoutHandlers:
            del stdoutHandler.HandleCallback

        del self.InitializeProcessCallback
        del self.RenderExecutableCallback
        del self.RenderArgumentCallback
        del self.PreRenderTasksCallback
        del self.PostRenderTasksCallback

    def InitializeProcess(self):
        self.SingleFramesOnly = False
        self.StdoutHandling = True

        #Std out handlers
        self.AddStdoutHandlerCallback(".*Tile ([0-9]+)/([0-9]+).*").HandleCallback += self.HandleTileProgress
        self.AddStdoutHandlerCallback(".*Sample ([0-9]+)/([0-9]+).*").HandleCallback += self.HandleSampleProgress
        self.AddStdoutHandlerCallback(".*Scene, Part ([0-9]+)-([0-9]+).*").HandleCallback += self.HandleSceneProgress
        self.AddStdoutHandlerCallback(".*Saved:.*").HandleCallback += self.HandleStdoutSaved
        #self.AddStdoutHandlerCallback(".*Error.*").HandleCallback += self.HandleStdoutError
        self.AddStdoutHandlerCallback("Unable to open.*").HandleCallback += self.HandleStdoutFailed
        self.AddStdoutHandlerCallback("Failed to read blend file.*").HandleCallback += self.HandleStdoutFailed
        self.AddStdoutHandlerCallback(".*Unable to create directory.*").HandleCallback += self.HandleStdoutFailed

    def RenderExecutable(self):
        ### Get Version ##
        blVersion = self.GetPluginInfoEntryWithDefault( "Version", "" ).lower()

        try:
            return self.GetRenderExecutable( "Blender_%s_RenderExecutable" % ( blVersion ), "Blender")
        except:
            return self.GetRenderExecutable( "Blender_RenderExecutable", "Blender")

    def RenderArgument(self):
        sceneFile = self.GetPluginInfoEntryWithDefault( "SceneFile", self.GetDataFilename() )
        sceneFile = RepositoryUtils.CheckPathMapping( sceneFile )
        if SystemUtils.IsRunningOnWindows():
            sceneFile = sceneFile.replace( "/", "\\" )
            if sceneFile.startswith( "\\" ) and not sceneFile.startswith( "\\\\" ):
                sceneFile = "\\" + sceneFile
        else:
            sceneFile = sceneFile.replace( "\\", "/" )

        renderArgument = " -b \"" + sceneFile + "\""
        renderArgument += " -t " + self.GetPluginInfoEntryWithDefault( "Threads", "0" )

        outputFile = self.GetPluginInfoEntryWithDefault( "OutputFile", "" )
        outputFile = RepositoryUtils.CheckPathMapping( outputFile )
        if SystemUtils.IsRunningOnWindows():
            outputFile = outputFile.replace( "/", "\\" )
            if outputFile.startswith( "\\" ) and not outputFile.startswith( "\\\\" ):
                outputFile = "\\" + outputFile
        else:
            outputFile = outputFile.replace( "\\", "/" )

        renderArgument += StringUtils.BlankIfEitherIsBlank( " -x 1 -o \"", StringUtils.BlankIfEitherIsBlank( outputFile, "\"" ) )
        renderArgument += " -s " + str(self.GetStartFrame()) + " -e " + str(self.GetEndFrame()) + " -a "

        return renderArgument

    def PreRenderTasks(self):
        self.LogInfo( "Blender job starting..." )

        # Plugin specific values for progress
        self.totalFrames = self.GetEndFrame() - self.GetStartFrame() + 1
        self.finishedFrames = 0
        self.totalChunks = 0
        self.currentChunk = 0
        self.chunkType = ""

        self.UpdateProgress()

    def PostRenderTasks(self):
        self.LogInfo( "Blender job finished." )

    def UpdateProgress(self):
        progress = self.finishedFrames

        # If we know the chunk type, we should have set its progress as well
        if self.chunkType != "":
            progress += (self.currentChunk / float(self.totalChunks))
            message = "Rendering %(ct)s %(cc)s/%(tt)s of frame %(ff)s/%(tf)s for this task"
        else:
            message = "Rendering frame %(ff)s/%(tf)s for this task"

        self.SetStatusMessage( message % {
            "ct": self.chunkType,
            "ff": str(self.finishedFrames + 1),
            "tf": str(self.totalFrames),
            "cc": str(self.currentChunk),
            "tt": str(self.totalChunks) })

        progress = progress / float( self.totalFrames )
        self.SetProgress( progress * 100 )

        if self.GetBooleanPluginInfoEntryWithDefault( "SupressOutput", True ):
            self.SuppressThisLine()

    def HandleStdoutSaved(self):
        self.finishedFrames += 1
        self.currentChunk = 0 # Avoid incorrect progress math after addtion

        self.UpdateProgress()

        if self.finishedFrames + 1 > self.totalFrames:
            # This avoids us showing a status message of "rendering frame 2/1"
            self.SetStatusMessage( "Task complete." )

    def HandleTileProgress(self):
        ''' Find tile progress for Cycle's tile render '''
        self.currentChunk = int( self.GetRegexMatch(1) )
        self.totalChunks  = int( self.GetRegexMatch(2) )
        self.chunkType = "tile"
        self.UpdateProgress()

    def HandleSampleProgress(self):
        ''' Find sample progress for Cycle's progressive render '''
        # Samples are reported in order, so let's be awesome
        self.currentChunk = int( self.GetRegexMatch(1) )
        self.totalChunks  = int( self.GetRegexMatch(2) )
        self.chunkType = "sample"
        self.UpdateProgress()

    def HandleSceneProgress(self):
        ''' Find sub-frame progress for the Blender Internal renderer '''
        # We hit problems with things like motion blur and sub-surf sampling
        # when reporting progress since lists progress multiple times without
        # always telling us how many loops there would be.

        # Tiles aren't reported in order, so let's track it ourselves
        # self.currentChunk += 1
        # self.totalChunks  = int( self.GetRegexMatch(2) )
        # self.chunkType = "chunk"
        self.UpdateProgress()

    def HandleStdoutError(self):
        self.FailRender( self.GetRegexMatch(0) )

    def HandleStdoutFailed(self):
        self.FailRender( self.GetRegexMatch(0) )
