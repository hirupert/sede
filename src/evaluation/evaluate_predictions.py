import argparse
import re
from functools import partial
from typing import List, Dict

from allennlp.training.metrics import Average

from src.ext_services.jsql_parser import JSQLParser
from src.metrics.bleu.bleu_scorer import BleuScorer
from src.metrics.partial_match_eval.evaluate import evaluate
from src.spider_evaluator import evaluate_single


# pylint: disable=too-many-branches
def calculate_metrics(predictions: str, rat_sql: bool, rat_sql_gap: bool, spider_dev_gold: str):
    predicted_lines: List[str] = []
    gold_lines: List[str] = []

    if rat_sql or rat_sql_gap:
        with open(spider_dev_gold, "r") as in_fp:
            spider_gold_lines = [line.strip() for line in in_fp]
            spider_gold_sqls = [line.split("\t")[0].strip() for line in spider_gold_lines]
            db_ids = [line.split("\t")[1].strip() for line in spider_gold_lines]

        gold_lines = spider_gold_sqls.copy()
        with open(predictions, "r") as in_fp:
            predicted_lines = [line.strip() if "\t" not in line else line.split("\t")[1] for line in in_fp]

    assert len(predicted_lines) == len(gold_lines)
    print(f"Got {len(gold_lines)} queries")

    predicted_lines = [line if line else "a" for line in predicted_lines]
    predicted_lines = [re.sub(r" +", " ", line).lower().strip() for line in predicted_lines]
    gold_lines = [re.sub(r" +", " ", line).lower().strip() for line in gold_lines]

    metrics: Dict[str, float] = {}

    # calculate BLEU score
    blue_scorer = BleuScorer()
    blue_scorer(predicted_lines, gold_lines)
    metrics.update(blue_scorer.get_metric(reset=True))

    # parse queries with JSQL parser
    print("Parsing queries with JSQL parser")
    jsql_parser = JSQLParser.create()
    translated_predicted = jsql_parser.translate_batch(predicted_lines, parse_on_clause=False)
    translated_gold = jsql_parser.translate_batch(gold_lines, parse_on_clause=False)

    # parse queries with JSQL parser
    print("Parsing queries with JSQL parser without values")
    translated_predicted_no_values = jsql_parser.translate_batch(
        predicted_lines, anonymize_values=True, parse_on_clause=False
    )
    translated_gold_no_values = jsql_parser.translate_batch(gold_lines, anonymize_values=True, parse_on_clause=False)

    # calculate percentage of valid SQL queries
    parsable_queries_accuracy = Average()
    for translated_predicted_query in translated_predicted:
        if translated_predicted_query:
            parsable_queries_accuracy(1.0)
        else:
            parsable_queries_accuracy(0.0)

    # calculate PCM-F1
    pcm_f1_metric = Average()
    pcm_f1_scores = evaluate(translated_gold, translated_predicted, punish_invalid_sql=True)
    pcm_f1_scores = [num for num in pcm_f1_scores if isinstance(num, (int, float))]
    if not pcm_f1_scores:
        pcm_f1_metric(0)
    else:
        pcm_f1_metric(sum(pcm_f1_scores) / len(pcm_f1_scores))

    # calculate PCM-F1 no values
    pcm_f1_no_values_metric = Average()
    pcm_f1_no_values_scores = evaluate(
        translated_gold_no_values, translated_predicted_no_values, punish_invalid_sql=True
    )
    pcm_f1_no_values_scores = [num for num in pcm_f1_no_values_scores if isinstance(num, (int, float))]
    if not pcm_f1_no_values_scores:
        pcm_f1_no_values_metric(0)
    else:
        pcm_f1_no_values_metric(sum(pcm_f1_no_values_scores) / len(pcm_f1_no_values_scores))

    # calculate PCM-EM
    pcm_em_metric = Average()
    pcm_em_scores = evaluate(translated_gold, translated_predicted, punish_invalid_sql=True, exact_match=True)
    pcm_em_scores = [num for num in pcm_em_scores if isinstance(num, (int, float))]
    if not pcm_em_scores:
        pcm_em_metric(0)
    else:
        pcm_em_metric(sum(pcm_em_scores) / len(pcm_em_scores))

    # calculate PCM-EM no values
    pcm_em_no_values_metric = Average()
    pcm_em_no_values_scores = evaluate(
        translated_gold_no_values, translated_predicted_no_values, punish_invalid_sql=True, exact_match=True
    )
    pcm_em_no_values_scores = [num for num in pcm_em_no_values_scores if isinstance(num, (int, float))]
    if not pcm_em_scores:
        pcm_em_no_values_metric(0)
    else:
        pcm_em_no_values_metric(sum(pcm_em_no_values_scores) / len(pcm_em_no_values_scores))

    # calculate exact match
    if rat_sql or rat_sql_gap:
        spider_evaluate_func = partial(
            evaluate_single.evaluate, db_dir="data/spider/database", table="data/spider/tables.json"
        )
        exact_match = Average()

        for (
            index,
            (gold, pred, db_id),
        ) in enumerate(zip(gold_lines, predicted_lines, db_ids)):
            correct = int(spider_evaluate_func(gold, pred, db_id))
            exact_match(correct)

            translated_predicted_item = translated_predicted_no_values[index]
            translated_gold_item = translated_gold_no_values[index]
            if translated_predicted_item and translated_gold_item:
                pcm_f1_em_score = evaluate(
                    [translated_gold_item], [translated_predicted_item], punish_invalid_sql=True, exact_match=True
                )[0]
                if correct == 1 and pcm_f1_em_score < 1.0:
                    print("EM is 1 but PCM-EM-NoValues is < 1:\n")
                    print(f"Pred: {pred}")
                    print(f"Gold: {gold}\n")
                if correct == 0 and pcm_f1_em_score == 1.0:
                    print("EM is 0 but PCM-EM-NoValues is 1:\n")
                    print(f"Pred: {pred}")
                    print(f"Gold: {gold}\n")

        metrics["exact_match_accuracy"] = exact_match.get_metric(reset=True)

    metrics["parsable_queries_accuracy"] = parsable_queries_accuracy.get_metric(reset=True)
    metrics["partial_match_f1"] = pcm_f1_metric.get_metric(reset=True)
    metrics["partial_match_f1_no_values"] = pcm_f1_no_values_metric.get_metric(reset=True)
    metrics["partial_match_em"] = pcm_em_metric.get_metric(reset=True)
    metrics["partial_match_no_values_em"] = pcm_em_no_values_metric.get_metric(reset=True)

    print(metrics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=str, help="Predictions file", required=True)
    parser.add_argument("--rat-sql", action="store_true")
    parser.add_argument("--rat-sql-gap", action="store_true")
    parser.add_argument("--spider-dev-gold", type=str, help="Spider dev file", required=False)
    args = parser.parse_args()
    calculate_metrics(args.predictions, args.rat_sql, args.rat_sql_gap, args.spider_dev_gold)
