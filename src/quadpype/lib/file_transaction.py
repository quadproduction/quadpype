import os
import logging
import sys
import errno

from quadpype.lib import create_hardlink, create_symlink

# this is needed until speedcopy for linux is fixed
if sys.platform == "win32":
    from speedcopy import copyfile
else:
    from shutil import copyfile


class DuplicateDestinationError(ValueError):
    """Error raised when transfer destination already exists in queue.

    The error is only raised if `allow_queue_replacements` is False on the
    FileTransaction instance and the added file to transfer is of a different
    src file than the one already detected in the queue.

    """


class FileTransaction:
    """File transaction with rollback options.

    The file transaction is a three-step process.

    1) Rename any existing files to a "temporary backup" during `process()`
    2) Copy the files to final destination during `process()`
    3) Remove any backed up files (*no rollback possible!) during `finalize()`

    Step 3 is done during `finalize()`. If not called the .bak files will
    remain on disk.

    These steps try to ensure that we don't overwrite half of any existing
    files e.g. if they are currently in use.

    Note:
        A regular filesystem is *not* a transactional file system and even
        though this implementation tries to produce a 'safe copy' with a
        potential rollback do keep in mind that it's inherently unsafe due
        to how filesystem works and a myriad of things could happen during
        the transaction that break the logic. A file storage could go down,
        permissions could be changed, other machines could be moving or writing
        files. A lot can happen.

    Warning:
        Any folders created during the transfer will not be removed.
    """

    MODE_COPY = 0
    MODE_HARDLINK = 1
    MODE_SYMLINK = 2

    def __init__(self, log=None, allow_queue_replacements=False):
        if log is None:
            log = logging.getLogger("FileTransaction")

        self.log = log

        # The transfer queue
        # todo: make this an actual FIFO queue?
        self._transfers = {}

        # Destination file paths that a file was transferred to
        self._transferred = []

        # Backup file location mapping to original locations
        self._backup_to_original = {}

        self._allow_queue_replacements = allow_queue_replacements

    def add(self, src, dst, mode=MODE_COPY):
        """Add a new file to transfer queue.

        Args:
            src (str): Source path.
            dst (str): Destination path.
            mode (MODE_COPY, MODE_HARDLINK, MODE_SYMLINK): Transfer mode.
        """

        opts = {"mode": mode}

        src = os.path.normpath(os.path.abspath(src))
        dst = os.path.normpath(os.path.abspath(dst))

        if dst in self._transfers:
            queued_src = self._transfers[dst][0]
            if src == queued_src:
                self.log.debug(
                    "File transfer was already in queue: {} -> {}".format(
                        src, dst))
                return
            else:
                if not self._allow_queue_replacements:
                    raise DuplicateDestinationError(
                        "Transfer to destination is already in queue: "
                        "{} -> {}. It's not allowed to be replaced by "
                        "a new transfer from {}".format(
                            queued_src, dst, src
                        ))

                self.log.warning("File transfer in queue replaced..")
                self.log.debug(
                    "Removed from queue: {} -> {} replaced by {} -> {}".format(
                        queued_src, dst, src, dst))

        self._transfers[dst] = (src, opts)

    def process(self):
        # Backup any existing files
        for dst, (src, _) in self._transfers.items():
            self.log.debug("Checking file ... {} -> {}".format(src, dst))
            path_same = self._same_paths(src, dst)
            if path_same or not os.path.exists(dst):
                continue

            # Backup original file
            # todo: add timestamp or uuid to ensure unique
            backup = dst + ".bak"
            self._backup_to_original[backup] = dst
            self.log.debug(
                "Backup existing file: {} -> {}".format(dst, backup))
            os.rename(dst, backup)

        # Copy the files to transfer
        for dst, (src, opts) in self._transfers.items():
            path_same = self._same_paths(src, dst)
            if path_same:
                self.log.debug(
                    "Source and destination are same files {} -> {}".format(
                        src, dst))
                continue

            self._create_folder_for_file(dst)

            if opts["mode"] == self.MODE_COPY:
                self.log.debug("Copying file ... {} -> {}".format(src, dst))
                copyfile(src, dst)
            elif opts["mode"] == self.MODE_HARDLINK:
                self.log.debug("Hardlinking file ... {} -> {}".format(
                    src, dst))
                create_hardlink(src, dst)
            elif opts["mode"] == self.MODE_SYMLINK:
                self.log.debug("Symlinking file ... {} -> {}".format(
                    src, dst))
                create_symlink(src, dst)

            self._transferred.append(dst)

    def finalize(self):
        # Delete any backed up files
        for backup in self._backup_to_original.keys():
            try:
                os.remove(backup)
            except OSError:
                self.log.error(
                    "Failed to remove backup file: {}".format(backup),
                    exc_info=True)

    def rollback(self):
        errors = 0
        last_exc = None
        # Rollback any transferred files
        for path in self._transferred:
            try:
                os.remove(path)
            except OSError as exc:
                last_exc = exc
                errors += 1
                self.log.error(
                    "Failed to rollback created file: {}".format(path),
                    exc_info=True)

        # Rollback the backups
        for backup, original in self._backup_to_original.items():
            try:
                os.rename(backup, original)
            except OSError as exc:
                last_exc = exc
                errors += 1
                self.log.error(
                    "Failed to restore original file: {} -> {}".format(
                        backup, original),
                    exc_info=True)

        if errors:
            self.log.error(
                "{} errors occurred during rollback.".format(errors),
                exc_info=True)
            raise last_exc

    @property
    def transferred(self):
        """Return the processed transfers destination paths"""
        return list(self._transferred)

    @property
    def backups(self):
        """Return the backup file paths"""
        return list(self._backup_to_original.keys())

    def _create_folder_for_file(self, path):
        dirname = os.path.dirname(path)
        try:
            os.makedirs(dirname)
        except OSError as e:
            if e.errno != errno.EEXIST:
                self.log.critical("An unexpected error occurred.")
                raise e

    def _same_paths(self, src, dst):
        # handles same paths but with C:/project vs c:/project
        if os.path.exists(src) and os.path.exists(dst):
            return os.stat(src) == os.stat(dst)

        return src == dst
