"""
Wordpress client
"""

import json
from urllib.parse import urlparse

import requests
from readability.readability import Document, Unparseable
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost

from feedspora.generic_client import GenericClient


class WPClient(GenericClient):
    ''' The WPClient handles the connection to Wordpress. '''
    client = None

    def __init__(self, account, testing):
        '''
        Initialize
        :param account:
        :param testing:
        '''

        if not testing:
            self.client = Client(account['wpurl'], account['username'],
                                 account['password'])
        self.set_common_opts(account)

    # pylint: disable=no-self-use
    def get_content(self, url):
        '''
        Retrieve URL content and parse it w/ readability if it's HTML
        :param url:
        '''
        request = requests.get(url)
        content = ''

        # pylint: disable=no-member

        if request.status_code == requests.codes.ok and \
           request.headers['Content-Type'].find('html') != -1:
            try:
                content = Document(request.text).summary()
            except Unparseable:
                pass
        # pylint: enable=no-member

        return content

    # pylint: enable=no-self-use

    def test_output(self, **kwargs):
        '''
        Print output for testing purposes
        :param kwargs:
        '''
        print(
            json.dumps({
                "client": self.get_name(),
                "title": kwargs['entry'].title,
                "post_tag": self.filter_tags(kwargs['entry']),
                "Content": self.shorten_url(kwargs['entry'].link)
            },
                       indent=4))

        return True

    def post(self, entry):
        '''
        Post entry to Wordpress.
        :param entry:
        '''

        post_content = r"Source: <a href='{}'>{}</a><hr\>{}".format(
            self.shorten_url(entry.link),
            urlparse(entry.link).netloc, self.get_content(entry.link))
        to_return = False

        if self.is_testing():
            to_return = self.test_output(entry=entry)
        else:
            # get text with readability
            post = WordPressPost()
            post.title = entry.title
            post.content = post_content
            post.terms_names = {
                'post_tag': self.filter_tags(entry),
                'category': ["AutomatedPost"]
            }
            post.post_status = 'publish'
            post_id = self.client.call(NewPost(post))
            to_return = post_id != 0

        return to_return
