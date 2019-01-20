"""
CommonConfig: Common configuration functions applying to both
GenericClient and GenericFeed.
"""

class CommonConfig:
    _config = None
    _posts_done = 0

    def __init__(self, config):
        '''
        Initialize
        :param config:
        '''
        self._config = config
        self.set_common_opts(config)

    def get_config(self):
        '''
        Return config dict
        (Really only needed so that non-config code can access a public method)
        '''

        return self._config

    def is_post_limited(self):
        '''
        Config has a post limit set
        '''

        return self._config['max_posts'] != 0

    def set_option_defaults(self, config):
        '''
        Set default values for options common to all clients/feeds
        :param config:
        '''

        option_defaults = {'max_posts': 0,
                           'max_tags': 100,
                           'post_prefix': '',
                           'post_suffix': '',
                           'post_include_content': False,
                           'post_include_media': False,
                          }
        for option, default_value in option_defaults.items():
            if option not in config:
                self._config[option] = default_value


    def set_common_opts(self, config):
        '''
        Set options common to all clients/feeds
        This should only entail setting any defaults or changing any
        formats that need such or data manipulations required
        :param config:
        '''

        # Failsafe - should already have been initialized... except during tests
        if not self._config:
            if config:
                self._config = config
            else:
                self._config = dict()

        self.set_option_defaults(config)

        # Format changes/data manipulations
        # Tags
        if 'tags' in config:
            self._config['tags'] = [
                word.strip() for word in config['tags'].split(',')
            ]
        else:
            self._config['tags'] = []

        # Tag filtering options
        if 'tag_filter_opts' in config:
            self._config['tag_filter_opts'] = {key.strip(): True \
                for key in config['tag_filter_opts'].split(',')}
        else:
            self._config['tag_filter_opts'] = dict()

        # URL shortener
        if 'url_shortener' in config:
            self._config['url_shortener'] = config['url_shortener'].lower()
        # URL shortener opts
        if 'url_shortener_opts' not in config:
            self._config['url_shortener_opts'] = dict()

