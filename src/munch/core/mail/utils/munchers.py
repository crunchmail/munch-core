from django.utils.module_loading import import_string


class MuncherRunner:
    def __init__(self, settings, filters_settings_key):
        self.settings = settings
        self.filters_settings_key = filters_settings_key

    def process(self, *args, **kwargs):
        raise NotImplementedError


class ContentMuncherRunner(MuncherRunner):
    def process(self, indata, *args, **kwargs):
        registered_functions = self.settings.get(
            self.filters_settings_key, [])

        outdata = indata
        for func_dotted_path in registered_functions:
            func = import_string(func_dotted_path)
            outdata = func(outdata, *args, **kwargs)

        return outdata


class HeadersMuncherRunner(MuncherRunner):
    def process(self, *args, **kwargs):
        registered_functions = self.settings.get(
            self.filters_settings_key, [])

        for func_dotted_path in registered_functions:
            func = import_string(func_dotted_path)
            func(*args, **kwargs)
