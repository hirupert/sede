import unittest

from src.metrics.partial_match_eval.jsql_reader import JSQLReader
from src.ext_services.jsql_parser import JSQLParser


class TestEvaluate(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = JSQLParser()
        self.jsql_reader = JSQLReader()

    def test_get_all_tables_simple(self):
        parsed = self.parser.parse_sql("select first_name, last_name from customers")
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(customers="customers"))

    def test_get_all_tables_spider_join_alias(self):
        parsed = self.parser.parse_sql(
            """
            select t2.concert_name , t2.theme , count(*)
            from singer_in_concert as t1 join concert as t2 on t1.concert_id = t2.concert_id
            group by t2.concert_id
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(t1="singer_in_concert", t2="concert"))

    def test_get_all_tables_spider_sub_query(self):
        parsed = self.parser.parse_sql(
            """
            SELECT T1.fname,
                   T1.age
            FROM student AS T1
            JOIN has_pet AS T2 ON T1.stuid = T2.stuid
            JOIN pets AS T3 ON T3.petid = T2.petid
            WHERE T3.pettype = 'dog'
              AND T1.stuid NOT IN
                (SELECT T1.stuid
                 FROM student AS T1
                 JOIN has_pet AS T2 ON T1.stuid = T2.stuid
                 JOIN pets AS T3 ON T3.petid = T2.petid
                 WHERE T3.pettype = 'cat')
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(T1="student", T2="has_pet", T3="pets"))

    def test_get_all_tables_sede_no_sub_query(self):
        parsed = self.parser.parse_sql(
            """
            SELECT 
              Tags.TagName,
              AVG(CAST(ViewCount AS BIGINT)) AS AverageViewCount,
              COUNT(Posts.Id) AS QuestionCount 
            FROM Tags
            JOIN PostTags ON Tags.Id = PostTags.TagId
            JOIN Posts ON PostTags.PostId = Posts.Id
            WHERE AcceptedAnswerId IS NOT NULL AND Tags.TagName = '##TagName##'
            GROUP BY Tags.TagName
            ORDER BY AverageViewCount DESC
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(Tags="Tags", PostTags="PostTags", Posts="Posts"))

    def test_get_all_tables_sede_sub_query_same_table_different_aliases(self):
        parsed = self.parser.parse_sql(
            """
            SELECT  q.Id AS [Post Link]
            FROM Posts q 
            WHERE q.PostTypeId = 1 
                  AND q.ClosedDate IS NULL
                  AND q.AcceptedAnswerId IS NULL
                  AND q.AnswerCount > 0
                  AND EXISTS (SELECT a.Id
                              FROM Posts a
                              WHERE a.Score = 0
                                    AND a.ParentId = q.Id)
                  AND NOT EXISTS (SELECT a.Id 
                                  FROM Posts a 
                                  WHERE a.Score > 0 
                                        AND a.ParentId = q.Id) 
            ORDER BY q.Id DESC
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(a="Posts", q="Posts"))

    def test_get_all_tables_sede_sub_query_same_table_different_aliases_2(self):
        parsed = self.parser.parse_sql(
            """
            SELECT  Top 100 
                  p.Id AS [Post Link], 
                  Len(ph.Text) as [Markdown Length],
                  p.Score as [Score]
            From Posts p, PostHistory ph
            Where p.PostTypeId = 2
                  and ph.PostId = p.Id                 -- getting history for the right post
                  and ph.PostHistoryTypeId in (2,5,8)  -- initial body, edit body, rollback body
                  and not exists (                     -- no later revisions of the body
                    SELECT * from PostHistory phtwo
                    Where phtwo.PostId = p.Id
                      and phtwo.PostHistoryTypeId in (2,5,8)
                      and phtwo.CreationDate > ph.CreationDate
                  )
                  and p.OwnerUserId = 26369
            Order By Len(ph.Text) Desc
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(p="Posts", ph="PostHistory", phtwo="PostHistory"))

    def test_get_all_tables_sede_with(self):
        parsed = self.parser.parse_sql(
            """
            WITH  Raw AS (
              SELECT
                OwnerUserId AS UserId,
                COUNT(*) AS Questions
              FROM Posts
              WHERE
                PostTypeId = 1
                AND
                OwnerUserId > 0
              GROUP BY OwnerUserId
              HAVING COUNT(AcceptedAnswerId)=0
            )
            SELECT TOP 100
              Users.Id,
              Users.Id AS [User Link],
              Users.Reputation,
              Raw.Questions
            FROM Raw, Users
            WHERE Raw.UserId = Users.Id
            ORDER BY Users.Reputation DESC, Users.Id
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(Posts="Posts", Raw="Raw", Users="Users"))

    def test_get_all_tables_sede_sub_query_in_from(self):
        parsed = self.parser.parse_sql(
            """
            SELECT  sum(upvote) as totup
            , sum(downvote) as totdown
            ,  sum(upvote) * 5 - sum(downvote) * 2 as score
            from (
               SELECT p.id
               , sum(case when v.votetypeid = 2 then 1 else 0 end) as upvote
               , sum(case when v.votetypeid = 3 then 1 else 0 end) as downvote
               from posts p
               inner join posttags pt on pt.postid = p.id
               inner join tags t on t.id = pt.tagid
               inner join votes v on v.postid = p.id
               where t.tagname= "tag"
               and v.votetypeid in (2,3) -- upvote, downvote
               and p.posttypeid = 1 -- Q 
               group by p.id
            ) as basedata
            """
        )
        tables = self.jsql_reader.get_all_tables(parsed)
        self.assertEqual(tables, dict(p="posts", pt="posttags", t="tags", v="votes"))
