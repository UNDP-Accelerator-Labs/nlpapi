run `./run_embed.sh` in a different terminal to start the ML backend.

Compute embeddings:
```
python -m nlpapi --config config.json --graph graph_embed.json --input sm_pads.json --output out.csv
```

Fill vector db with embeddings:
```
python -m vecdb --input out.csv --name test:dot --db file://vec.db
```

Querying the db:
```
python -m vecdb --name test:dot --db file://vec.db --config config.json --graph graph_embed.json --query 'food systems'
```
