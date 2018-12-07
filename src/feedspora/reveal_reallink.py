'''
Created on Nov 26, 2015
@author: aurelien


This script modifies an Atom feed (given as parameter) by replacing every
entries' links and ID by the first link found in its content. The modified feed
is printed on stdout. It allows the new modified feed to make the "real" link
available, instead of the default link, when the latter is not relevant (see
Atom feeds generated out of Diaspora).
'''

import sys

from bs4 import BeautifulSoup


def main():
    '''Entry point if called as an executable'''
    source_filename = sys.argv[1]
    try:
        with open(source_filename) as source_file:
            soup = BeautifulSoup(source_file, 'html.parser')
    except FileNotFoundError:
        print("File " + source_filename + " not found.")

    for entry in soup.find_all('entry'):
        content_soup = BeautifulSoup(
            entry.find('content').string, 'html.parser')
        entry.find('link')['href'] = content_soup.find('a')['href']
        entry.find('id').string = content_soup.find('a')['href']
        entry.find('title').string = content_soup.find('a').string


if __name__ == '__main__':
    main()
