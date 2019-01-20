"""
GenericFeed: base class providing features to specific feeds.
"""

from feedspora.common_config import CommonConfig

class GenericFeed(CommonConfig):
    '''
    Implements the base functionalities expected from feeds.
    Nearly all of this comes from CommonConfig.
    '''
    _path = None

    def __init__(self, config):
        '''
        Initialize
        :param config:
        '''
        if isinstance(config, str):
            # "Old school" configuration (feeds as path strings)
            self._path = config
            # ...for setting defaults, etc. below
            config = dict()
        elif isinstance(config, dict):
            # New style configuration (feeds as dict structures)
            if 'path' in config:
                self._path = config['path']
        self._config = config
        self.set_common_opts(config)

    def get_path(self):
        '''
        Get the defined path (URL)
        '''
        return self._path
