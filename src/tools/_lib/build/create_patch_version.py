# -*- coding: utf-8 -*-
"""Create QuadPype patch from current src."""
import click
import enlighten
from pathlib2 import Path

from appdirs import user_data_dir


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

    if path:
        out_dir_path = Path(path)
        if out_dir_path.is_file():
            out_dir_path = out_dir_path.parent
    else:
        out_dir_path = Path(user_data_dir("quadpype", "quad"))

    _print(f"Creating the patch zip archive in {out_dir_path} ...")
    version = create_version_from_live_code(progress_callback=update_progress)

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
    if not bootstrap.term:
        header = ""
    elif message_type == 0:
        header = bootstrap.term.aquamarine3(">>> ")
    elif message_type == 1:
        header = bootstrap.term.orangered2("!!! ")
    elif message_type == 2:
        header = bootstrap.term.tan1("... ")
    else:
        header = bootstrap.term.darkolivegreen3("--- ")

    print(f"{header}{msg}")


if __name__ == "__main__":
    main()
