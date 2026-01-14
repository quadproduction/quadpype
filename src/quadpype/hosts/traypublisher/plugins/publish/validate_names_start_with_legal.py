import re
from pathlib import Path

import pyblish.api
from quadpype.pipeline.publish import (
    ValidateContentsOrder,
    PublishXmlValidationError,
)

START_NUMBER_PATTERN = r'^(\d+.+)$'

class ValidateNamesStartWithLegal(pyblish.api.InstancePlugin):
    """Validate if all the files names starts with a legal character"""

    label = "Validate Files Names Start With Legal"
    hosts = ["traypublisher"]
    order = ValidateContentsOrder
    active = True

    def process(self, instance):
        filepaths_with_errors = []

        for filepath in instance.data["sourceFilepaths"]:
            filename = Path(filepath).name
            if re.search(START_NUMBER_PATTERN, filename):
                filepaths_with_errors.append(filepath)

        if filepaths_with_errors:
            if not instance.data.get('transientData'):
                instance.data['transientData'] = dict()

            instance.data['transientData'][self.__class__.__name__] = filepaths_with_errors
            raise PublishXmlValidationError(
                self,
                "Files names can not start with a number : {}.".format(
                    ', '.join([Path(filepath).name for filepath in filepaths_with_errors])
                )
            )
