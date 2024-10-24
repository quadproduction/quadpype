class SaveSettingsValidation(Exception):
    pass


class SaveWarningExc(SaveSettingsValidation):
    def __init__(self, warnings):
        if isinstance(warnings, str):
            warnings = [warnings]
        self.warnings = warnings
        msg = " | ".join(warnings)
        super().__init__(msg)
