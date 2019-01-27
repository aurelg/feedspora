"""
LinkedIn client
"""

from linkedin import linkedin

from feedspora.generic_client import GenericClient


class LinkedInClient(GenericClient):
    ''' The LinkedInClient handles the connection to LinkedIn. '''
    _linkedin = None
    _visibility = None

    def __init__(self, config, testing):
        '''
        Initialize
        :param config:
        :param testing:
        '''
        self._config = config

        if not testing:
            self._linkedin = linkedin.LinkedInApplication(
                token=config['authentication_token'])
        self._visibility = config['visibility']
        self.set_common_opts(config)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._config['name'],
            "comment": kwargs['comment'],
            "title": kwargs['title'],
            "description": kwargs['description'],
            "link": kwargs['submitted_url'],
            "media": kwargs['submitted_image_url'],
            "visibility": self._visibility
        }

    def post(self, feed, entry):
        '''
        Post entry to LinkedIn
        :param feed:
        :param entry:
        '''
        stripped_html = self.strip_html(feed, entry.content) \
                        if entry.content else None
        raw_contents = entry.title
        if self.resolve_option(feed, 'post_include_content') and stripped_html:
            raw_contents += ': '+stripped_html
        comment = self.resolve_option(feed, 'post_prefix') + \
                  self._mkrichtext(raw_contents, self.filter_tags(feed, entry),
                                   maxlen=700) + \
                  self.resolve_option(feed, 'post_suffix')
        # Just in case...
        comment = comment.strip()

        post_args = {'comment': comment,
                     'title': self._trim_string(entry.title, 200),
                     'description': self._trim_string(entry.title, 256),
                     'submitted_url': self.shorten_url(feed, entry.link),
                     'submitted_image_url': None,
                     'visibility_code': self._visibility
                     }
        if self.resolve_option(feed, 'post_include_media') and entry.media_url:
            post_args['submitted_image_url'] = entry.media_url

        to_return = False
        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(**post_args))
        else:
            to_return = self._linkedin.submit_share(**post_args)
            if 'updateUrl' not in to_return:
                # Failure - pass it on
                to_return = {}

        return to_return
