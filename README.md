NLPAPI
======

This repo contains a python based API server that provides various NLP APIs.

## Setup Python

In order to setup python install `python >= 3.11` and `conda`.
Create a new environment and activate it.
Then run:
```
make install
```

For contributing python code run:
```
make pre-commit
```
To set up the python pre-commit hook.

And ensure that all lints pass:
```
make lint-all
```
You can also call individual lints via make. See `make help`.

## Running the server

In order to get the language API to work, create the tables by running:
```
python -m app.system --init-location
```
Or to create tables for all APIs via:
```
python -m app.system --init-db
```

The first time you will get an error that the config file is missing.
It will create a config file for you. Locate it and fill in all correct values.

Once the config file and the tables are created run:
```
make run-api
```
To start the server. The server has an interactive mode. You can type commands
in the terminal. The most useful commands are `quit`, `restart`, and `help`.

## Use docker image locally

Prepare a config file for the image to use named `docker.config.json`
(you can copy your local config file but keep in mind that your `localhost` is
`host.docker.internal` inside the container).

Run
```
make -s build-dev
```
to build the docker image
(note that the config file will be baked into the image).
Use `make -s git-check` to verify that the current working copy is clean and
that no unwanted (or uncommit) files will be included in the image.

If you just want to run the API locally start the container via:
```
make compose
```

Test the connection via:
```
curl -X POST --json '{"token": <user token>, "input": "Is London really a place?"}' http://localhost:8080/api/locations
```

## Push docker image

Make sure to log in to azure via `make azlogin`.

Run
```
CONFIG_PATH=- make -s build
make -s dockerpush
```
to build the image and push it to azure. Note, that the settings are read
from the environment at deploy time and not from the config file.

## Deploying new version

Make sure to be on the main branch with a clean working copy.

Run
```
make -s deploy
```
