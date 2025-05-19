import pyblish.api
import subprocess
import re
import os
import platform
import logging

class CollectLicenseData(pyblish.api.InstancePlugin):

    """Collect License Data"""

    hosts = ["nuke"]
    label = "Collect License Data"
    order = pyblish.api.CollectorOrder + 0.4990
    optional = True
    rlm_path = os.getenv("RLMUTIL_EXEC")
    if not rlm_path:
        logging.error(
            "Please set the RLMUTIL_EXEC environment variable to the path of "
            "your rlmutil executable in your Nuke environment."
        )
        raise RuntimeError("RLMUTIL_EXEC environment variable is not set.")

    # Match with server address
    foundry_licence_regex_result = re.search(r':(\d+@[\w.]+)', os.environ.get("foundry_LICENSE", ""))
    foundry_licence = foundry_licence_regex_result.group(1) if foundry_licence_regex_result else None

    def get_available_licenses(self):
        if not self.foundry_licence:
            return False

        # Define the command to run
        avail_command = f'{self.rlm_path} rlmstat -c {self.foundry_licence} -avail'

        # Define the pattern for matching the number of available licenses for nuke_i
        pattern = r'nuke_i v\d+\.\d+ available: (\d+)'

        # Run the command and capture the output
        result = subprocess.run(avail_command, shell=True, stdout=subprocess.PIPE, text=True)

        # Use regex to find the match in the output
        match = re.search(pattern, result.stdout)

        # Check if a match is found
        if match:
            # Extract the number of available licenses
            available_licenses = int(match.group(1))
            logging.info(f'License available detected : {available_licenses}')
        else:
            return False

        if available_licenses == 0:
            return False

        return True

    def get_user_licenses(self):
        if not self.foundry_licence:
            return False

        # Define the pattern for matching user licenses for nuke_i
        user_command = f'{self.rlm_path} rlmstat -c {self.foundry_licence} -u {os.environ["USER"]}'

        user_pattern = r'nuke_i v\d+\.\d+: (\S+)@\S+ (\d+)/(\d+)'

        # Run the command and capture the output
        result = subprocess.run(user_command, shell=True, stdout=subprocess.PIPE, text=True)

        # Use regex to find the match in the output
        matches = re.findall(user_pattern, result.stdout)

        # Check if any matches are found
        if matches:
            logging.info('User already have a license')
            return True

        logging.info('User does not have a license')
        return False

    def process(self, instance):

        # If user is not on Linux, make the publish non-blocking
        if platform.system() != 'Linux':
            logging.info("Collect License Data is only available on linux")
            return True

        # If rlm_path has been modified, make the publish non-blocking
        if not os.path.exists(self.rlm_path):
            logging.warning("Can't Detect the RLM bin path")
            return True

        # Check if user already have a license
        if self.get_user_licenses():
            logging.info("License found with success")
            return True

        # Check if user can get an available license
        if self.get_available_licenses():
            logging.info("License found with success")
            return True

        # User can't publish
        raise Exception("No available license ! Can't publish")
