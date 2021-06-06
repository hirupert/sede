import re
from typing import Union

import ftfy


MAX_LENGTH = 510


def _preprocess(text: str) -> str:

    # normalize non UTF-8 characters to their matching UTF-8 ones
    text = ftfy.fix_text(text)

    text = re.sub(r"`", "", text)

    # remove non ASCII characters
    text = re.sub(r"[^\x00-\x7f]", r"", text)

    text = re.sub(r"[\n\t\r]+", " ", text)

    # replace all alias like "as [User Id]" to "as user_id"
    alias_pattern = re.compile(r"\[([^\]]+)]", re.MULTILINE)
    match = re.search(alias_pattern, text)
    while match is not None:
        group_one = match.group(1)
        new_alias = group_one.lower().replace(" ", "_")
        text = text.replace(match.group(0), new_alias)
        match = re.search(alias_pattern, text)

    # remove redundant whitespaces
    text = re.sub(r" +", " ", text)

    return text.strip()


def _clean_volt_where_clause(cleaned_query: str) -> str:
    volt_where_pattern = re.compile(
        r"(where|and) \(select volt_tt_[a-z0-9]+\.fl[i|o]p as fl[i|o]p " r"from volt_tt_[a-z0-9]+\) = 1( and)?",
        re.MULTILINE | re.IGNORECASE,
    )
    match = re.search(volt_where_pattern, cleaned_query)
    while match is not None:
        group_where = match.group(1).lower()
        if group_where == "and":  # case of AND
            cleaned_query = cleaned_query.replace(match.group(0), "")
        else:
            if match.group(2) is not None:  # case of WHERE ... AND
                cleaned_query = cleaned_query.replace(match.group(0), "WHERE")
            else:  # case of WHERE without AND
                cleaned_query = cleaned_query.replace(match.group(0), "")
        match = re.search(volt_where_pattern, cleaned_query)
    return re.sub(r" +", " ", cleaned_query).strip()


def _remove_comment_at_beginning(cleaned_query: str) -> str:
    return re.sub(r"^([- ]+|(result))+", "", cleaned_query, re.MULTILINE)


# pylint: disable=too-many-return-statements,too-many-branches
def clean_sql_query(query: str, max_length: int = MAX_LENGTH) -> Union[str, None]:
    if not query:
        return None

    cleaned_query = re.sub(r"(SET TIME ZONE|set time zone) '([^;]+)';", "", query, flags=re.IGNORECASE)

    if "LTRIM( REPLACE( REPLACE( REPLACE( REPLACE( REPLACE( REPLACE( REPLACE( REPLACE(" in query:
        return None

    if "replace(ltrim(rtrim(replace(RTRIM(LTRIM(REPLACE(REPLACE" in query:
        return None

    lower_text = cleaned_query.lower()

    if re.search(r"\b(select)\b", lower_text) is None:
        return None

    if re.search(r"\b(from)\b", lower_text) is None:
        return None

    # if the query starts with a temp table
    if lower_text.startswith("create temp table"):
        select_index = lower_text.index("select")
        if cleaned_query[select_index - 1] == "(":
            select_index -= 1
        cleaned_query = cleaned_query[select_index:]

    cleaned_query = _clean_volt_where_clause(cleaned_query)

    lower_text = cleaned_query.lower()

    if re.search(r"\b(insert|update|delete|create|set)\b", lower_text) is not None:
        if re.search(r"[`'\"](insert|update|delete|create|set)[`'\"]", lower_text) is None:
            return None

    if "admin.flip_flop_switch" in lower_text or lower_text.startswith("padb_fetch_sample:"):
        return None

    # remove comments at the beginning of line
    cleaned_query = _remove_comment_at_beginning(cleaned_query)

    # remove comments at the end of lines
    cleaned_query = re.sub(r"--(.+)\n", "", cleaned_query)

    # remove declares with a new line
    cleaned_query = re.sub(r"(DECLARE|declare) [^\n]+\n", " ", cleaned_query, re.IGNORECASE | re.MULTILINE | re.DOTALL)

    cleaned_query = _preprocess(cleaned_query)

    if "into #" in cleaned_query or "INTO #" in cleaned_query:
        return None

    # remove declares
    cleaned_query = re.sub(r"(DECLARE|declare) [^;]+;", " ", cleaned_query, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    cleaned_query = re.sub(r"(DECLARE|declare) (?:.(?!(SELECT|select)))", "SELECT", cleaned_query)

    # remove comments at the end of the query
    cleaned_query = re.sub(r"--(.?)+$", "", cleaned_query, re.MULTILINE)

    # remove comments like /* a comment */
    cleaned_query = re.sub(r"/\*[^*/]+\*/", "", cleaned_query, re.MULTILINE)

    cleaned_query = re.sub(r" +", " ", cleaned_query).strip()

    # remove long sequences
    tokens = cleaned_query.split()
    if len(tokens) > max_length:
        return None

    cleaned_query = cleaned_query.strip()

    # clear ending ;
    if cleaned_query.endswith(";"):
        cleaned_query = cleaned_query[0:-1]

    # multiple queries
    if ";" in cleaned_query:
        return None

    cleaned_query = cleaned_query.strip()

    return cleaned_query
