bl_info = {
    "name": "Render Catalogue",
    "version": (1, 0),
    "description": "Display render slots in a catalogue.",
    "blender": (4, 1, 1),
    "category": "Render",
}

import bpy
import os
import bpy.utils.previews
import time
from bpy_extras.view3d_utils import location_3d_to_region_2d

# Set addon path
addonPath = os.path.join(os.path.dirname(__file__), "")

# Global variables
rendering = None
loadingThumb = None
modalCompete= None
RrImageSize = (0,0)
switchIconPath = os.path.join(addonPath, r"render_catalogue\icon\switch.png")
RrFilePath = os.path.join(addonPath, "render_catalogue/renderResult.blend")
RrImage = "RC Render Result"
thumbnailDir = os.path.join(bpy.app.tempdir, "thumbnail/")
thumbName = "thumbRenderCat_"
missingRenderThumbName= "maybeNoRenderImage_"
failedRenderThumbName= "noRenderImage_"
thumbSize = 128
thumbExt = ".jpg"
BG_SlotIndex = ''
scrshotName = "RenderCatScreenshot_"
handlers = bpy.app.handlers
addon_keymaps = []


def sceneInit():
    """Initialize scene and setup keymaps."""
    renderResult = is_RR_image()

    if renderResult is not None:
        if renderResult == False:
            for img in bpy.data.images:
                if img.type == 'RENDER_RESULT' and img.name != RrImage:
                    bpy.data.images.remove(img)
            importRrImageRef(RrFilePath, RrImage)
            setImageEditorContext(bpy.data.images[RrImage])
        else:
            clearCat(thumbName)
    else:
        importRrImageRef(RrFilePath, RrImage)
        setImageEditorContext(bpy.data.images[RrImage])


def getRrImageSize():
    resPercentage = bpy.context.scene.render.resolution_percentage
    res = bpy.context.scene.render
    RrImageSize = (int(res.resolution_x * (resPercentage / 100)), int(res.resolution_y * (resPercentage / 100)))
    return RrImageSize


def loadThumb():
    """Load thumbnail images as icons for UI display."""
    global loadingThumb
    iconsThumb.clear()
    renderSlots = is_RR_image()
    if renderSlots and renderSlots != False:
        renderSlots = renderSlots.render_slots
        for slot in renderSlots:
            if slot.name != thumbName + "0" and os.path.isdir(thumbnailDir):
                thumbFile = slot.name
                thumbnailPath= os.path.join(thumbnailDir, thumbFile + thumbExt)

                if not os.path.isfile(thumbnailPath):
                    thumbFile = f"{missingRenderThumbName}{slot.name.split('_')[-1]}"
                iconsThumb.load(thumbFile, thumbnailPath, 'IMAGE')
    loadingThumb = False


def is_RR_image():
    """Check if Render Result image exists."""
    for img in bpy.data.images:
        if img.type == 'RENDER_RESULT':
            return img if img.name == RrImage else False
    return None


def setImageEditorContext(img):
    """Set the image editor context to the specified image."""
    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = img
            return area

    return None

def saveRender(renderResult,thumbnailPath):
    """Save the render result to a file."""
    scene = bpy.context.scene
    render_settings = scene.render.image_settings
    original_format = render_settings.file_format
    original_colorDepth = render_settings.color_depth
    render_settings.file_format = 'JPEG'

    try:
        renderResult.save_render(thumbnailPath, scene=bpy.context.scene, quality=0) #bpy.ops.image.save_as(filepath=thumbnailPath, save_as_render= False, copy= True)
        render_settings.file_format= original_format
        render_settings.color_depth= original_colorDepth
        return True

    except Exception as e:
        #print(f"Render catalogue error saving image: {e}")
        #print(f"(probably missing render)")
        render_settings.file_format= original_format
        render_settings.color_depth= original_colorDepth
        return False


def createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize):
    """Create and save a thumbnail from render result."""
    global loadingThumb
    renderResult = is_RR_image()

    if not renderResult:
        loadingThumb = False
        return

    slotIndex = renderResult.render_slots.active.name.split('_')[1]
    thumbnailPath = os.path.join(thumbnailDir, f"{thumbName}{slotIndex}{thumbExt}")

    if not os.path.isfile(thumbnailPath) and saveRender(renderResult, thumbnailPath):
        bpy.ops.image.open(filepath=thumbnailPath)
        imgThumb = bpy.data.images.get(os.path.basename(thumbnailPath))

        if imgThumb.size[1] != 0 and imgThumb.size[0]!= 0:
            thumbnailHeight = int(thumbSize * imgThumb.size[1] / imgThumb.size[0])
            imgThumb.scale(thumbSize, thumbnailHeight)
            imgThumb.save(filepath=thumbnailPath, quality=0)

        if imgThumb.users > 0:
            imgThumb.user_clear()
        bpy.data.images.remove(imgThumb, do_unlink=True)
        setImageEditorContext(renderResult)
        return True
    else:
        loadingThumb = False
        return False


def addRenderSlot(thumbnailDir, thumbName, empty=None):
    """Add a new render slot."""
    global rendering, loadingThumb, modalCompete
    renderResult = is_RR_image()
    if renderResult is None:
        importRrImageRef(RrFilePath, RrImage)
        renderResult = is_RR_image()

    if renderResult == False:
        for img in bpy.data.images:
            if img.type == 'RENDER_RESULT' and img.name != RrImage:
                if img.users > 0:
                    img.user_clear()
                bpy.data.images.remove(img)
        importRrImageRef(RrFilePath, RrImage)
        renderResult = bpy.data.images[RrImage]

    if renderResult:
        area= setImageEditorContext(renderResult)

        #get new slot name and index
        slotIndex = "1"
        if len(renderResult.render_slots) > 1:
            slotNameList = []
            for i in range(0, len(renderResult.render_slots)):
                slotName = renderResult.render_slots[i].name
                slotNameList.append(int(slotName.split('_')[1]))
            slotIndex = str(max(slotNameList) + 1)

        name = f"SS{thumbName}{slotIndex}" if empty else f"{thumbName}{slotIndex}"
        newSlot = renderResult.render_slots.new(name=name)
        renderResult.render_slots.active = newSlot
        if empty is None:
            try:
                bpy.ops.render.render("INVOKE_DEFAULT")
            except Exception as e:
                print(f"Error saving new image: {e}")
                rendering = None
                loadingThumb = None
                modalCompete= None
                if setImageEditorContext(renderResult):
                    deleteCurrentSlot()

        else:
            return renderResult


def crop_image(orig_img, cropped_min_x, cropped_max_x, cropped_min_y, cropped_max_y):
    """Crop an image to specified dimensions."""
    num_channels = orig_img.channels
    orig_size_x = orig_img.size[0]
    orig_size_y = orig_img.size[1]

    cropped_min_x = max(0, cropped_min_x)
    cropped_max_x = min(orig_size_x, cropped_max_x)
    cropped_min_y = max(0, cropped_min_y)
    cropped_max_y = min(orig_size_y - 26, cropped_max_y)

    cropped_size_x = cropped_max_x - cropped_min_x
    cropped_size_y = cropped_max_y - cropped_min_y

    cropped_img = bpy.data.images.new(name="cropped_img", width=cropped_size_x, height=cropped_size_y)

    print("Exctracting image fragment, this could take a while...")
    # loop through each row of the cropped image grabbing the appropriate pixels from original
    # the reason for the strange limits is because of the
    # order that Blender puts pixels into a 1-D array.
    current_cropped_row = 0
    for yy in range(cropped_min_y, cropped_max_y):
        orig_start = (cropped_min_x + yy * orig_size_x) * num_channels
        orig_end = orig_start + (cropped_size_x * num_channels)
        cropped_start = (current_cropped_row * cropped_size_x) * num_channels
        cropped_end = cropped_start + (cropped_size_x * num_channels)

        cropped_img.pixels[cropped_start:cropped_end] = orig_img.pixels[orig_start:orig_end]
        current_cropped_row += 1

    return cropped_img


def getCamBorder(region, rv3d):
    """Get camera border coordinates in pixel space."""
    scene = bpy.context.scene
    cam = scene.camera
    camData = cam.data

    frame = camData.view_frame(scene=scene)
    frame = [cam.matrix_world @ v for v in frame]
    # Kept as original per request
    frame_px = [location_3d_to_region_2d(region, rv3d, v) for v in frame]
    return frame_px


def setScreenshotUI(overlays=None, gizmo=None, region_ui=None, toolbar=None):
    """Set UI state for screenshot."""
    spaceData = bpy.context.space_data

    overlays = spaceData.overlay.show_overlays
    gizmo = spaceData.show_gizmo
    region_ui = spaceData.show_region_ui
    toolbar = spaceData.show_region_toolbar

    spaceData.overlay.show_overlays = False
    spaceData.show_gizmo = False
    if region_ui:
        spaceData.show_region_ui = False
    if toolbar:
        spaceData.show_region_toolbar = False

    return overlays, gizmo, region_ui, toolbar


def reSetScreenshotUI(overlays=True, gizmo=None, region_ui=None, toolbar=None):
    """Reset UI state after screenshot."""
    spaceData = bpy.context.space_data
    spaceData.overlay.show_overlays = overlays
    spaceData.show_gizmo = gizmo
    if region_ui:
        spaceData.show_region_ui = True
    if toolbar:
        spaceData.show_region_toolbar = True


def takeScreenshot(thumbnailDir, scrshotName, thumbExt, area):
    """Take a screenshot and process it."""
    #global RrImageSize
    RrImageSize= getRrImageSize()
    renderResult = addRenderSlot(thumbnailDir, thumbName, empty=True)
    slotIndex = renderResult.render_slots.active.name.split('_')[1]
    scrshotPath = os.path.join(thumbnailDir, f"{scrshotName}{slotIndex}{thumbExt}")

    bpy.ops.screen.screenshot_area(filepath=scrshotPath)

    scrshot = bpy.data.images.load(scrshotPath)
    scrshot.pack()
    scrshot.filepath = ""

    viewPoint = area.spaces[0].region_3d.view_perspective
    if viewPoint == 'CAMERA':
        for region in area.regions:
            if region.type == 'WINDOW':
                frame_px = getCamBorder(region, area.spaces[0].region_3d)
                cropped_min_x = round(frame_px[3][0])
                cropped_max_x = round(frame_px[0][0])
                cropped_min_y = round(frame_px[2][1])
                cropped_max_y = round(frame_px[0][1])

                cropedImg = crop_image(scrshot, cropped_min_x, cropped_max_x, cropped_min_y, cropped_max_y)
                cropedImg.scale(RrImageSize[0], RrImageSize[1])
                cropedImg.save(filepath=scrshotPath)
                bpy.data.images.remove(cropedImg)
                scrshot.reload()
                break

    return scrshot


def createScrshotThumbnail(scrshotImg, thumbnailDir, thumbName, thumbExt):
    """Create thumbnail from screenshot image."""
    slotIndex = scrshotImg.name.split('_')[1].split('.')[0]
    thumbnailPath = os.path.join(thumbnailDir, f"SS{thumbName}{slotIndex}{thumbExt}")

    thumbnailHeight = int(thumbSize * scrshotImg.size[1] / scrshotImg.size[0])
    scrshotImg.scale(thumbSize, thumbnailHeight)
    scrshotImg.save(filepath=thumbnailPath, quality=0)

def deleteCurrentSlot(thumbnailDir= None):
    """Delete the current render slot."""
    renderResult = is_RR_image()
    area = setImageEditorContext(renderResult)
    if renderResult and renderResult != False and bpy.context.area == area:
        nextSlot = renderResult.render_slots.active_index - 1
        currentSlotName = renderResult.render_slots.active.name

        if currentSlotName != thumbName + "0":
            bpy.ops.image.remove_render_slot()
            print(currentSlotName)
            print(scrshotName in currentSlotName)
            if 'SS' in currentSlotName:
                bpy.data.images.remove(bpy.data.images[f"{scrshotName}{currentSlotName.split('_')[-1]}{thumbExt}"])
        else:
            bpy.ops.image.clear_render_slot()
            print("Can't delete thumbRv_0. | in tools.py --> deleteCurrentSlot()")

        if thumbnailDir != None:
            thumbnailPath = os.path.join(thumbnailDir, f"{currentSlotName}{thumbExt}")
            if os.path.exists(thumbnailPath):
                os.remove(thumbnailPath)

        for i, Rslot in enumerate(renderResult.render_slots):
            if i == nextSlot:
                renderResult.render_slots.active = Rslot
                break


def clearCat(thumbName):
    """Clear all thumbnails in category."""
    renderResult = is_RR_image()
    area = setImageEditorContext(renderResult)

    if renderResult and renderResult != False and area:
        if os.path.isdir(thumbnailDir):
            for file in os.listdir(thumbnailDir):
                os.remove(os.path.join(thumbnailDir, file))

        if renderResult.users > 1:
            renderResult.user_clear()
        bpy.data.images.remove(renderResult)

        for img in bpy.data.images.values():
            if scrshotName in img.name:
                bpy.data.images.remove(img)

        importRrImageRef(RrFilePath, RrImage)
        setImageEditorContext(bpy.data.images[RrImage])


def importRrImageRef(RrFilePath, RrImage):
    """Import Render Result image from reference scene."""
    with bpy.data.libraries.load(RrFilePath) as (data_from, data_to):
        if RrImage in data_from.images:
            data_to.images = [RrImage]

    for lib in bpy.data.libraries:
        if lib.name == 'renderResult.blend':
            bpy.data.libraries.remove(lib)


def setRenderSlotActive(slotName):
    """Set specified render slot as active."""
    renderResult = is_RR_image()
    slots = renderResult.render_slots
    area = setImageEditorContext(renderResult)

    for i in range(0, len(slots)):
        slots.active_index = i
        if slots.active.name == slotName:
            break

    if 'SS' in slotName:
        imgName = f"{scrshotName}{slotName.split('_')[1]}{thumbExt}"
        img = bpy.data.images[imgName]
        for area in bpy.context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = img


# Setup icon collections
iconsThumb = bpy.utils.previews.new()
customIcon = bpy.utils.previews.new()
customIcon.load("switch", switchIconPath, 'IMAGE')


# Timer for scene initialization
bpy.app.timers.register(sceneInit, first_interval=0.5)


class AddRenderSlot(bpy.types.Operator):
    """Create and add a render slot with rendering."""
    bl_idname = "render.add_render_slot"
    bl_label = "Rcat Render"

    _timer = None

    def pre(self, scene, context=None):
        global rendering
        rendering = True

    def post(self, scene, context=None):
        global rendering
        rendering = False

    def execute(self, context):
        global rendering, loadingThumb, modalCompete
        if rendering in (False, None) and modalCompete in (True, None):
            modalCompete= False
            rendering = True
            loadingThumb = True
            bpy.app.handlers.render_pre.append(self.pre)
            bpy.app.handlers.render_post.append(self.post)
            self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
            context.window_manager.modal_handler_add(self)
            addRenderSlot(thumbnailDir, thumbName)
            return {'RUNNING_MODAL'}
        else:
            return {'FINISHED'}

    def modal(self, context, event):
        global loadingThumb, modalCompete
        if event.type == 'TIMER' and rendering is False:
            modalCompete= True
            if self._timer is not None:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize)
            loadThumb()
            self.finish()

            return {'FINISHED'}
        return {'PASS_THROUGH'}

    def finish(self):
        global loadingThumb
        # Safely remove handlers when operator finishes
        loadingThumb= False
        try:
            bpy.app.handlers.render_pre.remove(self.pre)
        except ValueError:
            pass  # Handler already removed
        try:
            bpy.app.handlers.render_post.remove(self.post)
        except ValueError:
            pass  # Handler already removed

    def cancel(self, context):
        # Clean up on cancel
        global loadingThumb, modalCompete
        loadingThumb= False
        modalCompete= True
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
        self.finish()


class AddViewportSlot(bpy.types.Operator):
    """Add a screenshot from the viewport to the catalogue."""
    bl_idname = "render.add_viewport_slot"
    bl_label = "Rcat Add Viewport Slot"

    _timer = None
    start_time = 0.0
    running = None
    UI_status = []

    def executeUI(self, context):
        global rendering
        if rendering in (False, None): #and loadingThumb != True:
            area = bpy.context.area
            if area.type == 'VIEW_3D':
                if self.running is None:
                    self.running = True
                    self.UI_status = setScreenshotUI()
                    self.start_time = time.time()
                elif self.running == False:
                    return {'FINISHED'}
                else:
                    return {'RUNNING_MODAL'}
        return {'FINISHED'}

    def modal(self, context, event):
        self.executeUI(context)
        elapsed_time = time.time() - self.start_time

        if elapsed_time > 0.1:
            self.running = False
            if rendering in (False, None):
                area = bpy.context.area
                if area.type == 'VIEW_3D':
                    scrshotImg = takeScreenshot(thumbnailDir, scrshotName, thumbExt, area)
                    reSetScreenshotUI(*self.UI_status)
                    createScrshotThumbnail(scrshotImg, thumbnailDir, thumbName, thumbExt)
                    scrshotImg.reload()
                    setImageEditorContext(scrshotImg)
                    loadThumb()
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class DeleteRenderSlot(bpy.types.Operator):
    """Delete the current render slot."""
    bl_idname = "render.delete_render_slot"
    bl_label = "Rcat Delete Render Slot"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        global loadingThumb
        if loadingThumb != True:
            deleteCurrentSlot(thumbnailDir)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class ClearCatalogue(bpy.types.Operator):
    """Clear all catalogue entries."""
    bl_idname = "render.clear_catalogue"
    bl_label = "Rcat Clear Render Catalogue"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        global loadingThumb
        if loadingThumb != True:
            clearCat(thumbName)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class SwitchView(bpy.types.Operator):
    """Switch between render slots."""
    bl_idname = "render.switch_view"
    bl_label = "Rcat Switch Render Slot"

    def execute(self, context):
        global BG_SlotIndex, rendering, loadingThumb
        renderResult = is_RR_image()
        if renderResult and renderResult != False:
            activeSlotIndex = renderResult.render_slots.active.name
            setRenderSlotActive(BG_SlotIndex)
            if rendering in (False, None) and loadingThumb in (False, None) and not 'SS' in BG_SlotIndex:
                if createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize):
                    loadThumb()
            BG_SlotIndex = activeSlotIndex
        return {'FINISHED'}


class CycleUp(bpy.types.Operator):
    """Cycle up through render slots."""
    bl_idname = "render.cycle_up"
    bl_label = "Rcat Cycle Render Slot Up"

    def execute(self, context):
        global rendering, loadingThumb
        renderResult = is_RR_image()
        if renderResult and renderResult != False and len(renderResult.render_slots) > 1:
            currentSlotName = renderResult.render_slots.active.name

            if currentSlotName in (False, "thumbRenderCat_0"):
                if renderResult.render_slots[-1]:
                    currentSlotName= renderResult.render_slots[-1].name

            for i in range(1, len(renderResult.render_slots)):
                slotName = renderResult.render_slots[i].name
                if slotName == currentSlotName:
                    newIndex = 1 if i == len(renderResult.render_slots) - 1 else i + 1
                    renderResult.render_slots.active_index = newIndex
                    newSlotName = renderResult.render_slots.active.name

                    if 'SS' in newSlotName:
                        setRenderSlotActive(newSlotName)
                    else:
                        setImageEditorContext(renderResult)
                        if rendering in (False, None) and loadingThumb in (False, None):
                            if createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize):
                                 loadThumb()
                    break
        return {'FINISHED'}


class CycleDown(bpy.types.Operator):
    """Cycle down through render slots."""
    bl_idname = "render.cycle_down"
    bl_label = "Rcat Cycle Render Slot Down"

    def execute(self, context):
        global rendering, loadingThumb
        renderResult = is_RR_image()
        if renderResult and renderResult != False and len(renderResult.render_slots) > 1:
            currentSlotName = renderResult.render_slots.active.name

            if currentSlotName in (False, "thumbRenderCat_0"):
                if renderResult.render_slots[1]:
                    currentSlotName= renderResult.render_slots[1].name

            for i in range(1, len(renderResult.render_slots)):
                slotName = renderResult.render_slots[i].name
                if slotName == currentSlotName:
                    newIndex = len(renderResult.render_slots) if i == 1 else i - 1
                    renderResult.render_slots.active_index = newIndex
                    newSlotName = renderResult.render_slots.active.name

                    if 'SS' in newSlotName:
                        setRenderSlotActive(newSlotName)
                    else:
                        setImageEditorContext(renderResult)
                        if rendering in (False, None) and loadingThumb in (False, None):
                            if createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize):
                                loadThumb()
                    break
        return {'FINISHED'}


class SetSlotView(bpy.types.Operator):
    """Set the view to a specific slot."""
    bl_idname = "render.set_slot_view"
    bl_label = "Rcat Set Slot View"

    buttonName: bpy.props.StringProperty()
    last_click_time = 0.0
    click = 0

    def execute_setView_FG(self, context):
        global rendering, loadingThumb
        setRenderSlotActive(self.buttonName)
        if rendering == False and loadingThumb == False and 'SS' not in self.buttonName :
            if createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize):
                loadThumb()
        return {'FINISHED'}

    def execute_setView_BG(self, context):
        global BG_SlotIndex
        BG_SlotIndex = self.buttonName
        return {'FINISHED'}

    def modal(self, context, event):
        if self.click == 0:
            self.last_click_time = time.time()
            self.click += 1

        elapsed_time = time.time() - self.last_click_time
        if elapsed_time < 0.15 and event.type == 'LEFTMOUSE' and self.click == 1:
            self.execute_setView_BG(context)
            return {'FINISHED'}
        elif elapsed_time >= 0.15:
            self.execute_setView_FG(context)
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class ReloadThumbnail(bpy.types.Operator):
    """Empty operator for UI purposes. used in key map panel to display the buutton correctly."""
    bl_idname = "render.reload_thumbnail"
    bl_label = "Rcat Reload Thumbnail"

    def execute(self, context):
        global rendering, loadingThumb
        if rendering in (False, None) and loadingThumb in (False, None):
            renderResult = is_RR_image()
            if renderResult and renderResult != False and len(renderResult.render_slots) > 1:
                renderSlots = renderResult.render_slots
                currentSlotName = renderSlots.active.name
                for i, Rslot in enumerate(reversed(renderSlots)):
                    if not 'SS' in Rslot.name and Rslot.name != 'thumbRenderCat_0':
                        setRenderSlotActive(Rslot.name)
                        if createThumbnail(thumbnailDir, thumbName, thumbExt, thumbSize):
                            loadThumb()

                setRenderSlotActive(currentSlotName)

        return {'FINISHED'}


class EmptyOp(bpy.types.Operator):
    """Empty operator for UI purposes. used in key map panel to display the buutton correctly."""
    bl_idname = "render.empty_op"
    bl_label = "Rcat Empty Op"

    def execute(self, context):

        return {'FINISHED'}


class LayoutRenderCatalogue:
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Render Catalogue'


class LayoutRenderCataloguePanel(LayoutRenderCatalogue, bpy.types.Panel):
    """Main Render Catalogue panel."""
    bl_label = "Render Catalogue"
    bl_idname = "IMAGE_EDITOR_PT_RenderCatalogue"

    def draw(self, context):
        self.layout


class RC_PT_PanelButton(LayoutRenderCatalogue, bpy.types.Panel):
    """Buttons sub-panel."""
    bl_label = "Buttons"
    bl_parent_id = "IMAGE_EDITOR_PT_RenderCatalogue"
    bl_options = {"DEFAULT_CLOSED"}


    def draw(self, context):
        layout = self.layout
        split = layout.split()

        col = split.column(align=True)
        col.operator("render.add_render_slot", text='', icon="ADD")
        col.operator("render.delete_render_slot", text='', icon="REMOVE")
        col.operator("render.clear_catalogue", text='', icon="X")
        col.scale_y = 1.0

        col = split.column(align=True)
        #switchIcon = customIcon["switch"]
        col.operator("render.switch_view", text='', icon="UV_SYNC_SELECT")
        col.scale_y = 3.0

        col = split.column(align=True)
        col.operator("render.cycle_up", text='', icon="SORT_DESC")
        col.operator("render.cycle_down", text='', icon="SORT_ASC")
        col.scale_y = 1.5

        col= layout.column(align=True)
        col.operator("render.reload_thumbnail", text='', icon="IMAGE_RGB")
        col.scale_y = 1.5


class RC_PT_DocPanel(LayoutRenderCatalogue, bpy.types.Panel):
    """Documentation sub-panel."""
    bl_parent_id = "RC_PT_PanelButton"
    bl_label = "Key map:"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        #switchIcon = customIcon["switch"]
        layout = self.layout
        slot = layout.column()
        scaleX = (context.region.width) / 135

        col = slot.row(align=True)
        col.label(text='Buttons:')

        mappings = [
            ('F12', "ADD", 'Render.'),
            ('CTRL+F12', "NONE", 'Take a screenshot when over the 3D viewport. '),
            ('Del', "REMOVE", 'Delete current slot.'),
            ('Ctrl+Del', "X", 'Clear render catalogue.'),
            ('S', 'UV_SYNC_SELECT', 'Switch between forward/backward slot.'),
            ('Page up', "SORT_DESC", 'Cycle up through slot.'),
            ('Page down', "SORT_ASC", 'Cycle down through slot.'),
            ('F5', "IMAGE_RGB", 'Reload all thumbnail of the catalogue.')

        ]

        for key, icon, text in mappings:
            col = slot.row(align=True)
            emptyspace= f'<{str(16-len(key))}'
            col.label(text=f'{key: {emptyspace}} =>')
            col.scale_x = scaleX
            if isinstance(icon, int):
                col.label(icon_value=icon, text=text)
            else:
                col.label(icon=icon, text=text)

        col = slot.row(align=True)
        col.label(text='')
        col.scale_y = 0.25

        col = slot.row(align=True)
        col.label(text='In the catalogue:')

        col = slot.row(align=True)
        col.label(icon="MOUSE_LMB", text='            => ')
        col.scale_x = scaleX / 6.25
        col = col.row(align=True)
        col.operator("render.empty_op", text='', icon='HIDE_OFF', emboss=True, depress=True)
        col.scale_x = 1.9
        col.label(text='  Set forward.')

        col = slot.row(align=True)
        col.label(icon="MOUSE_LMB_DRAG", text='            => ')
        col.scale_x = scaleX / 6.25
        col = col.row(align=True)
        col.operator("render.empty_op", text='', icon='HIDE_OFF', emboss=False, depress=False)
        col.scale_x = 1.9
        col.label(text='  Set backward.')


class RC_PT_PanelThumb(LayoutRenderCatalogue, bpy.types.Panel):
    """Thumbnail catalogue sub-panel."""
    bl_label = "Catalogue"
    bl_parent_id = "IMAGE_EDITOR_PT_RenderCatalogue"

    def draw(self, context):
        layout = self.layout
        renderResult = is_RR_image()

        if renderResult and renderResult != False:
            renderSlots = renderResult.render_slots
            activeSlotIndex = int(renderResult.render_slots.active.name.split('_')[-1])
            lastSlot = renderSlots[-1].name

            box = layout.box()
            for i, Rslot in enumerate(reversed(renderSlots)):
                if Rslot.name != thumbName + "0":
                    row = box.row(align=True)
                    slot = row.box()
                    col = slot.row(align=True)

                    icon = 'HIDE_OFF' if int(
                        Rslot.name.split('_')[-1]) == activeSlotIndex or Rslot.name == BG_SlotIndex else 'HIDE_ON'
                    emboss = True if int(
                        Rslot.name.split('_')[-1]) == activeSlotIndex or Rslot.name == BG_SlotIndex else False
                    depress = True if int(Rslot.name.split('_')[-1]) == activeSlotIndex else False

                    scaleY = (3 * context.region.width) / 152
                    scaleX = (context.region.width) / 152
                    if context.region.width < 100:
                        scaleY, scaleX = 2, 10

                    col.operator("render.set_slot_view", text='', icon=icon, emboss=emboss,
                                 depress=depress).buttonName = Rslot.name
                    col.scale_y = scaleY
                    col.scale_x = scaleX

                    if len(iconsThumb) > 0:
                        if not Rslot.name in iconsThumb:
                            iconKey= "None"
                        else:
                            iconKey= Rslot.name
                        thumbIcon = 168 if loadingThumb and Rslot.name == lastSlot else iconsThumb[iconKey].icon_id if iconKey in iconsThumb else 257 #.....168 if loadingThumb and Rslot.name == lastSlot else iconsThumb[iconKey].icon_id if iconKey in iconsThumb else 257 if iconKey == "False" else 1 #...... 168 if loadingThumb and Rslot.name == lastSlot else (iconsThumb[iconKey].icon_id if thumbName in iconKey else (257 if iconKey == "None" else 1))
                        col.template_icon(icon_value=thumbIcon)


def register():
    """Register all classes and initialize addon with keymaps."""
    bpy.utils.register_class(AddRenderSlot)
    bpy.utils.register_class(AddViewportSlot)
    bpy.utils.register_class(DeleteRenderSlot)
    bpy.utils.register_class(ClearCatalogue)
    bpy.utils.register_class(SwitchView)
    bpy.utils.register_class(CycleUp)
    bpy.utils.register_class(CycleDown)
    bpy.utils.register_class(SetSlotView)
    bpy.utils.register_class(ReloadThumbnail)
    bpy.utils.register_class(EmptyOp)
    bpy.utils.register_class(LayoutRenderCataloguePanel)
    bpy.utils.register_class(RC_PT_PanelButton)
    bpy.utils.register_class(RC_PT_DocPanel)
    bpy.utils.register_class(RC_PT_PanelThumb)

    # Define and set keymaps
    kmi_defs = (
        (DeleteRenderSlot.bl_idname, 'DEL', 'PRESS', False, False, False),
        (ClearCatalogue.bl_idname, 'DEL', 'PRESS', True, False, False),
        (SwitchView.bl_idname, 'S', 'PRESS', False, False, False),
        (CycleUp.bl_idname, 'PAGE_UP', 'PRESS', False, False, False),
        (CycleDown.bl_idname, 'PAGE_DOWN', 'PRESS', False, False, False),
        (ReloadThumbnail.bl_idname, 'F5', 'PRESS', False, False, False),
    )

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    # Modify default F12 keymap
    wm.keyconfigs.default.keymaps['Screen'].keymap_items["render.render"].ctrl = True
    wm.keyconfigs.default.keymaps['Screen'].keymap_items["render.render"].shift = True

    # Modify animation render keymap
    for item in wm.keyconfigs.default.keymaps['Screen'].keymap_items:
        if item.name == 'Render' and item.properties.animation:
            item.alt = True
            item.shift = True

    # Addon keymaps
    if kc:
        km = kc.keymaps.new(name='Image Generic', space_type="IMAGE_EDITOR")
        for identifier, key, action, ctrl, shift, alt in kmi_defs:
            kmi = km.keymap_items.new(identifier, key, action, ctrl=ctrl, shift=shift, alt=alt)
            addon_keymaps.append((km, kmi))

        # Override F12 keys
        km = kc.keymaps.new(name='Screen', space_type="EMPTY")
        kmi = km.keymap_items.new(AddRenderSlot.bl_idname, 'F12', 'PRESS')
        addon_keymaps.append((km, kmi))

        km = kc.keymaps.new(name='Screen', space_type="EMPTY")
        kmi = km.keymap_items.new(AddViewportSlot.bl_idname, 'F12', 'PRESS', ctrl=True)
        addon_keymaps.append((km, kmi))


def unregister():
    """Unregister all classes and clean up."""
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    wm = bpy.context.window_manager
    wm.keyconfigs.default.keymaps['Screen'].keymap_items["render.render"].ctrl = False
    wm.keyconfigs.default.keymaps['Screen'].keymap_items["render.render"].shift = False
    for item in wm.keyconfigs.default.keymaps['Screen'].keymap_items:
        if item.name == 'Render' and item.properties.animation:
            item.alt = False
            item.shift = False

    bpy.utils.unregister_class(AddRenderSlot)
    bpy.utils.unregister_class(AddViewportSlot)
    bpy.utils.unregister_class(DeleteRenderSlot)
    bpy.utils.unregister_class(ClearCatalogue)
    bpy.utils.unregister_class(SwitchView)
    bpy.utils.unregister_class(CycleUp)
    bpy.utils.unregister_class(CycleDown)
    bpy.utils.unregister_class(SetSlotView)
    bpy.utils.unregister_class(ReloadThumbnail)
    bpy.utils.unregister_class(EmptyOp)
    bpy.utils.unregister_class(LayoutRenderCataloguePanel)
    bpy.utils.unregister_class(RC_PT_PanelButton)
    bpy.utils.unregister_class(RC_PT_DocPanel)
    bpy.utils.unregister_class(RC_PT_PanelThumb)

    clearCat(thumbName)
    iconsThumb.clear()
    customIcon.clear()
    bpy.utils.previews.remove(iconsThumb)
    bpy.utils.previews.remove(customIcon)

if __name__ == "__main__":
    register()
