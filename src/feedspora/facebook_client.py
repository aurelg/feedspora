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

    def __init__(self, config, testing):
        '''
        Initialize
        :param config:
        :param testing:
        '''
        self._config = config

        if not testing:
            self._graph = facebook.GraphAPI(config['token'])

        self.set_common_opts(config)

    def get_dict_output(self, **kwargs):
        '''
        Return dict output for testing purposes
        :param kwargs:
        '''

        return {
            "client": self._config['name'],
            "link": kwargs['attachment']['link'],
            "message": kwargs['attachment']['message']
        }

    def post(self, feed, entry):
        '''
        Post entry to Facebook.
        :param feed:
        :param entry:
        '''
        # "Only owners of the URL have the ability to specify the picture,
        #  name, thumbnail or description params." -- Facebook Law
        # This greatly limits what we can reliably do/provide, obviously
        stripped_html = self.strip_html(feed, entry.content) \
                        if entry.content else None
        text = ''
        if self.resolve_option(feed, 'post_include_content') and \
           stripped_html or \
           not self.resolve_option(feed, 'post_include_media'):
            text = self.resolve_option(feed, 'post_prefix')
            if not self.resolve_option(feed, 'post_include_media'):
                # Not including media (which pulls in the title as the link
                # name), so we need to insert the title here
                text += entry.title
                if self.resolve_option(feed, 'post_include_content') and \
                   stripped_html:
                    # More to come, so add a delimiter
                    text += ': '
            if self.resolve_option(feed, 'post_include_content') and \
               stripped_html:
                text += stripped_html
            text += self.resolve_option(feed, 'post_suffix')
        text += ''.join([' #{}'.format(k)
                         for k in self.filter_tags(feed, entry)])
        if not self.resolve_option(feed, 'post_include_media'):
            text += ' '+self.shorten_url(feed, entry.link)
        # Just in case...
        text = text.strip()

        # 'message' and 'link' are the only two components of a post
        attachment = {'message': text}
        if self.resolve_option(feed, 'post_include_media'):
            # In this case, specify the link, which will include its media
            # (and the title as the link text, as previously mentioned)
            attachment['link'] = self.shorten_url(feed, entry.link)
        else:
            attachment['link'] = None

        to_return = False
        if self.is_testing():
            self.accumulate_testing_output(
                self.get_dict_output(text=text, attachment=attachment))
        else:
            to_return = self._graph.put_object(self._config['post_to_id'],
                                               'feed', **attachment)
            if 'id' not in to_return or to_return['id'] == 0:
                to_return = ()

        return to_return
