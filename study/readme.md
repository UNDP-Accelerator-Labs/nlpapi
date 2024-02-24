run `./run.sh` in a different terminal to start the ML backend.

run below scripts from the root folder.

Compute embeddings:
```
python -m nlpapi --config study/config.json --graph study/graph_embed.json --input @study/sm_pads.json --output study/out.csv
```

Fill vector db with embeddings:
```
python -m vecdb --input @study/out.csv --name test:dot --db file://study/vec.db
```

Querying the db:
```
python -m vecdb --name test:dot --db file://study/vec.db --config study/config.json --graph study/graph_embed.json --query 'food systems'
```

Gemma:
```
python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input 'how are you?' --output -
```
