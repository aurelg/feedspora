'''
Created on Nov 2, 2015

@author: aurelien
'''

from feedspora.feedspora import FeedSpora

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
    feedspora.connect(config['account']['pod'],
                      config['account']['name'],
                      config['account']['password'])
    feedspora.set_db_file('feedspora.db')
    feedspora.run()
    