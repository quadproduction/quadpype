from abc import ABC, abstractmethod
from quadpype.lib import Logger

log = Logger.get_logger("SyncServer")


class AbstractProvider(ABC):
    CODE = ''
    LABEL = ''

    _log = None

    def __init__(self, project_name, site_name, tree=None, presets=None):
        self.presets = None
        self.active = False
        self.site_name = site_name

        self.presets = presets

        super().__init__()

    @property
    def log(self):
        if self._log is None:
            self._log = Logger.get_logger(self.__class__.__name__)
        return self._log

    @abstractmethod
    def is_active(self):
        """
            Returns True if provider is activated, eg. has working credentials.
        Returns:
            (boolean)
        """

    @classmethod
    @abstractmethod
    def get_global_settings_schema(cls):
        """
            Returns dict for editable properties on global settings level


            Returns:
                (list) of dict
        """

    @classmethod
    @abstractmethod
    def get_project_settings_schema(cls):
        """
            Returns dict for editable properties on project settings level


            Returns:
                (list) of dict
        """

    @classmethod
    @abstractmethod
    def get_user_settings_schema(cls):
        """
            Returns dict for editable properties on user settings level


            Returns:
               (list) of dict
        """

    @abstractmethod
    def upload_file(self, source_path, path,
                    server, project_name, file, representation, site,
                    overwrite=False):
        """
            Copy file from 'source_path' to 'target_path' on provider.
            Use 'overwrite' boolean to rewrite existing file on provider

        Args:
            source_path (string):
            path (string): absolute path with or without name of the file
            overwrite (boolean): replace existing file

            arguments for saving progress:
            server (SyncServer): server instance to call update_db on
            project_name (str): name of project_name
            file (dict): info about uploaded file (matches structure from db)
            representation (dict): complete repre containing 'file'
            site (str): site name
        Returns:
            (string) file_id of created/modified file ,
                throws FileExistsError, FileNotFoundError exceptions
        """
        pass

    @abstractmethod
    def download_file(self, source_path, local_path,
                      server, project_name, file, representation, site,
                      overwrite=False):
        """
            Download file from provider into local system

        Args:
            source_path (string): absolute path on provider
            local_path (string): absolute path with or without name of the file
            overwrite (boolean): replace existing file

            arguments for saving progress:
            server (SyncServer): server instance to call update_db on
            project_name (str):
            file (dict): info about uploaded file (matches structure from db)
            representation (dict): complete repre containing 'file'
            site (str): site name
        Returns:
            (string) file_id of created/modified file ,
                throws FileExistsError, FileNotFoundError exceptions
        """
        pass

    @abstractmethod
    def delete_file(self, path):
        """
            Deletes file from 'path'. Expects path to specific file.

        Args:
            path (string): absolute path to particular file

        Returns:
            None
        """
        pass

    @abstractmethod
    def list_folder(self, folder_path):
        """
            List all files and subfolders of particular path non-recursively.
        Args:
            folder_path (string): absolut path on provider

        Returns:
            (list)
        """
        pass

    @abstractmethod
    def create_folder(self, folder_path):
        """
            Create all nonexistent folders and subfolders in 'path'.

        Args:
            path (string): absolute path

        Returns:
            (string) folder id of lowest subfolder from 'path'
        """
        pass

    @abstractmethod
    def get_tree(self):
        """
            Creates folder structure for providers which do not provide
            tree folder structure (GDrive has no accessible tree structure,
            only parents and their parents)
        """
        pass

    @abstractmethod
    def get_roots_config(self, anatomy=None):
        """
            Returns root values for path resolving

            Takes value from Anatomy which takes values from Settings
            overridden by the User Settings

        Returns:
            (dict) - {"root": {"root": "/My Drive"}}
                     OR
                     {"root": {"root_ONE": "value", "root_TWO":"value}}
            Format is importing for usage of python's format ** approach
        """
        pass

    def resolve_path(self, path, root_config=None, anatomy=None):
        """
            Replaces all root placeholders with proper values

            Args:
                path(string): root[work]/folder...
                root_config (dict): {'work': "c:/..."...}
                anatomy (Anatomy): object of Anatomy
            Returns:
                (string): proper url
        """
        if not root_config:
            root_config = self.get_roots_config(anatomy)

        if root_config and not root_config.get("root"):
            root_config = {"root": root_config}

        try:
            if not root_config:
                raise KeyError

            path = path.format(**root_config)
        except KeyError:
            try:
                path = anatomy.fill_root(path)
            except KeyError:
                msg = "Error in resolving local root from anatomy"
                self.log.error(msg)
                raise ValueError(msg)
        except IndexError:
            msg = "Path {} contains unfillable placeholder"
            self.log.error(msg)
            raise ValueError(msg)

        return path
