import re
import sys
import argparse
import subprocess
import platform
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog='QuadPype Pre Run Script',
        description='Mandatory script that will execute the platform dependant code before QuadPype run'
    )
    parser.add_argument("-d", "--dev", action="store_true")
    parser.add_argument("-p", "--prod", action="store_true")
    parser.add_argument("-m", "--mongo-uri", help='Format should be like: mongodb://uri.to.my.mongo-db:27017')

    args = parser.parse_args()

    # Build the argument string for the platform dependant script
    args_string = ""
    if args.dev:
        args_string += "-d"

    if args.prod and not args.dev:
        # If the used add the flags for dev and prod,
        # we start in dev, to avoid potential mistakes or issues
        args_string += "-p"

    if args.mongo_uri:
        # First, check MongoDB connection string format validity
        match = re.fullmatch(r"^mongodb(\+srv)?://([\w.%-]+:[\w.%-]+@)?[\w.%-]+(:\d{1,5})?/?$", args.mongo_uri)
        if not match:
            raise ValueError("Value of script argument '--mongo-uri' doesn't match the expected format\n"
                             "The connection string should look like: mongodb://uri.to.my.mongo-db:27017\n"
                             "The regex pattern used is: '^mongodb(\+srv)?://([\w.%-]+:[\w.%-]+@)?[\w.%-]+(:\d{1,5})?/?$'")
        args_string += " -m {}".format(args.mongo_uri)

    low_platform = platform.system().lower()

    repo_root = Path(__file__)
    while (repo_root.parts[-1]) != "src":
        repo_root = repo_root.parent
    repo_root.resolve()

    print("#######################")
    print(args_string)
    print("#######################")

    if low_platform == "windows":
        pre_run_script_path = repo_root.joinpath("tools", "pre_run.ps1")
        p = subprocess.Popen(
            'powershell.exe -ExecutionPolicy RemoteSigned -file "{}" {}'.format(
                pre_run_script_path, args_string),
            stdout=sys.stdout
        )
        p.communicate()
    else:
        raise NotImplementedError("ERROR: The pre_run script hasn't yet being coded for this platform")


if __name__ == "__main__":
    main()
