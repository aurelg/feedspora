# What is FeedSpora?

FeedSpora posts RSS/Atom feeds to your Diaspora account. It's a bot written in Python3, inspired from [Fefebot](https://github.com/svbergerem/fefebot).

# Installation

Install dependencies:

- [Diaspy](https://github.com/marekjm/diaspy) (the latest version is recommended if you can't connect to your pod)
- [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/)
- [PyYAML](http://pyyaml.org)

Then extract FeedSpora and install it with the usual:
    
    python setup.py install
    
# Usage
- Create a config file out of the provided template `feedspora.yml.template`
- Publish all RSS/Atom entries to your Diaspora account with:

		python -m feedspora

