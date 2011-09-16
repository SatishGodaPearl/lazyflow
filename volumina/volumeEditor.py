import copy

from PyQt4.QtCore import Qt, pyqtSignal, QObject
from PyQt4.QtGui import QApplication, QWidget, QBrush, QPen, QColor, QTransform

from eventswitch import EventSwitch
from imageScene2D import ImageScene2D
from imageView2D import ImageView2D
from positionModel import PositionModel
from navigationControler import NavigationControler, NavigationInterpreter
from brushingcontroler import BrushingInterpreter, BrushingControler
from brushingmodel import BrushingModel
from pixelpipeline.imagepump import ImagePump
from slicingtools import SliceProjection

useVTK = True
try:
    from view3d.view3d import OverviewScene
except:
    import traceback
    traceback.print_exc()
    useVTK = False

#*******************************************************************************
# V o l u m e E d i t o r                                                      *
#*******************************************************************************

class VolumeEditor( QObject ):
    zoomInFactor  = 1.1
    zoomOutFactor = 0.9

    def __init__( self, shape, layerStackModel, labelsink=None):
        super(VolumeEditor, self).__init__()
        assert(len(shape) == 5)
        self._shape = shape
        
        self._showDebugPatches = False
        self.layerStack = layerStackModel

        # three ortho image pumps
        alongTXC = SliceProjection( abscissa = 2, ordinate = 3, along = [0,1,4] )
        alongTYC = SliceProjection( abscissa = 1, ordinate = 3, along = [0,2,4] )
        alongTZC = SliceProjection( abscissa = 1, ordinate = 2, along = [0,3,4] )

        imagepumps = []
        imagepumps.append(ImagePump( layerStackModel, alongTXC ))
        imagepumps.append(ImagePump( layerStackModel, alongTYC ))
        imagepumps.append(ImagePump( layerStackModel, alongTZC ))

        # synced slicesource collections
        syncedSliceSources = []
        for i in xrange(3):
            syncedSliceSources.append(imagepumps[i].syncedSliceSources)

        # three ortho image scenes
        self.imageScenes = []
        self.imageScenes.append(ImageScene2D())
        self.imageScenes.append(ImageScene2D())
        self.imageScenes.append(ImageScene2D())
        names = ['x', 'y', 'z']
        for scene, name, pump in zip(self.imageScenes, names, imagepumps):
            scene.setObjectName(name)
            scene.stackedImageSources = pump.stackedImageSources

        # three ortho image views
        self.imageViews = []
        self.imageViews.append(ImageView2D(self.imageScenes[0]))
        self.imageViews.append(ImageView2D(self.imageScenes[1]))
        self.imageViews.append(ImageView2D(self.imageScenes[2]))
        
        self.imageViews[0].setTransform(QTransform(1,0,0,0,1,0,0,0,1))
        self.imageViews[1].setTransform(QTransform(0,1,1,0,0,0))
        self.imageViews[2].setTransform(QTransform(0,1,1,0,0,0))

        if useVTK:
            self.view3d = OverviewScene(shape=self._shape[1:4])
            def onSliceDragged(num, pos):
                newPos = copy.deepcopy(self.posModel.slicingPos)
                newPos[pos] = num
                self.posModel.slicingPos = newPos
                
            self.view3d.changedSlice.connect(onSliceDragged)
        else:
            self.view3d = QWidget()

        # navigation control
        self.posModel     = PositionModel(self._shape)
        v3d = None
        if useVTK:
            v3d = self.view3d
        self.navCtrl      = NavigationControler(self.imageViews, syncedSliceSources, self.posModel, view3d=v3d)
        self.navInterpret = NavigationInterpreter(self.posModel, self.imageViews)

        # eventswitch
        self.es = EventSwitch(self.imageViews)
        self.es.interpreter = self.navInterpret
        
        # brushing control
        self.brushingModel = BrushingModel()
        #self.crosshairControler = CrosshairControler() 
        self.brushingInterpreter = BrushingInterpreter(self.brushingModel, self.imageViews)
        self.brushingControler = BrushingControler(self.brushingModel, self.posModel, labelsink)
        
        def onBrushSize(s):
            b = QPen(QBrush(self.brushingModel.drawColor), s)
            #b = QPen(QBrush(QColor(0,255,0)), 15) #for testing
            for s in self.imageScenes:
                s.setBrush(b)
        def onBrushColor(c):
            b = QPen(QBrush(c), self.brushingModel.brushSize)
            #b = QPen(QBrush(QColor(0,255,0)), 15) #for testing
            for s in self.imageScenes:
                s.setBrush(b)
        
        self.brushingModel.brushSizeChanged.connect(onBrushSize)
        self.brushingModel.brushColorChanged.connect(onBrushColor)
        
        self._initConnects()

    @property
    def showDebugPatches(self):
        return self._showDebugPatches
    @showDebugPatches.setter
    def showDebugPatches(self, show):
        for s in self.imageScenes:
            s.showDebugPatches = show
        self._showDebugPatches = show

    def scheduleSlicesRedraw(self):
        for s in self.imageScenes:
            s._invalidateRect()

    def _initConnects(self):
        for i, v in enumerate(self.imageViews):
            #connect interpreter
            v.sliceShape = self.posModel.sliceShape(axis=i)
            
        #connect controler
        self.posModel.channelChanged.connect(self.navCtrl.changeChannel)
        self.posModel.timeChanged.connect(self.navCtrl.changeTime)
        self.posModel.slicingPositionChanged.connect(self.navCtrl.moveSlicingPosition)
        self.posModel.cursorPositionChanged.connect(self.navCtrl.moveCrosshair)
        self.posModel.slicingPositionSettled.connect(self.navCtrl.settleSlicingPosition)

    def setDrawingEnabled(self, enabled): 
        for i in range(3):
            self.imageViews[i].drawingEnabled = enabled
        
    def cleanUp(self):
        QApplication.processEvents()
        print "VolumeEditor: cleaning up "
        for scene in self._imageViews:
            scene.close()
            scene.deleteLater()
        self._imageViews = []
        QApplication.processEvents()
        print "finished saving thread"
    
    def closeEvent(self, event):
        event.accept()

    def nextChannel(self):
        assert(False)
        self.posModel.channel = self.posModel.channel+1

    def previousChannel(self):
        assert(False)
        self.posModel.channel = self.posModel.channel-1
