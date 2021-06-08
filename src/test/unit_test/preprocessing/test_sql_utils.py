import json
from collections import Counter

import srsly
import unittest

from src.preprocessing import sql_utils


def _calculate_nesting_level(train_dev_test):
    stats = Counter()
    sql_utils.calculate_nesting_level(train_dev_test, stats)
    sum_of_numbers = sum(number * count for number, count in stats.items())
    count = sum(count for n, count in stats.items())
    mean = sum_of_numbers / count
    return mean


class TestSqlUtils(unittest.TestCase):
    @unittest.skip
    def test_calculate_nesting_level_spider(self):
        with open("data/spider/train_spider.json") as in_fp:
            train_spider = json.load(in_fp)
        with open("data/spider/dev.json") as in_fp:
            dev_spider = json.load(in_fp)
        train_dev_spider = train_spider + dev_spider
        mean = _calculate_nesting_level(train_dev_spider)
        print(f"Spider Avg. SQL depth = {mean}")
        self.assertEqual(round(mean, 2), 1.15)

    def test_calculate_nesting_level_sede(self):
        train_sede = [line for line in srsly.read_jsonl("data/sede/train.jsonl")]
        dev_sede = [line for line in srsly.read_jsonl("data/sede/val.jsonl")]
        test_sede = [line for line in srsly.read_jsonl("data/sede/test.jsonl")]
        train_dev_test = train_sede + dev_sede + test_sede
        mean = _calculate_nesting_level(train_dev_test)
        print(f"SEDE Avg. SQL depth = {mean}")
        self.assertEqual(round(mean, 2), 1.29)

    def test_preprocess_for_jsql(self):
        sql = """
        SELECT    RankNo, 
                 [User Link], 
                 Reputation, 
                 Location
        
        FROM
                 (
                    SELECT Id [User Link], Reputation, Location,
                           DENSE_RANK() OVER (ORDER BY Reputation DESC) RankNo
                    FROM   Users
                    WHERE 
                      (
                       lower(Location) LIKE '%philippines%'
                       
                       --Location LIKE '%##Location##%'
                       
                       --
                       OR lower(Location) LIKE 'baguio city'
                      
                       )   
                          
                    ) derivedtable
        
        WHERE   LEN(Location) > 1  and  RankNo <= ##MaximumRankNo## 
        
        --ORDER    BY RankNo
        ORDER    BY location
        """
        cleaned = sql_utils.preprocess_for_jsql(sql)

        expected = (
            "SELECT RankNo, 'user_link', Reputation, Location "
            "FROM ( SELECT Id 'user_link', Reputation, Location, "
            "DENSE_RANK() OVER (ORDER BY Reputation DESC) RankNo FROM Users "
            "WHERE ( lower(Location) LIKE '%philippines%' "
            "OR lower(Location) LIKE 'baguio city' ) ) derivedtable "
            "WHERE LEN(Location) > 1 and RankNo <= '##MaximumRankNo##' ORDER BY location"
        )
        self.assertEqual(cleaned, expected)
