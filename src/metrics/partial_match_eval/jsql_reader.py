from typing import List, Dict, Optional

from src.metrics.partial_match_eval.utils import get_recursively, flatten


class JSQLReader:
    @staticmethod
    def parse_sql_to_parsed_body(parsed_sql: Dict, anonymize_values: bool, parse_on_clause: bool) -> Dict:
        select_bodies = []
        for key, value in parsed_sql.items():
            if key == "selectBody":
                if "selects" in value:
                    for select in value["selects"]:
                        select_bodies.append(select)
                else:
                    select_bodies.append(value)
            elif key == "withItemsList":
                for with_value in parsed_sql["withItemsList"]:
                    select_body = with_value["selectBody"]
                    if "selects" in select_body:
                        for select in select_body["selects"]:
                            select_bodies.append(select)
                    else:
                        select_bodies.append(select_body)

        parsed_dict = {"select_body_{}".format(i): [] for i in range(len(select_bodies))}

        for num, body in enumerate(select_bodies):
            while isinstance(body, list):
                body = body[0]

            body_dict = JSQLReader._get_parse_body(
                body, anonymize_values=anonymize_values, parse_on_clause=parse_on_clause
            )

            parsed_dict["select_body_{}".format(num)].append(body_dict)

        return parsed_dict

    @staticmethod
    def _get_parse_body(body: Dict, anonymize_values: bool, parse_on_clause: bool) -> Dict:
        # select
        select_items = JSQLReader._get_select_items(body.get("selectItems", []), anonymize_values, parse_on_clause)

        # top
        top_items = JSQLReader._get_top_clause(body.get("top", {}), body.get("limit", {}))

        # from
        from_items = JSQLReader._get_from_clause(
            body.get("fromItem", {}), body.get("joins", []), anonymize_values, parse_on_clause
        )

        # where
        where_items = JSQLReader._get_all_where_items(body.get("where"), anonymize_values, parse_on_clause)

        # order by
        order_by_items = JSQLReader._get_all_order_items(
            body.get("orderByElements", []), anonymize_values, parse_on_clause
        )

        # group by
        group_by_items = JSQLReader._get_all_group_by_columns(
            body.get("groupBy", {}), anonymize_values, parse_on_clause
        )

        # having
        having_items = JSQLReader._get_having_items(body.get("having", {}), anonymize_values, parse_on_clause)

        body_dict = {
            "select_items": select_items,
            "top_items": top_items,
            "from_items": from_items,
            "where_items": where_items,
            "order_items": order_by_items,
            "groupby_items": group_by_items,
            "having_items": having_items,
        }
        return body_dict

    # pylint: disable=too-many-branches
    @staticmethod
    def _get_column_items_inner(
        expression: Dict, anonymize_values: bool, parse_on_clause: bool, left_expression: bool
    ) -> List:
        if not expression:
            return []

        items = []

        left_right_items = JSQLReader._get_left_right_expressions(expression, anonymize_values, parse_on_clause)
        if left_right_items:
            items.extend(left_right_items)

        inner_sql_items = JSQLReader._get_items_from_inner_sql(expression, anonymize_values, parse_on_clause)
        if inner_sql_items:
            items.extend(inner_sql_items)

        # add terminals
        if "leftExpression" not in expression and "rightExpression" not in expression:
            column_name = JSQLReader._get_terminal(expression, "columnName")
            if column_name:
                if anonymize_values and not left_expression:
                    items.append("terminal")
                else:
                    items.append(column_name)
            string_expression = JSQLReader._get_terminal(expression, "stringExpression")
            if string_expression:
                if anonymize_values:
                    items.append("terminal")
                else:
                    items.append(string_expression)
            value_value = JSQLReader._get_terminal(expression, "value")
            if value_value:
                if anonymize_values:
                    items.append("terminal")
                else:
                    items.append(value_value)

            if "allColumns" in expression and expression["allColumns"]:
                items.append("*")

        aggregator = JSQLReader._get_aggregator(expression)

        if aggregator:
            items.append(aggregator)

        not_expr = JSQLReader._get_not(expression)

        if not_expr:
            items.append(not_expr)

        return items

    @staticmethod
    def _get_not(expression: Dict) -> Optional[str]:
        not_expr = None
        first_not_expr = expression.get("not", None)
        if first_not_expr:
            if expression["not"]:
                not_expr = "not"
        return not_expr

    @staticmethod
    def _get_aggregator(expression: Dict) -> Optional[str]:
        return expression.get("name", None)

    @staticmethod
    def _get_when_items(expression: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []
        when_clauses = expression.get("whenClauses", [])
        if not when_clauses:
            return []

        for when_clause in when_clauses:
            items.append("case")
            when_expression = when_clause.get("whenExpression", {})
            if when_expression:
                when_expression_items = JSQLReader._get_items_from_expression(
                    when_expression, anonymize_values, parse_on_clause
                )
                items.extend(when_expression_items)
            then_expression = when_clause.get("thenExpression", {})
            if then_expression:
                then_expression_items = JSQLReader._get_items_from_expression(
                    then_expression, anonymize_values, parse_on_clause
                )
                items.extend(then_expression_items)

        return items

    # pylint: disable=too-many-branches
    @staticmethod
    def _get_items_from_expression(expression: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []

        if "parameters" in expression:
            parameters_items = []
            for parameter_expression in expression["parameters"]["expressions"]:
                parameters_items.extend(
                    JSQLReader._get_items_from_expression(parameter_expression, anonymize_values, parse_on_clause)
                )
            column_name = parameters_items
        else:
            column_name = expression.get("columnName")

        if column_name:
            if isinstance(column_name, list):
                if len(column_name) == 1:
                    column_name = column_name[0]
                    items.append(column_name)
                else:
                    items.extend(column_name)
            else:
                items.append(column_name)

        inner_sql_items = JSQLReader._get_items_from_inner_sql(expression, anonymize_values, parse_on_clause)
        items.extend(inner_sql_items)

        when_expressions_items = JSQLReader._get_when_items(expression, anonymize_values, parse_on_clause)
        items.extend(when_expressions_items)

        aggregator = JSQLReader._get_aggregator(expression)
        if aggregator:
            items.append(aggregator)
            if column_name:
                items.append([aggregator, column_name])
            else:
                if "allColumns" in expression and expression["allColumns"]:
                    items.append("*")
                    items.append([aggregator, "*"])
        left_right_expression = JSQLReader._get_left_right_expressions(expression, anonymize_values, parse_on_clause)
        items.extend(left_right_expression)

        if "type" in expression and expression["type"] == "OVER":
            items.append("OVER")
            order_by_items = JSQLReader._get_all_order_items(
                expression.get("orderByElements", []), anonymize_values, parse_on_clause
            )
            if order_by_items:
                items.extend(order_by_items)

        return items

    @staticmethod
    def _get_left_right_expressions(expression: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []

        # leftExpression
        left_expression_items = JSQLReader._get_column_items_inner(
            expression.get("leftExpression"), anonymize_values, parse_on_clause=parse_on_clause, left_expression=True
        )
        if left_expression_items:
            items.extend(left_expression_items)

        # rightExpression
        right_expression_items = JSQLReader._get_column_items_inner(
            expression.get("rightExpression"), anonymize_values, parse_on_clause=parse_on_clause, left_expression=False
        )
        if right_expression_items:
            items.extend(right_expression_items)

        # rightItemsList
        right_items_list_dict = expression.get("rightItemsList", {})
        if right_items_list_dict:
            items.append("IN")
            for right_item_expression in right_items_list_dict.get("expressions", []):
                right_items_expression_items = JSQLReader._get_column_items_inner(
                    right_item_expression, anonymize_values, parse_on_clause=parse_on_clause, left_expression=False
                )
                if right_items_expression_items:
                    items.extend(right_items_expression_items)

        string_expression = expression.get("stringExpression")
        if string_expression:
            items.append(string_expression)
            if left_expression_items and right_expression_items:
                items.append([left_expression_items, right_expression_items, string_expression])

        return items

    @staticmethod
    def _get_column_items(
        select_item: Dict, anonymize_values: bool, parse_on_clause: bool, add_alias: bool = False
    ) -> List:
        if len(select_item.keys()) == 1:  # select * from ..
            return ["*"]

        expression = select_item.get("expression")
        if not expression:
            return []

        items = JSQLReader._get_items_from_expression(expression, anonymize_values, parse_on_clause)

        if "alias" in select_item and select_item["alias"]:
            alias = select_item["alias"]["name"]
            if add_alias:
                items.append(alias)

        return items

    @staticmethod
    def _get_terminal(body: Dict, item: str) -> Optional[str]:
        item = body.get(item)
        if item:
            while isinstance(item, list):
                item = item[0]
            return str(item)
        return None

    # pylint: disable=too-many-nested-blocks
    @staticmethod
    def _get_items_from_inner_sql(expression: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []
        inner_select_body_items = JSQLReader.parse_sql_to_parsed_body(
            expression, anonymize_values=anonymize_values, parse_on_clause=parse_on_clause
        )
        if inner_select_body_items:
            for select_body_list in inner_select_body_items.values():
                select_body_items_dict = select_body_list[0]
                for clause_items in select_body_items_dict.values():
                    if clause_items:
                        items.extend(clause_items)

        return items

    @staticmethod
    def _get_top_clause(top_item: Dict, limit_item: Dict) -> List:
        items = []

        expression = top_item.get("expression")
        if expression:
            if "stringValue" in expression:
                items.append(expression["stringValue"])
            elif "name" in expression:
                items.append(expression["name"])

        # add LIMIT clause
        if limit_item:
            row_count = limit_item["rowCount"]
            items.append(row_count["stringValue"])

        return items

    @staticmethod
    def get_all_tables(parsed: Dict) -> Dict[str, str]:
        alias_to_table_name_dict: Dict[str, str] = {}

        table_items = flatten(get_recursively(parsed, ["fromItem"]))

        join_items = get_recursively(parsed, ["joins"])
        join_items = flatten(join_items)

        for join_item in join_items:
            table_items.extend(flatten(get_recursively(join_item, ["rightItem"])))

        for from_item in table_items:
            table_name = None
            if from_item.get("name"):
                if from_item.get("database"):
                    table_name = from_item.get("name")
            table_alias = None
            if from_item.get("alias", {}).get("name"):
                table_alias = from_item.get("alias", {}).get("name")
            if table_name:
                if not table_alias:
                    table_alias = table_name
                alias_to_table_name_dict[table_alias] = table_name

        return alias_to_table_name_dict

    @staticmethod
    def _get_from_clause(from_dict: Dict, join_list: List, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []

        if "fullyQualifiedName" in from_dict:
            items.append(from_dict["fullyQualifiedName"])
        elif "multipartName" in from_dict:
            items.append(from_dict["multipartName"])
        elif "name" in from_dict:
            items.append(from_dict["name"])

        inner_sql_items = JSQLReader._get_items_from_inner_sql(from_dict, anonymize_values, parse_on_clause)
        items.extend(inner_sql_items)

        join_items = JSQLReader._get_join_clause(join_list, anonymize_values, parse_on_clause)
        if join_items:
            items.extend(join_items)

        if len(items) > 1:
            items.append(items.copy())

        return items

    @staticmethod
    def _get_select_items(select_items: List[Dict], anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []
        for select_item in select_items:
            column_items = JSQLReader._get_column_items(
                select_item, anonymize_values=anonymize_values, parse_on_clause=parse_on_clause
            )
            items.extend(column_items)

        if len(items) > 1:
            items.append(items.copy())

        return items

    @staticmethod
    def _get_items_from_join(join_dict: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []
        if "rightItem" in join_dict:
            right_item = join_dict["rightItem"]
            if "name" in right_item:
                items.append(right_item["name"])

            # inner sql in join
            if "selectBody" in right_item:
                inner_sql_items = JSQLReader._get_items_from_inner_sql(right_item, anonymize_values, parse_on_clause)
                items.extend(inner_sql_items)
        if "onExpression" in join_dict and parse_on_clause:
            on_expression = join_dict["onExpression"]
            left_right_expression = JSQLReader._get_left_right_expressions(
                on_expression, anonymize_values, parse_on_clause
            )
            items.extend(left_right_expression)

            # inner sql in on expression
            if "selectBody" in on_expression:
                inner_sql_items = JSQLReader._get_items_from_inner_sql(on_expression, anonymize_values, parse_on_clause)
                items.extend(inner_sql_items)

        if len(items) > 1:
            items.append(items.copy())

        return items

    @staticmethod
    def _get_join_clause(join_items: List[Dict], anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []
        for join_dict in join_items:
            join_clause_items = JSQLReader._get_items_from_join(join_dict, anonymize_values, parse_on_clause)
            items.extend(join_clause_items)

        return items

    @staticmethod
    def _get_items_from_group_by_expression(group_by_expression: Dict, anonymize_values: bool) -> List:
        items = []

        string_value = group_by_expression.get("stringValue")
        if string_value:
            if anonymize_values:
                items.append(["terminal"])
            else:
                items.append(string_value)

        return items

    @staticmethod
    def _get_all_group_by_columns(group_by_dict: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []

        group_by_expressions = group_by_dict.get("groupByExpressions", [])
        for group_by_expression in group_by_expressions:
            group_by_expression_items = JSQLReader._get_items_from_group_by_expression(
                group_by_expression, anonymize_values
            )
            if group_by_expression_items:
                items.extend(group_by_expression_items)
            group_by_expression_more_items = JSQLReader._get_items_from_expression(
                group_by_expression, anonymize_values, parse_on_clause
            )
            if group_by_expression_more_items:
                items.extend(group_by_expression_more_items)

        if len(items) > 1:
            items.append(items.copy())

        return items

    @staticmethod
    def _get_all_order_items(order_by_elements: List[Dict], anonymize_values: bool, parse_on_clause: bool) -> List:
        items = []
        for order_by_element in order_by_elements:
            expression = order_by_element.get("expression")
            if expression:
                expression_items = JSQLReader._get_items_from_expression(expression, anonymize_values, parse_on_clause)
                if "asc" in order_by_element and order_by_element["asc"]:
                    order = "asc"
                else:
                    order = "desc"
                expression_items.append(order)

                items.extend(expression_items)
                if len(expression_items) > 1:
                    items.append(expression_items)

        if len(items) > 1:
            items.append(items.copy())

        return items

    @staticmethod
    def _get_all_where_items(where_dict: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        if not where_dict:
            return []

        left_right_items = JSQLReader._get_left_right_expressions(where_dict, anonymize_values, parse_on_clause)

        return left_right_items

    @staticmethod
    def _get_having_items(having_dict: Dict, anonymize_values: bool, parse_on_clause: bool) -> List:
        if not having_dict:
            return []

        left_right_items = JSQLReader._get_left_right_expressions(having_dict, anonymize_values, parse_on_clause)

        return left_right_items
