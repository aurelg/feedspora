'''
Created on Nov 2, 2015

@author: Aurelien Grosdidier
@contact: aurelien.grosdidier@gmail.com
'''

from feedspora.feedspora import FeedSpora, DiaspyClient, TweepyClient, FacebookClient

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
        client = globals()[account['type']]
        feedspora.connect(client(account))
    [connect_account(account) for account in config['accounts']]
    feedspora.set_db_file('feedspora.db')
    feedspora.run()
    