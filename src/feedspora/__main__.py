'''
Created on Nov 2, 2015

@author: Aurelien Grosdidier
@contact: aurelien.grosdidier@gmail.com
'''
import argparse
import logging
# pylint: disable=unused-import
from feedspora.feedspora_runner import FeedSpora
from feedspora.feedspora_runner import DiaspyClient  # @UnusedImport
from feedspora.feedspora_runner import TweepyClient  # @UnusedImport
from feedspora.feedspora_runner import FacebookClient  # @UnusedImport
from feedspora.feedspora_runner import WPClient  # @UnusedImport
from feedspora.feedspora_runner import MastodonClient  # @UnusedImport
from feedspora.feedspora_runner import ShaarpyClient  # @UnusedImport
from feedspora.feedspora_runner import LinkedInClient  # @UnusedImport
# pylint: enable=unused-import

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
    # Parse input args
    arg_parser = argparse.ArgumentParser(
        description='Post from Atom/RSS feeds to various client types.')
    arg_parser.add_argument('-t', '--testing', nargs='?',
                        const='feedspora', default=None,
                        help='execute test runs; no actual posting done')
    parsed_args = arg_parser.parse_args()

    # root name of config and DB files, optionally modified by the --testing
    # argument value (if present)
    root_name = parsed_args.testing if parsed_args.testing else 'feedspora'

    run_config = read_config_file(root_name+'.yml')
    feedspora_main = FeedSpora()
    feedspora_main.set_feed_urls(run_config['feeds'])

    def connect_account(account, testing):
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
            client.set_name(account['name'])
            client.set_testing_root(testing)
            feedspora.connect(client)
        except Exception as exception:
            logging.error('Cannot connect {} : {}',
                          account['name'], str(exception))
        # pylint: enable=broad-except

    for account in run_config['accounts']:
        if 'enabled' not in account or account['enabled']:
            connect_account(account, parsed_args.testing)
    feedspora.set_db_file(root_name+'.db')
    feedspora.run()
