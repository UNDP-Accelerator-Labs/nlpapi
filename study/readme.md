run `./run.sh` in a different terminal to start the ML backend.

run below scripts from the root folder.

Hello World Test:
```
python -m nlpapi --config study/config.json --graph study/graphs/graph_embed.json --input 'hello world' --output -
```

Compute embeddings:
```
python -m nlpapi --config study/config.json --graph study/graphs/graph_embed.json --input @study/sm_pads.json --output study/out.csv
```

Fill vector db with embeddings:
```
python -m vecdb --input @study/out.csv --name test:dot --db file://study/vec.db
```

Querying the db:
```
python -m vecdb --name test:dot --db file://study/vec.db --config study/config.json --graph study/graphs/graph_embed.json --query 'food systems'
```

Gemma:

short benchmark
```
python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input 'tell me about the tallest mountain in the world' --output -
```

long benchmark
```
python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input @study/prompts/extract/test0.txt --output -
```

very long benchmark
```
python -m nlpapi --config study/config.json --graph study/graphs/graph_gemma.json --input @study/prompts/extract/ --output -
```

run all benchmarks:
```
./run.sh &> "run.cpu.$(date +%Y%m%d).log"
./bench.sh &> "bench.cpu.$(date +%Y%m%d).log"
```

LLama:

```
python -m nlpapi --config study/config.json --graph study/graphs/graph_llama.json --input 'today we are baking a chocolate cake' --system-prompt-key 'verify_circular_economy' --output -
```

```
python -m nlpapi --config study/config.json --graph study/graphs/graph_llama.json --input "@study/prompts/ce/ce_test_3.txt" --system-prompt-key 'verify_circular_economy' --output -
```

folder:

```
python -m nlpapi --config study/config.json --graph study/graphs/graph_llama.json --input "@study/prompts/ce/" --system-prompt-key 'verify_circular_economy' --output -
```
