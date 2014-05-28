import os
import ConfigParser
from pp_utils import Monitor


class ResourceReader(object):
    config = None

    def __init__(self):
        self.mon = Monitor()
        self.mon.on()

    def read(self, pp_dir, pp_home, pp_profile):
        """
        looks for resources.cfg in the profile, then in pp_home, then in the pi_presents directory.
        returns True if it finds the resources.cfg, otherwise returns False

        ::param pp_dir: the PiPresents directory
        ::param pp_home: the current pp_home directory
        ::param pp_profile: the current profile directory
        """
        if not ResourceReader.config:
            profile_config = os.path.join(pp_profile, "resources.cfg")
            home_config = os.path.join(pp_home, "resources.cfg")
            pp_config = os.path.join(pp_dir, 'pp_home', "resources.cfg")

            # try inside profile
            if os.path.exists(profile_config):
                config_path = profile_config

            # try inside pp_home
            elif os.path.exists(home_config):
                config_path = home_config

            # try in the pi presents directory
            elif os.path.exists(pp_config):
                config_path = pp_config

            else:
                # throw an error if we can't find any config files
                self.mon.err(self, "resources.cfg not found at {0}, {1} or {2}".format(profile_config, home_config, pp_config))
                return False

            ResourceReader.config = ConfigParser.ConfigParser()
            ResourceReader.config.read(config_path)
            self.mon.log(self, "resources.cfg read from " + config_path)
            return True

    def get(self, section, item):
        if not ResourceReader.config.has_option(section, item):
            return False
        else:
            return ResourceReader.config.get(section, item)
    

        


