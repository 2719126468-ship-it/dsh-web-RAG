import json, sys
sys.path.insert(0, '.')
from evaluator import evaluate, DEFAULT_TEST_SET
from retriever import HybridRetriever
retriever = HybridRetriever(use_rerank=True)
result = evaluate(retriever, DEFAULT_TEST_SET)
for i, row in enumerate(result['rows']):
    kw = DEFAULT_TEST_SET[i]['ground_truth_keywords']
    src = row['top1_source'][-40:]
    print(f'Q{i+1}: p={row["context_precision"]} r={row["context_recall"]} top1={src}')
    print(f'     kw={kw}')
    print()
print(f'Summary: precision={result["summary"]["context_precision"]} recall={result["summary"]["context_recall"]}')
