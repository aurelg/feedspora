"""
Facebook client.
"""

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
        profile = None

        if not testing:
            self._graph = facebook.GraphAPI(account['token'])
            profile = self._graph.get_object('me')
        self._post_as = 'TESTER'

        if 'post_as' in account:
            self._post_as = account['post_as']
        elif not testing:
            self._post_as = profile['id']

    def test_output(self, **kwargs):
        '''
        Print output for testing purposes
        :param kwargs:
        '''
        output = '>>> ' + self.get_name() + ' posting as ' + self._post_as + \
            ':\n' + 'Name: ' + kwargs['attachment']['name'] + ':\n' + \
            'Link: ' + kwargs['attachment']['link'] + ':\n' + \
            'Content: ' + kwargs['text']

        return self.output_test(output)

    def post(self, entry):
        '''
        Post entry to Facebook.
        :param entry:
        '''
        text = entry.title + ''.join(
            [' #{}'.format(k) for k in entry.keywords])
        attachment = {'name': entry.title, 'link': entry.link}

        to_return = False

        if self.is_testing():
            to_return = self.test_output(text=text, attachment=attachment)
        else:
            # pylint: disable=no-member
            to_return = self._graph.put_wall_post(text, attachment,
                                                  self._post_as)
            # pylint: enable=no-member

        return to_return