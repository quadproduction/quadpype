# -*- coding: utf-8 -*-
"""Create QuadPype patch from current src."""
from igniter import bootstrap_repos
import click
import enlighten
from pathlib2 import Path


manager = enlighten.get_manager()


@click.group(invoke_without_command=True)
@click.option("--path", required=False,
              help="Destination path to place the patch zip archive",
              type=click.Path(exists=True))
def main(path):
    # create zip file

    progress_bar = enlighten.Counter(
        total=100, desc="QuadPype Patch Creation", units="Files", color="green")

    def update_progress(value):
        progress_bar.update(incr=value)

    bs = bootstrap_repos.BootstrapRepos(progress_callback=update_progress)

    if path:
        out_path = Path(path)
        bs.data_dir = out_path
        if out_path.is_file():
            bs.data_dir = out_path.parent

    _print(f"Creating the patch zip archive in {bs.data_dir} ...")
    version = bs.create_version_from_live_code()

    progress_bar.close(clear=True)
    if not version:
        _print("Error while creating the patch zip archive.", 1)
        exit(1)

    _print(f"Successfully created patch archive v{version}")


def _print(msg: str, message_type: int = 0) -> None:
    """Print message to console.

    Args:
        msg (str): message to print
        message_type (int): type of message (0 info, 1 error, 2 note)

    """
    if not bootstrap_repos.term:
        header = ""
    elif message_type == 0:
        header = bootstrap_repos.term.aquamarine3(">>> ")
    elif message_type == 1:
        header = bootstrap_repos.term.orangered2("!!! ")
    elif message_type == 2:
        header = bootstrap_repos.term.tan1("... ")
    else:
        header = bootstrap_repos.term.darkolivegreen3("--- ")

    print(f"{header}{msg}")


if __name__ == "__main__":
    main()
