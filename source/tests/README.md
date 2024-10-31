Automatic tests for QuadPype
============================

Requirements:
============
Tests are recreating fresh DB for each run, so `mongorestore`, `mongodump` and `mongoimport` command line tools must be installed and on Path.

You can find intallers here: https://www.mongodb.com/docs/database-tools/installation/installation/

You can test that `mongorestore` is available by running this in console, or cmd:
```mongorestore --version```

Structure:
- integration - end to end tests, slow (see README.md in the integration folder for more info)
    - quadpype/modules/MODULE_NAME - structure follow directory structure in code base
        - fixture - sample data `(MongoDB dumps, test files etc.)`
        - `tests.py` - single or more pytest files for MODULE_NAME
- unit - quick unit test
    - MODULE_NAME
        - fixture
        - `tests.py`

How to run:
----------
- use QuadPype command 'runtests' from command line (`.venv` in ${QUADPYPE_ROOT} must be activated to use configured Python!)
-- `python ${QUADPYPE_ROOT}/start.py runtests`

By default, this command will run all tests in ${QUADPYPE_ROOT}/tests.

Specific location could be provided to this command as an argument, either as absolute path, or relative path to ${QUADPYPE_ROOT}.
(eg. `python ${QUADPYPE_ROOT}/start.py start.py runtests ../tests/integration`) will trigger only tests in `integration` folder.

See `${QUADPYPE_ROOT}/cli.py:runtests` for other arguments.

Run in IDE:
-----------
If you prefer to run/debug single file directly in IDE of your choice, you might encounter issues with imports.
It would manifest like `KeyError: 'QUADPYPE_DATABASE_NAME'`. That means you are importing module that depends on QuadPype to be running, eg. all expected variables are set.

In some cases your tests might be so localized, that you don't care about all env vars to be set properly.
In that case you might add this dummy configuration BEFORE any imports in your test file
```
import os
os.environ["QUADPYPE_DEBUG"] = "1"
os.environ["QUADPYPE_MONGO"] = "mongodb://localhost:27017"
os.environ["QUADPYPE_DATABASE_NAME"] = "quadpype"
os.environ["AVALON_DB"] = "avalon"
os.environ["AVALON_TIMEOUT"] = "3000"
os.environ["AVALON_ASSET"] = "Asset"
os.environ["AVALON_PROJECT"] = "test_project"
```
(AVALON_ASSET and AVALON_PROJECT values should exist in your environment)

This might be enough to run your test file separately. Do not commit this skeleton though.
Use only when you know what you are doing!
