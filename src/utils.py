import os
import re

import ftfy
import numpy as np
from more_itertools import unique_everseen


def preprocess(text: str):

    # normalize non UTF-8 characters to their matching UTF-8 ones
    text = ftfy.fix_text(text)

    text = text.replace("\n", " ")

    # remove redundant whitespaces
    text = re.sub(r" +", " ", text)

    return text.strip()


def split_sql_text(text: str):

    """ Splits SQL code and comment/description at the start of the query. """
    # remove queries that modify the dataset
    if (
        "insert" in text.lower()
        or "update" in text.lower()
        or "delete" in text.lower()
        or "create" in text.lower()
        or "set" in text.lower()
    ):
        return np.nan
    # if declare is present split the query at the first occurrence of DECLARE
    elif "declare" in text.lower():
        pattern = re.compile("declare", re.IGNORECASE)
        text = pattern.sub("DECLARE", text)
        out = text.split("DECLARE", 1)
        try:
            out[1] = "DECLARE " + out[1]
        except IndexError:
            return out[1]
        return out

    # check if it starts with a 'select' or a 'with'
    elif "select" in text.lower() or "with" in text.lower():

        index_s = text.lower().find("select")
        index_w = text.lower().find("with")

        # if it starts with 'with'
        if index_w < index_s and index_w != -1:
            key = "WITH"
        # else it startswith 'select'
        else:
            key = "SELECT"

        pattern = re.compile(key, re.IGNORECASE)
        text = pattern.sub(key, text)
        out = text.split(key, 1)

        try:
            out[1] = key + " " + out[1]
        except IndexError:
            return out[0]
        return out

    else:
        print(text)
        return np.nan


def remove_sql_comm(text: str) -> list:

    """ Removes SQL syntax from query. """

    dir_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(dir_path, "sql_commands.txt"), "r") as file:
        sql_comms = file.readlines()

    sql_comms = [i.replace("\n", "") for i in sql_comms]
    text = text.lower()

    for i in sql_comms:
        if i in text:
            text = text.replace(i, " ")

    return text


def keep_only_unique(text: str) -> str:

    """ Keeps only unique characters in the query(includes table names) """

    items = []
    for token in text.split():
        items.extend(token.split("."))

    return " ".join(list(unique_everseen(items)))
