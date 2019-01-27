'''
Created on Nov 2, 2015

@author: Aurelien Grosdidier
@contact: aurelien.grosdidier@gmail.com
'''
import argparse
import logging

# pylint: disable=unused-import
from feedspora.diaspora_client import DiaspyClient  # @UnusedImport
from feedspora.facebook_client import FacebookClient  # @UnusedImport
from feedspora.feedspora_runner import FeedSpora
from feedspora.generic_feed import GenericFeed
from feedspora.linkedin_client import LinkedInClient  # @UnusedImport
from feedspora.mastodon_client import MastodonClient  # @UnusedImport
from feedspora.shaarpy_client import ShaarpyClient  # @UnusedImport
from feedspora.tweepy_client import TweepyClient  # @UnusedImport
from feedspora.wordpress_client import WPClient  # @UnusedImport

# pylint: enable=unused-import


def read_config_file(filename):
    '''
    Loads the YML configuration file.
    :param filename:
    '''
    from yaml import load
    error = ''
    try:
        with open(filename) as config_file:
            return load(config_file)
    except FileNotFoundError as excpt:
        error = format(excpt)
    raise Exception("Couldn't load config file " + filename + ":\n" + error)


def main():
    '''Entry point if called as an executable'''

    def connect_client(account, testing):
        '''
        Initialize a client for the specified account
        Then register it in FeedSpora
        :param account:
        :param testing:
        '''
        # pylint: disable=broad-except
        try:
            client_class = globals()[account['type']]
            client = client_class(account, testing)
            client.set_testing_root(testing)
            feedspora.connect_client(client)
        except Exception as exception:
            logging.error('Cannot connect %s : %s', account['name'],
                          str(exception))
        # pylint: enable=broad-except

    def connect_feed(feed_data):
        '''
        Initialize a feed and register it in FeedSpora
        :param feed_data:
        '''
        feed = GenericFeed(feed_data)
        feedspora.connect_feed(feed)

    # Parse input args
    parser = argparse.ArgumentParser(
        description='Post from Atom/RSS feeds to various client types.')
    parser.add_argument(
        '-t',
        '--testing',
        nargs='?',
        const='feedspora',
        default=None,
        help='execute test runs; no actual posting done')
    args = parser.parse_args()

    # root name of config and DB files, optionally modified by the --testing
    # argument value (if present)
    root_name = args.testing if args.testing else 'feedspora'

    config = read_config_file(root_name + '.yml')
    feedspora = FeedSpora()

    for feed in config['feeds']:
        if 'enabled' not in feed or feed['enabled']:
            connect_feed(feed)

    for account in config['accounts']:
        if 'enabled' not in account or account['enabled']:
            connect_client(account, args.testing)
    feedspora.set_db_file(root_name + '.db')
    feedspora.set_testing(args.testing is not None)
    feedspora.run()


if __name__ == '__main__':
    main()
