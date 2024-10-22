import sys
print("\n".join(sys.path))

from maya import cmds
import pyblish.util
import quadpype

print("starting QuadPype usersetup for testing")
cmds.evalDeferred("pyblish.util.publish()")

cmds.evalDeferred("cmds.quit(force=True)")
cmds.evalDeferred("cmds.quit")
print("finished QuadPype usersetup  for testing")
