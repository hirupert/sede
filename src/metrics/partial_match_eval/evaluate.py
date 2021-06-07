from typing import Dict, List

from src.metrics.partial_match_eval.utils import get_item_index_in_list


def _get_combined_select_items(parsed: dict) -> dict:
    combined = {}
    for key in parsed.keys():
        select_body_1 = parsed[key][0]
        for select_key, select_value in select_body_1.items():
            if select_key not in combined:
                combined[select_key] = []
            combined[select_key].extend(select_value)
    return combined


# pylint: disable=too-many-branches,too-many-boolean-expressions
def calculate_score(parsed_gold: Dict, parsed_predicted: Dict, exact_match: bool = False) -> float:

    """:arg
    # precision : how many of the words in the predicted occur in reference
    # recall " how many of the words in reference occur in predicted
    F1 = 2 * p * r / (p+r)
    """

    items = [
        "select_items",
        "top_items",
        "from_items",
        "groupby_items",
        "having_items",
        "where_items",
        "order_items",
    ]

    scores = {}
    if len(parsed_gold) > 1:
        combined = _get_combined_select_items(parsed_gold)
        parsed_gold = {"select_body": [combined]}

    if len(parsed_predicted) > 1:
        combined = _get_combined_select_items(parsed_predicted)
        parsed_predicted = {"select_body": [combined]}

    for select_body_gold_list, select_body_predicted_list in zip(parsed_gold.values(), parsed_predicted.values()):
        select_body_gold_dict = select_body_gold_list[0]
        select_body_predicted_dict = select_body_predicted_list[0]
        for item in items:
            if item in select_body_gold_dict and item in select_body_predicted_dict:
                gold_items = select_body_gold_dict[item]
                predicted_items = select_body_predicted_dict[item]

                if not gold_items and not predicted_items:
                    continue

                if (len(gold_items) == 0 and len(predicted_items) != 0) or (
                    len(gold_items) != 0 and len(predicted_items) == 0
                ):
                    scores[item] = 0
                    continue

                temp_precision = 0
                temp_gold_items = gold_items.copy()
                for predicted_item in predicted_items:
                    item_index = get_item_index_in_list(temp_gold_items, predicted_item)
                    if item_index > -1:
                        del temp_gold_items[item_index]
                        temp_precision += 1

                temp_recall = 0.0
                temp_predicted_items = predicted_items.copy()
                for gold_item in gold_items:
                    item_index = get_item_index_in_list(temp_predicted_items, gold_item)
                    if item_index > -1:
                        del temp_predicted_items[item_index]
                        temp_recall += 1

                recall = float(temp_recall) / len(gold_items)
                precision = float(temp_precision) / len(predicted_items)

                if (recall + precision) == 0:
                    f1_score = 0
                else:
                    f1_score = 2 * recall * precision / (recall + precision)
                scores[item] = f1_score
            else:
                continue

    final_score = 0.0
    if scores:
        if exact_match:
            for score in scores.values():
                if score != 1.0:
                    return 0.0
            final_score = 1.0
        else:
            final_score = sum(list(scores.values())) / len(scores.values())

    return final_score


def evaluate(
    parsed_gold: List[Dict],
    parsed_predicted: List[Dict],
    punish_invalid_sql: bool = False,
    exact_match: bool = False,
) -> List[float]:
    """
    :param exact_match: bool
    :param punish_invalid_sql: bool
    :param parsed_gold: List[Dict]
    :param parsed_predicted: List[Dict]
    :return: scores: List[float]
    """
    scores = []
    for gold, predicted in zip(parsed_gold, parsed_predicted):
        # if punish_invalid_sql and (not gold or not predicted):
        #     scores.append(0.0)
        if not gold and not predicted:
            scores.append("JSQLError")
        elif gold and not predicted:  # prediction is invalid
            if punish_invalid_sql:
                scores.append(0.0)
            else:
                scores.append("JSQLError")
        else:
            scores.append(calculate_score(gold, predicted, exact_match=exact_match))
    return scores
