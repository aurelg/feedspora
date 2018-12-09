import json
from pathlib import Path
from unittest.mock import patch

from feedspora.__main__ import main


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

                assert expected[feedkey][clientkey] \
                        == tested[feedkey][clientkey], \
                        "Entries: Tested: %s\nExpected: %s" % \
                        (tested[feedkey][clientkey],
                         expected[feedkey][clientkey])
    # Cleanup db file

    if dbfile.exists():
        dbfile.unlink()
