# Common API scenarios

This file describes some common API scenarios. `<API_TOKEN>` denotes the API
token, `<WRITE_TOKEN>` denotes the write API token, and `<TANUKI>` denotes the
tanuki api token. `<COOKIE>` denotes a platform session cookie.

General server info:
https://nlpapi.sdg-innovation-commons.org/api/version

Status of LLM processing:
https://nlpapi.sdg-innovation-commons.org/api/collection/stats

Check whether a cookie is working:
```
curl -X 'POST' 'https://nlpapi.sdg-innovation-commons.org/api/user' -H 'accept: application/json' -H 'Content-Type: application/json' -H 'Cookie: acclab_platform-session=<COOKIE>' -d '{}'
```
or for short
```
curl --json '{}' -H 'Cookie: acclab_platform-session=<COOKIE>' https://nlpapi.sdg-innovation-commons.org/api/user
```
Below all `curl` commands will use `--json`.

## Add documents to the vector database

Add a full document collection:
```
curl --json '{"token": "<API_TOKEN>",
"write_access": "<WRITE_TOKEN>", "db": "main", "bases": ["blog"]}' https://nlpapi.sdg-innovation-commons.org/api/embed/add
```
Adds all documents from the `blog` base to the `main` database.

Add a single document:
```
curl --json '{"token": "<API_TOKEN>", "write_access": "<WRITE_TOKEN>", "db": "main", "main_id": "blog:17177"}' https://nlpapi.sdg-innovation-commons.org/api/embed/add
```
Adds a single document via main id to the `main` database.

## Handle the processing queue

See status of the processing queue (and other queues and the vector database):
https://nlpapi.sdg-innovation-commons.org/api/info

See errors in the processing queue:
https://nlpapi.sdg-innovation-commons.org/api/queue/error

Requeue errors (after fixing the underlying issue):
```
curl --json '{"token": "<API_TOKEN>", "write_access": "<WRITE_TOKEN>"}' https://nlpapi.sdg-innovation-commons.org/api/queue/requeue
```

Clear the processing queue. This removes errors that can't be fixed. Make sure
to call this endpoint when all processing is done since it also removes active
tasks and queued up tasks:
```
curl -v --json '{"token": "<API_TOKEN>", "write_access": "<WRITE_TOKEN>", "tanuki": "<TANUKI>", "clear_process_queue": true}' https://acclabs-nlpapi.azurewebsites.net/api/clear
```

## Add a tag group clustering

Add a tag group clustering with 100 clusters:
```
curl --json '{"token": "<API_TOKEN>", "write_access": "<WRITE_TOKEN>", "name": "my_little_tag_group_5", "bases": ["solution", "actionplan", "experiment", "blog"], "cluster_args": {"n_clusters": 100, "distance_threshold": null}, "is_updating": true}' https://nlpapi.sdg-innovation-commons.org/api/tags/create
```
The name must be unique but can be `null` to automatically generate. This creates
a clustering based on the specified bases. Set `is_updating` to False to experiment with
different settings without updating all platforms' tables.

## Explore the tag group clustering

Get the latest clusters:
```
curl --json '{}' https://nlpapi.sdg-innovation-commons.org/api/tags/clusters
```
You can specify a tag group name:
```
curl --json '{"name": "my_little_tag_group_5"}' https://nlpapi.sdg-innovation-commons.org/api/tags/clusters
```
or a tag group:
```
curl --json '{"tag_group": 123}' https://nlpapi.sdg-innovation-commons.org/api/tags/clusters
```
The output contains the tag group id. Keep this around for other endpoints.

Get clusters for given documents:
```
curl --json '{"main_ids": ["solution:5966", "solution:5967"], "tag_group": 7}' https://nlpapi.sdg-innovation-commons.org/api/tags/list
```

Get documents for given clusters:
```
curl --json '{"tag_group": 10, "cluster": "vaccination"}' https://nlpapi.sdg-innovation-commons.org/api/tags/docs
```

## Inspect documents

Get title and url of a single document:
```
curl --json '{"main_id": "solution:7228"}' https://nlpapi.sdg-innovation-commons.org/api/documents/info
```
If documents return the error `no access` provide a cookie:
```
curl -H 'Cookie: acclab_platform-session=<COOKIE>' --json '{"main_id": "solution:3124"}' https://nlpapi.sdg-innovation-commons.org/api/documents/info
```
You can bulk retrieve results:
```
curl --json '{"main_ids": ["solution:7228", "solution:3124"]}' https://nlpapi.sdg-innovation-commons.org/api/documents/infos
```
(You can provide cookies here, too).

Get the full text of a document as seen by internal processing:
```
curl -H 'Cookie: acclab_platform-session=<COOKIE>' --json '{"main_id": "solution:5677"}' https://nlpapi.sdg-innovation-commons.org/api/documents/fulltext
```
