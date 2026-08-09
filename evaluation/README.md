# VerityGraph evaluation

This directory exists to prevent unsupported AI-quality claims.

## Philosophy

A relation rule score is not accuracy and it is not the probability that a statement is true. VerityGraph reports extraction quality only when there is labelled data to compare against.

The first benchmark uses exact normalized triples:

```text
(subject, predicate, object)
```

and reports:

- true positives;
- false positives;
- false negatives;
- precision;
- recall;
- F1.

## Run the starter benchmark

Install the local model and development dependencies:

```bash
pip install -e ".[dev,nlp]"
```

Then run:

```bash
python evaluation/benchmark.py
```

Or persist the report:

```bash
python evaluation/benchmark.py --output evaluation/results/baseline.json
```

## Important limitation

`gold/basic_relations.json` is intentionally tiny. It proves that the evaluation machinery works; it is **not** a representative production benchmark and its score must not be used in a resume, README, investor deck, or product UI as general model accuracy.

The portfolio-quality benchmark will grow into a stratified labelled corpus covering:

- active vs passive voice;
- direct vs prepositional relations;
- multiple entities per sentence;
- cross-sentence references;
- entity aliases;
- organisations, people, locations, products, events, and mixed entity types;
- positive and negative/no-relation examples;
- document, Wikipedia, and public-web source spans;
- difficult parser/NER cases;
- multi-source agreement and contradiction cases.

## Future engine comparison

The same gold data will be used to compare:

| Engine | Precision | Recall | F1 | Latency | Memory | API cost |
|---|---:|---:|---:|---:|---:|---:|
| dependency baseline | measured | measured | measured | measured | measured | 0 |
| optional local LLM | measured | measured | measured | measured | measured | 0 |
| hybrid | measured | measured | measured | measured | measured | 0 |

This makes later model upgrades falsifiable: an extractor is better only when it improves measured behaviour for an acceptable resource trade-off.
