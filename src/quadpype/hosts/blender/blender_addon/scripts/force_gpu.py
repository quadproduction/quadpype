import bpy

bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'

#calling get_devices() first will populate the devices list
#otherwise the script might find it empty, even when compatible devices are present
bpy.context.preferences.addons['cycles'].preferences.get_devices()
bpy.context.preferences.addons['cycles'].preferences.devices[0].use= True

bpy.context.scene.cycles.device = 'GPU'

bpy.ops.wm.save_userpref()
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
