import re
from collections import Counter
from typing import Optional, List

ALIAS_PATTERN = re.compile(r"\[([^\]]+)]", re.MULTILINE | re.IGNORECASE)
TAGS_PATTERN = re.compile(r"([^'%])(##[a-z0-9_?:]+##)([^'%]?)", re.MULTILINE | re.IGNORECASE)
TOP_TAGS_PATTERN = re.compile(
    r"(top|percentile_cont)([ ]+)?[\(]?[ ]?(##[a-z0-9_]+(:[a-z]+)?(\?([0-9.]+))?##)[ ]?[\)]?", re.IGNORECASE
)


def _remove_comment_at_beginning(cleaned_query: str) -> str:
    return re.sub(r"^([- ]+|(result))+", "", cleaned_query, re.MULTILINE)


def remove_comments(sql: str) -> str:
    # remove comments at the beginning of line
    sql = _remove_comment_at_beginning(sql)

    # remove comments at the end of lines
    sql = re.sub(r"--(.+)?\n", "", sql)

    # remove comments at the end of lines
    sql = re.sub(r"\n;\n", " ", sql)

    sql = re.sub(" +", " ", sql)

    return sql.strip()


def remove_comments_after_removing_new_lines(sql: str) -> str:
    # remove comments at the end of the query
    sql = re.sub(r"--(.?)+$", "", sql, re.MULTILINE)

    # remove comments like /* a comment */
    sql = re.sub(r"/\*[^*/]+\*/", "", sql, re.MULTILINE)

    sql = re.sub(" +", " ", sql)

    return sql.strip()


def _surrounded_by_apostrophes(sql: str, start_index: int, end_index: int) -> bool:
    max_steps = 10

    starts_with_apostrophe = False
    step_count = 0
    while start_index >= 0 and step_count < max_steps:
        if sql[start_index] == "'":
            starts_with_apostrophe = True
            break
        if sql[start_index] == " ":
            starts_with_apostrophe = False
            break
        start_index -= 1
        step_count += 1

    end_with_apostrophe = False
    step_count = 0
    while end_index < len(sql) and step_count < max_steps:
        if sql[end_index] == "'":
            end_with_apostrophe = True
            break
        if sql[end_index] == " ":
            end_with_apostrophe = False
            break
        end_index += 1
        step_count += 1

    return starts_with_apostrophe and end_with_apostrophe


# pylint: disable=too-many-branches
def preprocess_for_jsql(sql: str) -> Optional[str]:
    # replace all alias like "as [User Id]" to "as 'user_id'"
    match = re.search(ALIAS_PATTERN, sql)
    while match is not None:
        group_one = match.group(1)
        if not _surrounded_by_apostrophes(sql, match.start(), match.end()):
            new_alias = f"'{group_one.lower()}'"
        else:
            new_alias = group_one.lower()

        if " " in new_alias:
            new_alias = new_alias.replace(" ", "_")
        sql = sql.replace(match.group(0), new_alias)
        match = re.search(ALIAS_PATTERN, sql)

    # replace all parameters like "TOP ##topn:int?200##" to "TOP 200"
    match = re.search(TOP_TAGS_PATTERN, sql)
    while match is not None:
        group_zero = match.group(0)
        default_number = match.group(6)

        if default_number is not None:
            new_alias = f"{match.group(1)} ({default_number})"
        else:
            new_alias = f"{match.group(1)} (100)"

        sql = sql.replace(group_zero, new_alias)
        match = re.search(TOP_TAGS_PATTERN, sql)

    # replace all parameters like ##tagName:Java## to '##tagName:Java##'
    new_sql = ""
    match = re.search(TAGS_PATTERN, sql)
    while match is not None:
        group_two = match.group(2)

        if not _surrounded_by_apostrophes(sql, match.start(), match.end()):
            new_alias = f"{match.group(1)}'{group_two}'{match.group(3)}"
            new_sql = new_sql + sql[0 : match.start()] + new_alias
        else:
            new_sql = new_sql + sql[0 : match.start()] + match.group(0)

        sql = sql[match.end() :]
        match = re.search(TAGS_PATTERN, sql)
    if sql:
        new_sql = new_sql + sql
    sql = new_sql

    # convert FORMAT function to CONVERT function to support JSQL
    sql = re.sub(r" format\(", " convert(", sql, flags=re.IGNORECASE)

    # remove comments from SQL
    sql = remove_comments(sql)

    # replace N'%Kitchener%' with '%Kitchener%'
    sql = re.sub(r" N'", " '", sql, re.IGNORECASE)

    # remove declares with a new line
    sql = re.sub(r"(DECLARE|declare) [^\n]+\n", " ", sql, re.IGNORECASE | re.MULTILINE | re.DOTALL)

    # remove new lines
    sql = re.sub(r"[\n\t\r]+", " ", sql)

    sql = remove_comments_after_removing_new_lines(sql)

    # remove declares
    sql = re.sub(r"(DECLARE|declare) [^;]+;", " ", sql, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    sql = re.sub(r"(DECLARE|declare) (?:.(?!(SELECT|select)))", "SELECT", sql)

    if "))))))))))))))))))))" in sql or "((((((((((((((((((((" in sql:
        return None

    if "cast(avg(cast(avg(cast(avg(cast(avg(cast(avg(cast(avg(cast(avg(" in sql:
        return None

    sql = re.sub(r"[^\x00-\x7f]", r" ", sql)
    sql = re.sub(r"``", r"'", sql)
    sql = re.sub(r"\"", r"'", sql)
    sql = re.sub(r" +", " ", sql).strip()

    if not sql:
        return None

    if sql[-1] == ";":
        sql = sql[0:-1]

    if ";" in sql:
        sql = sql.split(";")[-1]

    return sql


# pylint: disable=bare-except
def is_number(value, positive=False):
    try:
        float_value = float(value)
        if positive and float_value < 0.0:
            return False
        return True
    except:
        return False


def anonymize_values(tokens):
    new_tokens = []
    is_string_value = False
    copied_string_value = False
    for i, tok in enumerate(tokens):
        tok = tok.replace("`", "'").replace('"', "'")
        if tok.startswith("'"):
            is_string_value = not is_string_value
            copied_string_value = False
        # every string value will be inside apostrophes
        if is_string_value:
            if not copied_string_value:
                new_tokens.append("'value'")
            copied_string_value = True
        elif is_number(tok):
            # we don't want to replace number with 'value' if it's part of LIMIT or OFFSET
            if i - 1 >= 0 and tokens[i - 1].lower() in ["limit", "offset"]:
                new_tokens.append(tok)
            else:
                new_tokens.append("'value'")
        else:
            if tok != "'":
                new_tokens.append(tok)

        if tok.endswith("'") and len(tok) > 1:
            is_string_value = False
            copied_string_value = False
    return new_tokens


def update_quotes(char, in_single, in_double):
    """
    Taken from: https://github.com/jkkummerfeld/text2sql-data
    :param char:
    :param in_single:
    :param in_double:
    :return:
    """
    if char == '"' and not in_single:
        in_double = not in_double
    elif char == "'" and not in_double:
        in_single = not in_single
    return in_single, in_double


# pylint: disable=too-many-branches
def standardise_blank_spaces(query):
    """
    Taken from: https://github.com/jkkummerfeld/text2sql-data
    :param query:
    :return:
    """
    # split on special characters except _.:-
    in_squote, in_dquote = False, False
    tmp_query = []
    pos = 0
    while pos < len(query):
        char = query[pos]
        pos += 1
        # Handle whether we are in quotes
        if char in ["'", '"']:
            if not (in_squote or in_dquote):
                tmp_query.append(" ")
            in_squote, in_dquote = update_quotes(char, in_squote, in_dquote)
            tmp_query.append(char)
            if not (in_squote or in_dquote):
                tmp_query.append(" ")
        elif in_squote or in_dquote:
            tmp_query.append(char)
        elif char in "!=<>,;()[]{}+*/\\#":
            tmp_query.append(" ")
            tmp_query.append(char)
            while pos < len(query) and query[pos] in "!=<>+*" and char in "!=<>+*":
                tmp_query.append(query[pos])
                pos += 1
            tmp_query.append(" ")
        else:
            tmp_query.append(char)
    new_query = "".join(tmp_query)

    # Remove blank spaces just inside quotes:
    tmp_query = []
    in_squote, in_dquote = False, False
    prev = None
    prev2 = None
    for char in new_query:
        skip = False
        for quote, symbol in [(in_squote, "'"), (in_dquote, '"')]:
            if quote:
                if char in " \n" and prev == symbol:
                    skip = True
                    break
                if char in " \n" and prev == "%" and prev2 == symbol:
                    skip = True
                    break
                if char == symbol and prev in " \n":
                    tmp_query.pop()
                elif char == symbol and prev == "%" and prev2 in " \n":
                    tmp_query.pop(len(tmp_query) - 2)
        if skip:
            continue

        in_squote, in_dquote = update_quotes(char, in_squote, in_dquote)
        tmp_query.append(char)
        prev2 = prev
        prev = char
    new_query = "".join(tmp_query)

    # Replace single quotes with double quotes where possible
    tmp_query = []
    in_squote, in_dquote = False, False
    pos = 0
    while pos < len(new_query):
        char = new_query[pos]
        if (not in_dquote) and char == "'":
            to_add = [char]
            pos += 1
            saw_double = False
            while pos < len(new_query):
                tchar = new_query[pos]
                if tchar == '"':
                    saw_double = True
                to_add.append(tchar)
                if tchar == "'":
                    break
                pos += 1
            if not saw_double:
                to_add[0] = '"'
                to_add[-1] = '"'
            tmp_query.append("".join(to_add))
        else:
            tmp_query.append(char)

        in_squote, in_dquote = update_quotes(char, in_squote, in_dquote)

        pos += 1
    new_query = "".join(tmp_query)

    # remove repeated blank spaces
    new_query = " ".join(new_query.split())

    # Remove spaces that would break SQL functions
    new_query = "COUNT(".join(new_query.split("count ("))
    new_query = "LOWER(".join(new_query.split("lower ("))
    new_query = "MAX(".join(new_query.split("max ("))
    new_query = "MIN(".join(new_query.split("min ("))
    new_query = "SUM(".join(new_query.split("sum ("))
    new_query = "COUNT(".join(new_query.split("COUNT ("))
    new_query = "LOWER(".join(new_query.split("LOWER ("))
    new_query = "MAX(".join(new_query.split("MAX ("))
    new_query = "MIN(".join(new_query.split("MIN ("))
    new_query = "SUM(".join(new_query.split("SUM ("))
    new_query = "COUNT( *".join(new_query.split("COUNT(*"))
    new_query = "YEAR(CURDATE())".join(new_query.split("YEAR ( CURDATE ( ) )"))

    return new_query


def update_in_quote(in_quote, token):
    """
    Taken from: https://github.com/jkkummerfeld/text2sql-data
    :param in_quote:
    :param token:
    :return:
    """
    if '"' in token and len(token.split('"')) % 2 == 0:
        in_quote[0] = not in_quote[0]
    if "'" in token and len(token.split("'")) % 2 == 0:
        in_quote[1] = not in_quote[1]


# pylint: disable=too-many-branches,unsupported-membership-test
def calculate_nesting_level(train_dev_test: List, stats: Counter):
    """
    Taken from: https://github.com/jkkummerfeld/text2sql-data
    :param train_dev_test:
    :param stats:
    :return:
    """
    for sample in train_dev_test:
        try:
            if "query" in sample:
                sql = sample["query"]
            elif "QueryBody" in sample:
                sql = sample["QueryBody"]
            else:
                raise ValueError("Found no SQL in example")

            sql = standardise_blank_spaces(sql)
            max_depth = 0
            max_breadth = 1
            depth = 0
            prev = None
            other_bracket = []
            breadth = [0]
            in_quote = [False, False]
            for token in sql.split():
                if in_quote[0] or in_quote[1]:
                    update_in_quote(in_quote, token)
                elif token == "SELECT":
                    depth += 1
                    max_depth = max(max_depth, depth)
                    other_bracket.append(0)
                    breadth[-1] += 1
                    breadth.append(0)
                elif prev is not None and "(" in prev:
                    other_bracket[-1] += 1
                    update_in_quote(in_quote, token)
                elif token == ")":
                    if other_bracket[-1] == 0:
                        depth -= 1
                        other_bracket.pop()
                        possible = breadth.pop()
                        max_breadth = max(max_breadth, possible)
                    else:
                        other_bracket[-1] -= 1
                else:
                    update_in_quote(in_quote, token)

                if "(" in token and ")" in token:
                    prev = "SQL_FUNCTION"
                else:
                    prev = token
            stats[max_depth] += 1
        except IndexError:
            pass


def tokenize_sql(query):
    """
    Taken from: https://github.com/jkkummerfeld/text2sql-data
    :param query:
    :return:
    """
    tokens = []
    in_squote, in_dquote = False, False
    for token in query.split():
        # Handle prefixes
        if not (in_squote or in_dquote):
            if token.startswith("'%") or token.startswith('"%'):
                if token[0] == "'":
                    in_squote = True
                else:
                    in_dquote = True
                tokens.append(token[:2])
                token = token[2:]
            elif token.startswith("'") or token.startswith('"'):
                if token[0] == "'":
                    in_squote = True
                else:
                    in_dquote = True
                tokens.append(token[0])
                token = token[1:]

        # Handle mid-token aliases
        if not (in_squote or in_dquote):
            parts = token.split(".")
            if len(parts) == 2:
                table = parts[0]
                field = parts[1]
                if "alias" in table:
                    table_parts = table.split("alias")
                    tokens.append("alias".join(table_parts[:-1]))
                    tokens.append("alias" + table_parts[-1])
                else:
                    tokens.append(table)
                tokens.append(".")
                token = field

        # Handle aliases without field name.
        if not (in_squote or in_dquote):
            match = re.search(r"(?P<table>[A-Z_]+)(?P<alias>alias\d+)", token)
            if match:
                tokens.append(match.group("table"))
                tokens.append(match.group("alias"))
                continue

        # Handle suffixes
        if (in_squote and token.endswith("%'")) or (in_dquote and token.endswith('%"')):
            tokens.append(token[:-2])
            tokens.append(token[-2:])
        elif (in_squote and token.endswith("'")) or (in_dquote and token.endswith('"')):
            tokens.append(token[:-1])
            tokens.append(token[-1])
        elif (not (in_squote or in_dquote)) and len(token) > 1 and token.endswith("("):
            tokens.append(token[:-1])
            tokens.append(token[-1])
        else:
            tokens.append(token)
        in_squote, in_dquote = update_quotes(token, in_squote, in_dquote)

    return " ".join(tokens)
