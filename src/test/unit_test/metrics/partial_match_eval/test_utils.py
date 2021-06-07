import unittest


from src.metrics.partial_match_eval.utils import get_item_index_in_list


class TestUtils(unittest.TestCase):
    def test_get_item_index_in_list_only_strings(self):
        index = get_item_index_in_list(["a", "b", "c", "d"], "c")
        self.assertEqual(index, 2)

    def test_get_item_index_in_list_search_contains_simple_list(self):
        index = get_item_index_in_list([["a", "b", "c", ["e", "d"]], "bla", "bla2"], ["c", "b", "a", ["d", "e"]])
        self.assertEqual(index, 0)

    def test_get_item_index_in_list_search_contains_3_level_list(self):
        index = get_item_index_in_list(["bla", "bla2", ["a", [["c", "d"], "b"]]], ["a", ["b", ["c", "d"]]])
        self.assertEqual(index, 2)

    def test_get_item_index_in_list_search_contains_2_lists(self):
        index = get_item_index_in_list(
            ["bla", ["TagName", "MIN", ["MIN", "TagName"], "Owner", "COUNT", "*", ["COUNT", "*"]]],
            ["TagName", "MIN", ["MIN", "TagName"], "Owner", "COUNT", "*", ["COUNT", "*"]],
        )
        self.assertEqual(index, 1)
