smartsearch
===========

This repo contains a python based API server that provides various NLP APIs.

## Setup Python

In order to setup python install `python >= 3.10` and `conda`.
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
make -s build
```
to build the docker image
(note that the config file will be baked into the image).
Use `make -s git-check` to verify that the current working copy is clean and
that no unwanted (or uncommit) files will be included in the image.

If you just want to run the API locally start the container via:
```
docker run -d -p 8080:8080 -t "smartsearch-$(make -s name)"
```

Test the connection via:
```
curl -X POST --json '{"input": "Is London really a place?"}' http://localhost:8080/api/locations
```
