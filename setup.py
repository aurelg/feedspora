"""
Documentation
"""

from distutils.core import setup
from feedspora import __version__

mod_name = 'feedspora'
setup(name=mod_name,
      version=__version__,
      package_dir={'': 'src'},
      packages=['feedspora'],
      package_data={mod_name: ['../../README.md', '../../feedspora.yml.template']},
      url='http://aurelien.latitude77.org',
      author='Aurelien Grosdidier',
      author_email='aurelien.grosdidier@gmail.com',
      requires=['diaspy', 'beautifulsoup4'])
