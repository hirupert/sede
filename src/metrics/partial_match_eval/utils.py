from typing import List, Union


def get_item_index_in_list(items: List, search_item: Union[str, List]) -> int:
    if isinstance(search_item, str):  # str type
        index = -1
        try:
            index = items.index(search_item)
        except ValueError:
            pass
        return index
    elif isinstance(search_item, list):  # str type
        if all(isinstance(inner_item, str) for inner_item in items):  # we compare a List[str] to List[str]
            for inner_search_item in search_item:
                inner_found_index = get_item_index_in_list(items, inner_search_item)
                if inner_found_index == -1:
                    return -1
            return 0

        for index, item in enumerate(items):
            if not isinstance(item, list):
                continue

            found = False
            for inner_search_item in search_item:
                inner_found_index = get_item_index_in_list(item, inner_search_item)
                if inner_found_index > -1:
                    found = True
            if found:
                return index
            return -1
    else:
        raise ValueError("Value should be of type str or list only")

    return -1


def get_recursively1(search_object, field, search_within_field: bool = False, max_depth=100000):
    """
    Takes a dict with nested lists and dicts,
    and searches all dicts for a key of the field
    provided.
    """
    fields_found = []

    if not search_object or max_depth == 0:
        return fields_found

    if isinstance(search_object, list):
        search_object = {"": search_object}

    for key, value in search_object.items():
        if key == field:
            fields_found.append(value)
            if not search_within_field:
                continue

        if isinstance(value, dict):
            results = get_recursively1(value, field, search_within_field, max_depth - 1)
            for result in results:
                fields_found.append([result])
            # fields_found.append(results)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    more_results = get_recursively1(item, field, search_within_field, max_depth - 1)
                    for another_result in more_results:
                        fields_found.append([another_result])
                    # fields_found.append(more_results)

    return fields_found


# pylint: disable=too-many-nested-blocks,too-many-branches
def _add_object(fields: List[str], fields_found: list, key, value):
    if key in fields:
        if value != "":
            if key == "useCastKeyword":
                fields_found.append("cast")
            elif key == "allColumns":
                fields_found.append("*")
            elif key == "not":
                fields_found.append("not")
            elif isinstance(value, float):
                fields_found.append(str(value).replace('"', ""))
            elif isinstance(value, str):
                fields_found.append(value.replace('"', ""))
            else:
                fields_found.append(value)


def get_recursively(search_object, fields: List[str]):
    """
    Takes a dict with nested lists and dicts,
    and searches all dicts for a key of the field
    provided.
    """
    fields_found = []

    if isinstance(search_object, list):
        search_object = {"": search_object}

    temp_fields = fields.copy()
    if "name" in search_object.keys() and "fullyQualifiedName" in search_object.keys():
        if "name" in fields and "fullyQualifiedName" in fields:
            temp_fields = [item for item in fields if item != "name"]

    for key, value in search_object.items():
        _add_object(temp_fields, fields_found, key, value)

        if isinstance(value, dict):
            results = get_recursively(value, temp_fields)
            try:
                if len(results) > 0:
                    fields_found.append(results)
            except TypeError:
                fields_found.append(results)

        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    more_results = get_recursively(item, temp_fields)
                    try:
                        if len(more_results) > 0:
                            fields_found.append(more_results)
                    except TypeError:
                        fields_found.append(more_results)

    return fields_found


def flatten(lst: list) -> list:
    if not lst:
        return []

    if len(lst) == 1:
        if isinstance(lst[0], list):
            result = flatten(lst[0])
        else:
            result = lst
    elif isinstance(lst[0], list):
        result = flatten(lst[0]) + flatten(lst[1:])
    else:
        result = [lst[0]] + flatten(lst[1:])
    return result


def _get_items_with_depth(lst: list, current_depth: int = 0) -> list:
    items = []
    for item in lst:
        if not isinstance(item, list):
            items.append((current_depth, str(item)))
        else:
            items.extend(_get_items_with_depth(item, current_depth + 1))
    return items


def get_items_with_depth_rec(lst: list) -> list:
    if not lst:
        return []
    return _get_items_with_depth(lst, 0)
