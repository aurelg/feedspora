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

    # load expected
    with open(f"{feedtype}.au") as fp:
        expected = fp.read().split("\n")

    with patch("sys.argv", ["main", "--testing", feedtype]):
        main()
        # retrieve stdout and stderr
        captured = capsys.readouterr()
        # Compare
        print(captured.err)
        tested = captured.out.split("\n")
        # Check their length
        assert len(expected) == len(tested)

        # Check line by line

        for tested_line, expected_line in zip(tested, expected):
            assert tested_line == expected_line

    # Cleanup db file

    if dbfile.exists():
        dbfile.unlink()
