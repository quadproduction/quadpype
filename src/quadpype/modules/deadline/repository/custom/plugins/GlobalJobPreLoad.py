# /usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import tempfile
from datetime import datetime, timezone
import subprocess
import json
import platform
import uuid
import re

from Deadline.Scripting import (
    RepositoryUtils,
    FileUtils,
    DirectoryUtils
)

VERSION_REGEX = re.compile(
    r"(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[a-zA-Z\d\-.]*))?"
    r"(?:\+(?P<buildmetadata>[a-zA-Z\d\-.]*))?"
)


class PackageVersion:
    """Fake semver version class for QuadPype version purposes.

    The version
    """
    def __init__(self, major, minor, patch, prerelease, origin=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease

        is_valid = True
        if major is None or minor is None or patch is None:
            is_valid = False
        self.is_valid = is_valid

        if origin is None:
            base = "{}.{}.{}".format(str(major), str(minor), str(patch))
            if not prerelease:
                origin = base
            else:
                origin = "{}-{}".format(base, str(prerelease))

        self.origin = origin

    @classmethod
    def from_string(cls, version):
        """Create an object of version from string.

        Args:
            version (str): Version as a string.

        Returns:
            Union[PackageVersion, None]: Version object if input is nonempty
                string otherwise None.
        """

        if not version:
            return None
        valid_parts = VERSION_REGEX.findall(version)
        if len(valid_parts) != 1:
            # Return invalid version with filled 'origin' attribute
            return cls(None, None, None, None, origin=str(version))

        # Unpack found version
        major, minor, patch, pre, post = valid_parts[0]
        prerelease = pre
        # Post release is not important anymore and should be considered as
        #   part of prerelease
        # - comparison is implemented to find suitable build and builds should
        #       never contain prerelease part so "not proper" parsing is
        #       acceptable for this use case.
        if post:
            prerelease = "{}+{}".format(pre, post)

        return cls(
            int(major), int(minor), int(patch), prerelease, origin=version
        )

    def has_compatible_release(self, other):
        """Version has compatible release as other version.

        Both major and minor versions must be exactly the same. In that case
        a build can be considered as release compatible with any version.

        Args:
            other (PackageVersion): Other version.

        Returns:
            bool: Version is release compatible with other version.
        """

        if self.is_valid and other.is_valid:
            return self.major == other.major and self.minor == other.minor
        return False

    def __bool__(self):
        return self.is_valid

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.origin)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return self.origin == other
        return self.origin == other.origin

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            return None

        if not self.is_valid:
            return True

        if not other.is_valid:
            return False

        if self.origin == other.origin:
            return None

        same_major = self.major == other.major
        if not same_major:
            return self.major < other.major

        same_minor = self.minor == other.minor
        if not same_minor:
            return self.minor < other.minor

        same_patch = self.patch == other.patch
        if not same_patch:
            return self.patch < other.patch

        if not self.prerelease:
            return False

        if not other.prerelease:
            return True

        pres = [self.prerelease, other.prerelease]
        pres.sort()
        return pres[0] == self.prerelease


def get_quadpype_version_from_path(path, build=True):
    """Get QuadPype version from provided path.
         path (str): Path to scan.
         build (bool, optional): Get only builds, not sources

    Returns:
        Union[PackageVersion, None]: version of QuadPype if found.
    """

    # fix path for application bundle on macos
    if platform.system().lower() == "darwin":
        path = os.path.join(path, "MacOS")

    version_file = os.path.join(path, "quadpype", "version.py")
    if not os.path.isfile(version_file):
        return None

    # skip if the version is not build
    exe = os.path.join(path, "quadpype_console.exe")
    if platform.system().lower() in ["linux", "darwin"]:
        exe = os.path.join(path, "quadpype_console")

    # if only builds are requested
    if build and not os.path.isfile(exe):  # noqa: E501
        print("   ! path is not a build: {}".format(path))
        return None

    version = {}
    with open(version_file, "r") as vf:
        exec(vf.read(), version)

    version_str = version.get("__version__")
    if version_str:
        return PackageVersion.from_string(version_str)
    return None


def get_quadpype_executable():
    """Return QuadPype Executable from Event Plug-in Settings"""
    config = RepositoryUtils.GetPluginConfig("QuadPype")
    exe_list = config.GetConfigEntryWithDefault("QuadPypeExecutable", "")
    dir_list = config.GetConfigEntryWithDefault(
        "QuadPypeInstallationDirs", "")

    # clean '\ ' for MacOS pasting
    if platform.system().lower() == "darwin":
        exe_list = exe_list.replace("\\ ", " ")
        dir_list = dir_list.replace("\\ ", " ")
    return exe_list, dir_list


def get_quadpype_versions(dir_list):
    print(">>> Getting QuadPype executable ...")
    quadpype_versions = []

    # special case of multiple install dirs
    for dir_list in dir_list.split(","):
        install_dir = DirectoryUtils.SearchDirectoryList(dir_list)
        if install_dir:
            print("--- Looking for QuadPype at: {}".format(install_dir))
            sub_dirs = [
                f.path for f in os.scandir(install_dir)
                if f.is_dir()
            ]
            for subdir in sub_dirs:
                version = get_quadpype_version_from_path(subdir)
                if not version:
                    continue
                print("  - found: {} - {}".format(version, subdir))
                quadpype_versions.append((version, subdir))
    return quadpype_versions


def get_requested_quadpype_executable(
    exe, dir_list, requested_version
):
    requested_version_obj = PackageVersion.from_string(requested_version)
    if not requested_version_obj:
        print((
            ">>> Requested version '{}' does not match version regex '{}'"
        ).format(requested_version, VERSION_REGEX))
        return None

    print((
        ">>> Scanning for compatible requested version {}"
    ).format(requested_version))
    quadpype_versions = get_quadpype_versions(dir_list)
    if not quadpype_versions:
        return None

    # if looking for requested compatible version,
    # add the implicitly specified to the list too.
    if exe:
        exe_dir = os.path.dirname(exe)
        print("Looking for QuadPype at: {}".format(exe_dir))
        version = get_quadpype_version_from_path(exe_dir)
        if version:
            print("  - found: {} - {}".format(version, exe_dir))
            quadpype_versions.append((version, exe_dir))

    matching_item = None
    compatible_versions = []
    for version_item in quadpype_versions:
        version, version_dir = version_item
        if requested_version_obj.has_compatible_release(version):
            compatible_versions.append(version_item)
            if version == requested_version_obj:
                # Store version item if version match exactly
                # - break if is found matching version
                matching_item = version_item
                break

    if not compatible_versions:
        return None

    compatible_versions.sort(key=lambda item: item[0])
    if matching_item:
        version, version_dir = matching_item
        print((
            "*** Found exact match build version {} in {}"
        ).format(version_dir, version))

    else:
        version, version_dir = compatible_versions[-1]

        print((
            "*** Latest compatible version found is {} in {}"
        ).format(version_dir, version))

    # create list of executables for different platform and let
    # Deadline decide.
    exe_list = [
        os.path.join(version_dir, "quadpype_console.exe"),
        os.path.join(version_dir, "quadpype_console"),
        os.path.join(version_dir, "MacOS", "quadpype_console")
    ]
    return FileUtils.SearchFileList(";".join(exe_list))


def inject_quadpype_environment(deadlinePlugin):
    """ Pull env vars from QuadPype and push them to rendering process.

        Used for correct paths, configuration from QuadPype etc.
    """
    job = deadlinePlugin.GetJob()

    print(">>> Injecting QuadPype environments ...")
    try:
        exe_list, dir_list = get_quadpype_executable()
        exe = FileUtils.SearchFileList(exe_list)

        requested_version = job.GetJobEnvironmentKeyValue("QUADPYPE_VERSION")
        if requested_version:
            exe = get_requested_quadpype_executable(
                exe, dir_list, requested_version
            )
            if exe is None:
                raise RuntimeError((
                    "Cannot find compatible version available for version {}"
                    " requested by the job. Please add it through plugin"
                    " configuration in Deadline or install it to configured"
                    " directory."
                ).format(requested_version))

        if not exe:
            raise RuntimeError((
                "QuadPype executable was not found in the semicolon "
                "separated list \"{}\"."
                "The path to the render executable can be configured"
                " from the Plugin Configuration in the Deadline Monitor."
            ).format(";".join(exe_list)))

        print("--- QuadPype executable: {}".format(exe))

        # tempfile.TemporaryFile cannot be used because of locking
        temp_file_name = "{}_{}.json".format(
            datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f'),
            str(uuid.uuid1())
        )
        export_url = os.path.join(tempfile.gettempdir(), temp_file_name)
        print(">>> Temporary path: {}".format(export_url))

        args = [
            "--headless",
            "extractenvironments",
            export_url
        ]

        add_kwargs = {
            "project": job.GetJobEnvironmentKeyValue("AVALON_PROJECT"),
            "asset": job.GetJobEnvironmentKeyValue("AVALON_ASSET"),
            "task": job.GetJobEnvironmentKeyValue("AVALON_TASK"),
            "app": job.GetJobEnvironmentKeyValue("AVALON_APP_NAME"),
            "envgroup": "farm"
        }

        if job.GetJobEnvironmentKeyValue('IS_TEST'):
            args.append("--automatic-tests")

        if all(add_kwargs.values()):
            for key, value in add_kwargs.items():
                args.extend(["--{}".format(key), value])
        else:
            raise RuntimeError((
                "Missing required env vars: AVALON_PROJECT, AVALON_ASSET,"
                " AVALON_TASK, AVALON_APP_NAME"
            ))

        quadpype_mongo = job.GetJobEnvironmentKeyValue("QUADPYPE_MONGO")
        if quadpype_mongo:
            # inject env var for QuadPype extractenvironments
            # SetEnvironmentVariable is important, not SetProcessEnv...
            deadlinePlugin.SetEnvironmentVariable("QUADPYPE_MONGO",
                                                  quadpype_mongo)

        if not os.getenv("QUADPYPE_MONGO"):
            print(">>> Missing QUADPYPE_MONGO env var, process won't work")

        os.environ["AVALON_TIMEOUT"] = "5000"

        args_str = subprocess.list2cmdline(args)
        print(">>> Executing: {} {}".format(exe, args_str))
        process_exitcode = deadlinePlugin.RunProcess(
            exe, args_str, os.path.dirname(exe), -1
        )

        if process_exitcode != 0:
            raise RuntimeError(
                "Failed to run QuadPype process to extract environments."
            )

        print(">>> Loading file ...")
        with open(export_url) as fp:
            contents = json.load(fp)

        for key, value in contents.items():
            deadlinePlugin.SetProcessEnvironmentVariable(key, value)

        if "PATH" in contents:
            # Set os.environ[PATH] so studio settings' path entries
            # can be used to define search path for executables.
            print(f">>> Setting 'PATH' Environment to: {contents['PATH']}")
            os.environ["PATH"] = contents["PATH"]

        script_url = job.GetJobPluginInfoKeyValue("ScriptFilename")
        if script_url:
            script_url = script_url.format(**contents).replace("\\", "/")
            print(">>> Setting script path {}".format(script_url))
            job.SetJobPluginInfoKeyValue("ScriptFilename", script_url)

        print(">>> Removing temporary file")
        os.remove(export_url)

        print(">> Injection end.")
    except Exception as e:
        if hasattr(e, "output"):
            print(">>> Exception {}".format(e.output))
        import traceback
        print(traceback.format_exc())
        print("!!! Injection failed.")
        RepositoryUtils.FailJob(job)
        raise


def inject_render_job_id(deadlinePlugin):
    """Inject dependency ids to publish process as env var for validation."""
    print(">>> Injecting render job id ...")
    job = deadlinePlugin.GetJob()

    dependency_ids = job.JobDependencyIDs
    print(">>> Dependency IDs: {}".format(dependency_ids))
    render_job_ids = ",".join(dependency_ids)

    deadlinePlugin.SetProcessEnvironmentVariable("RENDER_JOB_IDS",
                                                 render_job_ids)
    print(">>> Injection end.")


def __main__(deadlinePlugin):
    print("*** GlobalJobPreload start ...")
    print(">>> Getting job ...")
    job = deadlinePlugin.GetJob()

    quadpype_render_job = \
        job.GetJobEnvironmentKeyValue('QUADPYPE_RENDER_JOB') or '0'
    quadpype_publish_job = \
        job.GetJobEnvironmentKeyValue('QUADPYPE_PUBLISH_JOB') or '0'
    quadpype_remote_job = \
        job.GetJobEnvironmentKeyValue('QUADPYPE_REMOTE_PUBLISH') or '0'

    if quadpype_publish_job == '1' and quadpype_render_job == '1':
        raise RuntimeError("Misconfiguration. Job couldn't be both " +
                           "render and publish.")

    if quadpype_publish_job == '1':
        inject_render_job_id(deadlinePlugin)
    if quadpype_render_job == '1' or quadpype_remote_job == '1':
        inject_quadpype_environment(deadlinePlugin)
