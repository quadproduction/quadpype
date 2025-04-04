# Test for backward compatibility of restructure of lib.py into lib library
# Contains simple imports that should still work


def test_backward_compatibility(printer):
    printer("Test if imports still work")
    try:
        from quadpype.lib import execute_hook
        from quadpype.lib import PypeHook

        from quadpype.lib import ApplicationLaunchFailed

        from quadpype.lib import get_ffmpeg_tool_path
        from quadpype.lib import get_last_version_from_path
        from quadpype.lib import get_paths_from_environ
        from quadpype.lib import get_version_from_path
        from quadpype.lib import version_up

        from quadpype.lib import get_ffprobe_streams

        from quadpype.lib import source_hash
        from quadpype.lib import run_subprocess

    except ImportError as e:
        raise
