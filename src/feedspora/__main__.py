'''
Created on Nov 2, 2015

@author: Aurelien Grosdidier
@contact: aurelien.grosdidier@gmail.com
'''
import logging
from feedspora.feedspora_runner import FeedSpora
from feedspora.feedspora_runner import DiaspyClient  # @UnusedImport
from feedspora.feedspora_runner import TweepyClient  # @UnusedImport
from feedspora.feedspora_runner import FacebookClient  # @UnusedImport
from feedspora.feedspora_runner import WPClient # @UnusedImport
from feedspora.feedspora_runner import MastodonClient # @UnusedImport
from feedspora.feedspora_runner import ShaarpyClient # @UnusedImport
from feedspora.feedspora_runner import LinkedInClient # @UnusedImport


def read_config_file(filename):
    """ Loads the YML configuration file. """
    from yaml import load
    error = ''
    try:
        with open(filename) as config_file:
            return load(config_file)
    except FileNotFoundError as excpt:
        error = format(excpt)
    raise Exception("Couldn't load config file "+filename+":\n"+error)

if __name__ == '__main__':
    config = read_config_file('feedspora.yml')
    feedspora = FeedSpora()
    feedspora.set_feed_urls(config['feeds'])
    def connect_account(account):
        '''
        Initialize a client for the specified account, and register it in FeedSpora
        :param account:
        '''
        try:
            client_class = globals()[account['type']]
            client = client_class(account)
            client.set_name(account['name'])
            feedspora.connect(client)
        except Exception as e:
            logging.error('Cannot connect {} : {}'.format(account['name'],
                                                        str(e)))
    for account in config['accounts']:
        if not 'enabled' in account or account['enabled']:
            connect_account(account)
    feedspora.set_db_file('feedspora.db')
    feedspora.run()
