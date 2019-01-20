"""
GenericFeed: base class providing features to specific feeds.
"""

from feedspora.common_config import CommonConfig

class GenericFeed(CommonConfig):
    '''
    Implements the base functionalities expected from feeds.
    Nearly all of this comes from CommonConfig.
    '''

    def __init__(self, config):
        '''
        Initialize
        :param config:
        '''
        self._config = config
        self.set_common_opts(config)
