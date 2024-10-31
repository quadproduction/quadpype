# -*- coding:  utf-8 -*-
"""Parse pyproject.toml and return its values.

Useful for shell scripts to know more about QuadPype build.
"""
import sys
import toml
from pathlib import Path
import click


@click.command()
@click.argument("keys", nargs=-1, type=click.STRING)
def main(keys):
    """Get values from `pyproject.toml`.

    You can specify dot separated keys from `pyproject.toml`
    as arguments and this script will return them on separate
    lines. If the key doesn't exist, None is returned.

    """
    repo_root = Path(__file__)
    while (repo_root.parts[-1]) != "src":
        repo_root = repo_root.parent
    repo_root.resolve()

    py_project = toml.load(repo_root.joinpath("pyproject.toml"))
    for q in keys:
        query = q.split(".")
        data = py_project

        for k in query:
            if isinstance(data, list):
                try:
                    data = data[int(k)]
                except IndexError:
                    print("None")
                    sys.exit()
                continue

            if isinstance(data, dict):
                data = data.get(k)
        print(data)


if __name__ == "__main__":
    main()
