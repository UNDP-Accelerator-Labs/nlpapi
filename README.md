NLPAPI
======

This repo contains a python based API server that provides various NLP APIs.

A public facing UI can be found [here](https://nlpapi.sdg-innovation-commons.org/search/).

## API usage

You can see some API scenarios [here](/scenarios.md).

## Setup Python

In order to setup python install `python >= 3.11` and `conda`.
Also, make sure `redis` is installed on your system.
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

## Running a full instance locally (without vector database)

`make run-local` which will create a `userdata/env.local` file where you need
to fill in the correct values. Then run `make run-local` again. Also, makes
sure to add the `gguf` file into the `models` folder (to run the LLM).

You can force a vector database to be loaded by setting `NO_QDRANT=false` in the
env file. This, however, requires you to provide credentials for the qdrant
database. It is not possible to access the qdrant database on Azure since it
is private to the docker compose and doesn't expose any endpoints. However, you
can create a local database by either running a docker image with it or by
providing a `file://path/to/database` as qdrant URL.

You can deactivate the LLM by setting `HAS_LLAMA=false` in the env file.

## Diagnosing qdrant

The qdrant UI is exposed on the server via the
[`/qdrant/dashboard`](https://nlpapi.sdg-innovation-commons.org/qdrant/dashboard)
endpoint.
You will have to provide the internal qdrant api token for accessing the
dashboard.

## Running a docker compose locally

Use the `make build-dev` command to create a local docker compose file. This
requires a config file in the root folder: `docker.config.json`. After building
the local docker compose you can run it via `make compose`. Both commands are
unified as `make run-docker-api`. `sample.config.json` provides a sample config
file. It does not specify a local vector database by default. You can replace
the `null` with a valid local configuration, though.

## Publishing the local copy

Make sure to have a clean workspace and all your commits are pushed to github.
Have your docker daemon running.
Run `make azlogin` to log in to the azure account. Then, run
`make publich-local` this will push the local images and end with the docker
compose file printed to stdout. Copy the docker compose content to the
deployment configuration tab on azure and save. This will update the app.

## Publishing a main version

When on the main branch call `make publish` to create the version tag. The
CI will build and push all docker images. Once that is done, from the same
commit, run `make build` locally to get the docker compose file. After that
you can also retrieve the current docker compose file via `make show-compose`.
Take the docker compose file output from either command and copy it to the
deployment configuration tab on azure and save. This will update the app.

## More below

Some of the following information might be redundant and / or slightly
outdated.

## Running the server

In order to get the language API to work, create the tables by running:
```
python -m app.system --init-location
```
Or to create tables for all APIs via:
```
CONFIG_PATH=myconfig.json python -m app.system --init-db
```

The first time you will get an error that the config file is missing.
It will create a config file for you. Locate it and fill in all correct values.
You can also specify a config file path via `CONFIG_PATH` (see above).

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
