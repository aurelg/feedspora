"""
LinkedIn client
"""

from linkedin import linkedin

from feedspora.generic_client import GenericClient


class LinkedInClient(GenericClient):
    ''' The LinkedInClient handles the connection to LinkedIn. '''
    _linkedin = None
    _visibility = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        self._account = account

        if not testing:
            self._linkedin = linkedin.LinkedInApplication(
                token=account['authentication_token'])
        self._visibility = account['visibility']
        self.set_common_opts(account)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._account['name'],
            "comment": kwargs['comment'],
            "title": kwargs['title'],
            "description": kwargs['description'],
            "link": kwargs['submitted_url'],
            "media": kwargs['submitted_image_url'],
            "visibility": self._visibility
        }

    def post(self, entry):
        '''
        Post entry to LinkedIn
        :param entry:
        '''
        stripped_html = self.strip_html(entry.content) \
                        if entry.content else None
        raw_contents = entry.title
        if self._account['post_include_content'] and stripped_html:
            raw_contents += ': '+stripped_html
        comment = self._account['post_prefix'] + \
                  self._mkrichtext(raw_contents, self.filter_tags(entry),
                                   maxlen=700) + \
                  self._account['post_suffix']
        # Just in case...
        comment = comment.strip()

        post_args = {'comment': comment,
                     'title': self._trim_string(entry.title, 200),
                     'description': self._trim_string(entry.title, 256),
                     'submitted_url': self.shorten_url(entry.link),
                     'submitted_image_url': None,
                     'visibility_code': self._visibility
                     }
        if self._account['post_include_media'] and entry.media_url:
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
