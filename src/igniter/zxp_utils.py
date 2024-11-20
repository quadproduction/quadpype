import semver

class ZXPExtensionData:

    def __init__(self, host_id: str, ext_id: str, installed_version: semver.VersionInfo, shipped_version: semver.VersionInfo):
        self.host_id = host_id
        self.id = ext_id
        self.installed_version = installed_version
        self.shipped_version = shipped_version
