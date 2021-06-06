import unittest

from src.metrics.partial_match_eval.evaluate import evaluate
from src.ext_services.jsql_parser import JSQLParser


class TestEvaluate(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = JSQLParser()

    def test_evaluate_simple(self):
        parsed_gold = self.parser.translate("select first_name, last_name from customers")
        parsed_predicted = self.parser.translate("select first_name from customers")
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score >= 0.75)

    def test_evaluate_complex(self):
        parsed_gold = self.parser.translate(
            """
        SELECT  CreationDate, COUNT(*) FROM ReviewTasks
        WHERE ReviewTaskTypeId = 11 and
              CompletedByReviewTaskId is NOT NULL and
              CreationDate > '20200101'
        GROUP BY CreationDate
        """
        )
        parsed_predicted = self.parser.translate(
            """
        SELECT  CreationDate, COUNT(*) FROM ReviewTasks
        WHERE ReviewTaskTypeId = 11 and
              CompletedByReviewTaskId is NOT NULL and
              CreationDate > '20200101'
        GROUP BY CreationDate
        ORDER BY CreationDate
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 0.8)

    def test_evaluate_sub_query(self):
        parsed_gold = self.parser.translate(
            """
        SELECT  B.Name, B.UserId AS [User Link]
        FROM Badges B
        WHERE Class = 1
        AND TagBased = 1
        AND (
            SELECT COUNT(B2.Name) FROM Badges B2
            WHERE B2.Name = B.Name
            AND B2.Class = 1
            AND B2.TagBased = 1
            ) = 1
        GROUP BY B.Name, B.UserId
        ORDER BY B.Name
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT  B.Name, B.UserId AS [User Link]
            FROM Badges B
            WHERE Class = 1
            AND TagBased = 1
            GROUP BY B.Name, B.UserId
            ORDER BY B.Name
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score >= 0.8)

    def test_evaluate_sub_query_sub_query(self):
        parsed_gold = self.parser.translate(
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
        parsed_predicted = self.parser.translate(
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
                                  WHERE a.Score < 0) 
            ORDER BY q.Id DESC
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score >= 0.8)

    def test_evaluate_repetition(self):
        parsed_gold = self.parser.translate(
            """
        SELECT B.Name
        FROM Badges B
        WHERE Class = 1
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT B.Name, B.Name, B.Name, B.Name, B.Name, B.Name, B.Name
            FROM Badges B
            WHERE Class = 1
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score >= 0.74)

    def test_evaluate_top(self):
        parsed_gold = self.parser.translate(
            """
            SELECT TOP 100
                    max(Users.Id) / 10.0 as User_Link,
                    Users.Reputation,
                    Users.CreationDate,
                    (select max(age) from Users) as max_age
            FROM Users
            WHERE Reputation > 10000
            ORDER BY CreationDate DESC
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT  
                TOP 100
                Users.Id as User_Link,
                Users.Reputation,
                Users.CreationDate
            FROM
                Users
            WHERE
                Reputation > 10000
            ORDER BY
                CreationDate DESC
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted], exact_match=False)[0]
        print(score)
        self.assertTrue(score >= 0.85)

    def test_evaluate_with(self):
        parsed_gold = self.parser.translate(
            """
            WITH  nominations as 
            (select row_number() over(order by creationdate asc) num
                  , creationdate
            from posts
            where posttypeid = 6
            )
            
            select *
            from nominations
        """
        )
        parsed_predicted = self.parser.translate(
            """
            WITH  nominations as 
            (select row_number() over(order by creationdate asc) num
                  , creationdate
            from posts
            where posttypeid = 6
            )
            
            select *
            from nominations
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1)

    def test_evaluate_sub_query_in_from(self):
        parsed_gold = self.parser.translate(
            """
            SELECT  TOP 100
                   TagUsers.UserLink AS [User Link],
                   TagUsers.Score AS Score,
                   TagUsers.[Count] AS [Count],
                   (TagUsers.Score + TagUsers.[Count]) / 2.0 AS Total
            FROM
            (
                SELECT a.OwnerUserId AS UserLink,
                       SUM(a.Score) / 10.0 AS Score,
                       COUNT(a.Score) AS [Count]
                FROM Posts a, 
                     Posts q
                     INNER JOIN PostTags pt ON q.Id = pt.PostId
                     INNER JOIN Tags t ON t.Id = pt.TagId
                WHERE a.ParentId = q.Id
                  AND a.PostTypeId = 2
                  AND a.CommunityOwnedDate IS NULL
                  AND t.TagName = '##tagName##'
                GROUP BY a.OwnerUserId
            ) TagUsers
            ORDER BY (TagUsers.Score + TagUsers.[Count]) / 2 DESC
        """
        )
        parsed_predicted = self.parser.translate(
            """
        SELECT  TOP 100
               TagUsers.UserLink AS [User Link],
               TagUsers.Score AS Score,
               TagUsers.[Count] AS [Count],
               (TagUsers.Score + TagUsers.[Count]) / 2.0 AS Total
        FROM
        (
            SELECT a.OwnerUserId AS UserLink,
                   SUM(a.Score) / 10.0 AS Score,
                   COUNT(a.Score) AS [Count]
            FROM Posts a, 
                 Posts q
                 INNER JOIN PostTags pt ON q.Id = pt.PostId
                 INNER JOIN Tags t ON t.Id = pt.TagId
            WHERE a.ParentId = q.Id
              AND a.PostTypeId = 2
            GROUP BY a.OwnerUserId
        ) TagUsers
        ORDER BY (TagUsers.Score + TagUsers.[Count]) / 2 DESC
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score >= 0.9)

    def test_evaluate_top_with_parameter(self):
        parsed_gold = self.parser.translate(
            """
            select top (##Top##) p.id as [post link],
                p.creationdate
            from posts p inner join votes v on v.votetypeid = p.id
                inner join votes v on v.votetypeid = p.id
            where v.votetypeid = 1 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 1 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 2 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 2 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 2 and v.votetypeid = 2 and v.votetypeid = 2
        """
        )
        parsed_predicted = self.parser.translate(
            """
            select top( ##Top## ) p.id as [post link],
                p.creationdate
            from posts p inner join votes v on v.votetypeid = p.id
                inner join votes v on v.votetypeid = p.id
            where v.votetypeid = 1 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 1 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 2 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 2 and v.votetypeid = 2 and v.votetypeid = 2 and
            v.votetypeid = 2 and v.votetypeid = 2 and v.votetypeid = 2
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_wrong_aliases_spider(self):
        parsed_gold = self.parser.translate(
            """
            select avg(capacity) ,  max(capacity) from stadium
        """
        )
        parsed_predicted = self.parser.translate(
            """
            select avg(stadium.average), max(stadium.capacity) from stadium
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score < 1.0)

    def test_evaluate_wrong_joins_spider(self):
        parsed_gold = self.parser.translate(
            """
            select avg(stadium.average), min(singer.age), max(singer.age)
            from stadium join singer join concert on stadium.stadium_id = concert.stadium_id
            join singer_in_concert on concert.concert_id = singer_in_concert.concert_id
                and singer_in_concert.singer_id = singer.singer_id
            where singer.is_male = 'terminal'
        """
        )
        parsed_predicted = self.parser.translate(
            """
            select avg(stadium.average), max(stadium.capacity) from stadium
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score < 1.0)

    def test_evaluate_wrong_aliases_spider_2(self):
        parsed_gold = self.parser.translate(
            """
            select t2.concert_name , t2.theme , count(*)
            from singer_in_concert as t1 join concert as t2 on t1.concert_id = t2.concert_id
            group by t2.concert_id
        """
        )
        parsed_predicted = self.parser.translate(
            """
            select concert.concert_name, concert.theme, count(*)
            from concert join singer_in_concert on concert.concert_id = singer_in_concert.concert_id
            group by concert.concert_id
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)
        score = evaluate([parsed_gold], [parsed_predicted], exact_match=True)[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_case_in_select(self):
        parsed_gold = self.parser.translate(
            """
            SELECT  Id as Post_Link, Votes, Upvotes, Downvotes, Upvotes * 1.0 / Votes
            from
            (SELECT p.Id, count(case when VoteTypeId = 2 then 1 end) as Upvotes,
              count(case when VoteTypeId = 3 then 1 end) AS Downvotes,
              count(case when VoteTypeId = 2 or VoteTypeId = 3 then 1 end) as Votes
            from Posts p inner join Votes v on p.Id = v.PostId
            where p.PostTypeId = 1 and p.ClosedDate is null
            group by p.Id) 
            where Votes > 100 and Upvotes > 0.2 * Votes and Upvotes < 0.8 * Votes
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT  Id as [Post Link], Votes, Upvotes, Downvotes, Upvotes * 1.0 / Votes
            from
            (SELECT p.Id, count(case when VoteTypeId = 2 then 1 end) as [Upvotes],
              count(case when VoteTypeId = 3 then 1 end) AS [Downvotes],
              count(case when VoteTypeId = 2 or VoteTypeId = 3 then 1 end) as [Votes]
            from Posts p inner join Votes v on p.Id = v.PostId
            where p.PostTypeId = 1 and p.ClosedDate is null
            group by p.Id)
            where Votes > 100 and Upvotes > 0.2 * Votes and Upvotes < 0.8 * Votes
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score >= 0.9)

    def test_evaluate_count_star_in_select(self):
        parsed_gold = self.parser.translate(
            """
            SELECT
                TOP 100
                MIN(Tags.TagName) AS TagName,
                Q.OwnerUserId AS [User Link],
                COUNT(*) AS Count
            FROM Posts Q, Posts A, PostTags, Tags
            WHERE A.ParentId = Q.Id AND PostTags.PostId = Q.Id AND Q.OwnerUserId > 0 AND
                Q.OwnerUserId = A.OwnerUserId AND Tags.Id = PostTags.TagId
            GROUP BY PostTags.TagId, Q.OwnerUserId
            ORDER BY Count DESC, Q.OwnerUserId
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT
                TOP 100
                MIN(Tags.TagName) AS TagName,
                Q.OwnerUserId AS [User Link],
                COUNT(*) AS Count
            FROM Posts Q, Posts A, PostTags, Tags
            WHERE A.ParentId = Q.Id AND PostTags.PostId = Q.Id AND Q.OwnerUserId > 0 AND
                Q.OwnerUserId = A.OwnerUserId AND Tags.Id = PostTags.TagId
            GROUP BY PostTags.TagId, Q.OwnerUserId
            ORDER BY Count DESC, Q.OwnerUserId
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_dateformat_in_select(self):
        parsed_gold = self.parser.translate(
            """
           SELECT 
                DATEPART(mm, CreationDate) as mm,
              DATEFROMPARTS(
                DATEPART(yyyy, CreationDate),
                DATEPART(mm, CreationDate),
                1) AS Month,
                COUNT(*) AS Count
            FROM Posts
            WHERE Id IN (
              SELECT MIN(Id) AS Id
              FROM Posts
              WHERE OwnerUserId > 0
              GROUP BY OwnerUserId
            )
            GROUP BY DATEFROMPARTS(
              DATEPART(yyyy, CreationDate),
              DATEPART(mm, CreationDate),
              1)
            ORDER BY Month DESC
        """
        )
        parsed_predicted = self.parser.translate(
            """
           SELECT 
                DATEPART(mm, CreationDate) as mm,
              DATEFROMPARTS(
                DATEPART(yyyy, CreationDate),
                DATEPART(mm, CreationDate),
                1) AS Month,
                COUNT(*) AS Count
            FROM Posts
            WHERE Id IN (
              SELECT MIN(Id) AS Id
              FROM Posts
              WHERE OwnerUserId > 0
              GROUP BY OwnerUserId
            )
            GROUP BY DATEFROMPARTS(
              DATEPART(yyyy, CreationDate),
              DATEPART(mm, CreationDate),
              1)
            ORDER BY Month DESC
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_inner_join(self):
        parsed_gold = self.parser.translate(
            """
            SELECT TOP 200
                ROW_NUMBER() OVER (ORDER BY TagName) AS Rank,
                Users.Id AS User_Link,
                SUM(CASE votes.votetypeid 
                        WHEN 2 THEN 1
                        WHEN 3 THEN -1
                        END) as Tag_score,
                COUNT(DISTINCT(Posts.Id)) AS Number_of_answers
            FROM Tags
                INNER JOIN PostTags ON PostTags.TagId = Tags.id
                INNER JOIN Posts ON Posts.ParentId = PostTags.PostId
                INNER JOIN Users ON Posts.OwnerUserId = Users.Id                
                LEFT OUTER JOIN Votes ON Votes.PostId = Posts.Id
            WHERE Tags.TagName = @tagName
                AND Posts.CommunityOwnedDate IS NULL
            GROUP BY TagName, Users.Id
            ORDER BY 3 DESC
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT TOP 200
                ROW_NUMBER() OVER (ORDER BY TagName) AS Rank,
                Users.Id AS User_Link,
                SUM(CASE votes.votetypeid 
                        WHEN 2 THEN 1
                        WHEN 3 THEN -1
                        END) as Tag_score,
                COUNT(DISTINCT(Posts.Id)) AS Number_of_answers
            FROM Tags
                INNER JOIN PostTags ON PostTags.TagId = Tags.id
                INNER JOIN Posts ON Posts.ParentId = PostTags.PostId
                INNER JOIN Users ON Posts.OwnerUserId = Users.Id                
                LEFT OUTER JOIN Votes ON Votes.PostId = Posts.Id
            WHERE Tags.TagName = @tagName
                AND Posts.CommunityOwnedDate IS NULL
            GROUP BY TagName, Users.Id
            ORDER BY 3 DESC
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_sub_query_in_join(self):
        parsed_gold = self.parser.translate(
            """
            SELECT  TOP 100
                   ROW_NUMBER() OVER(ORDER BY Score DESC) AS '#',
                   us.id User_Link,
                   us.DisplayName,
                   tuser.Score
                   
            FROM Users us
            
            JOIN 
            (SELECT Answers.OwnerUserId AS UserId, SUM(Answers.Score) AS Score
                 FROM Tags 
                JOIN PostTags ON Tags.Id = PostTags.TagId
                JOIN Posts ON Posts.Id = PostTags.PostId  
                JOIN Posts Answers ON Answers.ParentId = Posts.Id 
               WHERE Tags.TagName IN ('amazon-web-services', 'ibm')
              GROUP BY Answers.OwnerUserId
            ) tuser ON tuser.UserId = us.Id
            
            WHERE lower(us.Location) like '%pakistan%'
            OR lower(us.Location) like '%pak%'
            ORDER BY Score DESC;
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT  TOP 100
                   ROW_NUMBER() OVER(ORDER BY Score DESC) AS '#',
                   us.id User_Link,
                   us.DisplayName,
                   tuser.Score
                   
            FROM Users us
            
            JOIN 
            (SELECT Answers.OwnerUserId AS UserId, SUM(Answers.Score) AS Score
                 FROM Tags 
                JOIN PostTags ON Tags.Id = PostTags.TagId
                JOIN Posts ON Posts.Id = PostTags.PostId  
                JOIN Posts Answers ON Answers.ParentId = Posts.Id 
               WHERE Tags.TagName IN ('amazon-web-services', 'ibm')
              GROUP BY Answers.OwnerUserId
            ) tuser ON tuser.UserId = us.Id
            
            WHERE lower(us.Location) like '%pakistan%'
            OR lower(us.Location) like '%pak%'
            ORDER BY Score DESC;
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_sub_query_in_where(self):
        parsed_gold = self.parser.translate(
            """
            SELECT song_name
            FROM singer
            WHERE age  >  50
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT song_name
            FROM singer
            WHERE age  >  (SELECT avg(age) FROM singer)
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score < 1.0)

    def test_evaluate_group_by_simple(self):
        parsed_gold = self.parser.translate(
            """
            SELECT song_name, count(*) FROM singer GROUP BY 1
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT song_name, count(*) FROM singer GROUP BY 1
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_group_by_function(self):
        parsed_gold = self.parser.translate(
            """
            SELECT DATEPART(mm, creation_date), count(*) FROM singer GROUP BY DATEPART(mm, creation_date), 1
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT DATEPART(mm, creation_date), count(*) FROM singer GROUP BY DATEPART(mm, creation_date)
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score < 1.0)

    def test_evaluate_having_simple(self):
        parsed_gold = self.parser.translate(
            """
            SELECT song_name, count(*) FROM singer GROUP BY 1 HAVING count(*) > 5
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT song_name, count(*) FROM singer GROUP BY 1 HAVING count(*) > 5
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_having_complex(self):
        parsed_gold = self.parser.translate(
            """
            SELECT  
              p.Id as PostId,
              p.CreationDate as PostDate,
              p.Title as PostTitle,
              p.Tags as PostTags,
              c.Id as CommentId,
              c.CreationDate as CommentDate
              
            FROM 
              Posts p
              INNER JOIN 
              Comments c
              ON p.Id = c.PostId
              
            WHERE
              p.Title IS NOT NULL AND
              p.Tags IS NOT NULL AND
              p.CreationDate >= '2019-01-01 00:00:00'
              
            GROUP BY
              p.Id,
              p.CreationDate,
              p.Title,
              p.Tags,
              c.Id,
              c.CreationDate
              
            HAVING 
              (c.CreationDate - p.CreationDate) = MIN(c.CreationDate - p.CreationDate)
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT  
              p.Id as PostId,
              p.CreationDate as PostDate,
              p.Title as PostTitle,
              p.Tags as PostTags,
              c.Id as CommentId,
              c.CreationDate as CommentDate
              
            FROM 
              Posts p
              INNER JOIN 
              Comments c
              ON p.Id = c.PostId
              
            WHERE
              p.Title IS NOT NULL AND
              p.Tags IS NOT NULL AND
              p.CreationDate >= '2019-01-01 00:00:00'
              
            GROUP BY
              p.Id,
              p.CreationDate,
              p.Title,
              p.Tags,
              c.Id,
              c.CreationDate
              
            HAVING 
              (c.CreationDate - p.CreationDate) = MIN(c.CreationDate - p.CreationDate)
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_union(self):
        parsed_gold = self.parser.translate(
            """
            SELECT
                year(CreationDate) as y, month(CreationDate) as m, 0 as upvote, 1 as downvote
            from Votes
            where VoteTypeId=3
            union all
            SELECT
                year(CreationDate) as y, month(CreationDate) as m, 1 as upvote, 0 as downvote
            from Votes
            where VoteTypeId=2
        """
        )
        parsed_predicted = self.parser.translate(
            """
            SELECT
                year(CreationDate) as y, month(CreationDate) as m, 0 as upvote, 1 as downvote
            from Votes
            where VoteTypeId=3
            union all
            SELECT
                year(CreationDate) as y, month(CreationDate) as m, 1 as upvote, 0 as downvote
            from Votes
            where VoteTypeId=2
        """
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_anonymize_values(self):
        parsed_gold = self.parser.translate(
            """
            select avg(age) , min(age) , max(age) from singer where country = 'france'
            """,
            anonymize_values=True,
        )
        parsed_predicted = self.parser.translate(
            """
            select avg(singer.age), min(singer.age), max(singer.age) from singer where singer.country = 'terminal'
            """,
            anonymize_values=True,
        )
        score = evaluate([parsed_gold], [parsed_predicted])[0]
        print(score)
        self.assertTrue(score == 1.0)

    def test_evaluate_anonymize_values_greater_than(self):
        parsed_gold = self.parser.translate(
            """
            select name from country where continent = "europe" and population = "80000"
            """,
            anonymize_values=True,
        )
        parsed_predicted = self.parser.translate(
            """
            select country.name from country where country.continent = 'terminal' and country.population > 'terminal'
            """,
            anonymize_values=True,
        )
        score = evaluate([parsed_gold], [parsed_predicted], exact_match=True)[0]
        print(score)
        self.assertTrue(score == 0)

    def test_evaluate_anonymize_values_column_name(self):
        parsed_gold = self.parser.translate(
            """
            select country.region, country.population from country where country.localname = 'terminal'
            """,
            anonymize_values=True,
        )
        parsed_predicted = self.parser.translate(
            """
            select population , region from country where name = "angola"
            """,
            anonymize_values=True,
        )
        score = evaluate([parsed_gold], [parsed_predicted], exact_match=True)[0]
        print(score)
        self.assertTrue(score == 0)

    def test_evaluate_anonymize_values_order_by(self):
        parsed_gold = self.parser.translate(
            """
            select cost_of_treatment from treatments order by date_of_treatment desc limit 1
            """,
            anonymize_values=True,
        )
        parsed_predicted = self.parser.translate(
            """
            select treatments.cost_of_treatment from treatments order by treatments.date_of_treatment asc limit 1
            """,
            anonymize_values=True,
        )
        score = evaluate([parsed_gold], [parsed_predicted], exact_match=True)[0]
        print(score)
        self.assertTrue(score == 0)

    def test_evaluate_anonymize_values_different_limit(self):
        parsed_gold = self.parser.translate(
            """
            select cost_of_treatment from treatments order by date_of_treatment asc limit 1
            """,
            anonymize_values=True,
        )
        parsed_predicted = self.parser.translate(
            """
            select treatments.cost_of_treatment from treatments order by treatments.date_of_treatment asc limit 100
            """,
            anonymize_values=True,
        )
        score = evaluate([parsed_gold], [parsed_predicted], exact_match=True)[0]
        print(score)
        self.assertTrue(score == 0)
