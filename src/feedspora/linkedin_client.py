"""
LinkedIn client
"""
import copy

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
        self._account = copy.deepcopy(account)

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
            "client":
            self._account['name'],
            "title":
            self._trim_string(kwargs['entry'].title, 200),
            "link":
            self.shorten_url(kwargs['entry'].link),
            "visibility":
            self._visibility,
            "description":
            self._trim_string(kwargs['entry'].title, 256),
            "Comment": self._account['post_prefix'] + \
            self._mkrichtext(
                kwargs['entry'].title,
                self.filter_tags(kwargs['entry']),
                maxlen=700) + \
            self._account['post_suffix']
        }

    def post(self, entry):
        '''
        Post entry to LinkedIn
        :param entry:
        '''
        to_return = False

        if self.is_testing():
            self.accumulate_testing_output(self.get_dict_output(entry=entry))
        else:
            comment = self._account['post_prefix'] + \
                      self._mkrichtext(entry.title, self.filter_tags(entry),
                                       maxlen=700) + \
                      self._account['post_suffix']
            to_return = self._linkedin.submit_share(
                comment=comment,
                title=self._trim_string(entry.title, 200),
                description=self._trim_string(entry.title, 256),
                submitted_url=self.shorten_url(entry.link),
                visibility_code=self._visibility)

        return to_return
