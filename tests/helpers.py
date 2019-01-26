import logging
import json
from pathlib import Path
from unittest.mock import patch

from feedspora.__main__ import main

def list_cmp(a_list, b_list):
    """
    Return a list of elements in a_list but not in b_list
    """

    return [item for item in a_list if item not in b_list]


def detailed_cmp(tested, expected):
    """
    Perform a detailed analysis of just how the two are different
    """

    # Check the size first
    if len(tested) != len(expected):
        logging.error("Size of tested is %d, expected is %d!",
                      len(tested), len(expected))
    not_in_list = list_cmp(tested, expected)
    if not_in_list:
        logging.error("Missing from 'expected' list:\n%s",
                      ''.join(["\n    {}".format(json.dumps(x)) \
                                                 for x in not_in_list]))
    not_in_list = list_cmp(expected, tested)
    if not_in_list:
        logging.error("Missing from 'tested' list:\n%s",
                      ''.join(["\n    {}".format(json.dumps(x)) \
                                                 for x in not_in_list]))


def check_feed(capsys, feedtype):
    """
    Run feedspora and check its output
    """

    # Remove db file, if it exists
    dbfile = Path(f"{feedtype}.db")

    if dbfile.exists():
        dbfile.unlink()

    # Load expected
    with open(f"{feedtype}.au") as fp:
        expected = json.load(fp)

    with patch("sys.argv", ["main", "--testing", feedtype]):
        # Clear collected out/err
        capsys.readouterr()
        main()
        # Retrieve stdout and stderr
        stdout = capsys.readouterr().out
        tested = json.loads(stdout)

        # Check tested and expected have the same feeds
        assert tested.keys() == expected.keys(), \
            "Feeds: Tested: %s\nExpected: %s" % \
            (tested.keys(), expected.keys())

        # For each feed client, check that the list of entries is the same

        for feedkey in expected.keys():
            print(f"Testing feed {feedkey}")
            # Check tested and expected have the same Clients
            assert expected[feedkey].keys() == tested[feedkey].keys(), \
                "Clients: Tested: %s\nExpected: %s" % \
                (tested[feedkey].keys(), expected[feedkey].keys())

            for clientkey in expected[feedkey].keys():

                try:
                    assert expected[feedkey][clientkey] \
                            == tested[feedkey][clientkey], \
                            "Entries: Tested: %s\nExpected: %s" % \
                            (tested[feedkey][clientkey],
                             expected[feedkey][clientkey])
                except AssertionError:
                    # Get a more detailed analysis than a "==" test allows
                    detailed_cmp(tested[feedkey][clientkey],
                                 expected[feedkey][clientkey])
                    raise

    # Cleanup db file

    if dbfile.exists():
        dbfile.unlink()
