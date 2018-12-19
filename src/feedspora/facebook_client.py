"""
Facebook client.
"""
import copy
import facebook

from feedspora.generic_client import GenericClient


class FacebookClient(GenericClient):
    ''' The FacebookClient handles the connection to Facebook. '''
    # See https://stackoverflow.com/questions/11510850/
    #     python-facebook-api-need-a-working-example
    # https://github.com/pythonforfacebook/facebook-sdk
    # https://facebook-sdk.readthedocs.org/en/latest/install.html
    _graph = None
    _post_as = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''
        self._account = copy.deepcopy(account)
        profile = None

        if not testing:
            self._graph = facebook.GraphAPI(account['token'])
            profile = self._graph.get_object('me')

        if 'post_as' not in account:
            if testing:
                self._account['post_as'] = 'TESTER'
            else:
                self._account['post_as'] = profile['id']
        self.set_common_opts(account)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._account['name'],
            "posting_as": self._account['post_as'],
            "name": kwargs['attachment']['name'],
            "link": kwargs['attachment']['link'],
            "content": kwargs['text']
        }

    def post(self, entry):
        '''
        Post entry to Facebook.
        :param entry:
        '''
        text = self._account['post_prefix'] + entry.title + \
               self._account['post_suffix'] + \
               ''.join([' #{}'.format(k) for k in self.filter_tags(entry)])
        attachment = {'name': entry.title,
                      'link': self.shorten_url(entry.link)
                      }

        to_return = False

        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(text=text, attachment=attachment))
        else:
            # pylint: disable=no-member
            to_return = self._graph.put_wall_post(text, attachment,
                                                  self._account['post_as'])
            # pylint: enable=no-member

        return to_return
