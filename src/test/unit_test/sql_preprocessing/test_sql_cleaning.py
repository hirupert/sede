import unittest

from src.sql_preprocessing.sql_cleaning import clean_sql_query


# pylint: disable=too-many-public-methods
class TestSQLCleaning(unittest.TestCase):
    def test_create(self):
        cleaned_sql = clean_sql_query("create table a_table")
        self.assertTrue(cleaned_sql is None)

    def test_insert(self):
        cleaned_sql = clean_sql_query("insert into a_table values (1, 2, 3)")
        self.assertTrue(cleaned_sql is None)

    def test_no_from(self):
        cleaned_sql = clean_sql_query("select *")
        self.assertTrue(cleaned_sql is None)

    def test_set_time_zone(self):
        cleaned_sql = clean_sql_query(
            "SET TIME ZONE 'UTC'; SELECT " "Domains" "." "name" " AS " "Name" " from " "time" ""
        )
        self.assertEqual(cleaned_sql, "SELECT Domains.name AS Name from time")

    def test_create_temp_table_and_volt_table(self):
        cleaned_sql = clean_sql_query(
            "CREATE TEMP TABLE volt_tt_5b04b2819a291(organization_id, credit_card_billing_country) "
            "AS (SELECT flip.dim_subscriptions.organization_id AS organization_id, "
            "flip.dim_subscriptions.credit_card_billing_country AS credit_card_billing_country "
            "FROM flip.dim_subscriptions WHERE (SELECT volt_tt_5b04b2814c09f.flip AS flip "
            "FROM volt_tt_5b04b2814c09f) = 1) UNION ALL (SELECT flop.dim_subscriptions.organization_id "
            "AS organization_id, flop.dim_subscriptions.credit_card_billing_country AS credit_card_billing_country "
            "FROM flop.dim_subscriptions WHERE (SELECT volt_tt_5b04b2814c09f.flop AS flop "
            "FROM volt_tt_5b04b2814c09f) = 1);"
        )
        self.assertEqual(
            cleaned_sql,
            "(SELECT flip.dim_subscriptions.organization_id AS organization_id, "
            "flip.dim_subscriptions.credit_card_billing_country AS "
            "credit_card_billing_country FROM flip.dim_subscriptions ) "
            "UNION ALL (SELECT flop.dim_subscriptions.organization_id AS "
            "organization_id, flop.dim_subscriptions.credit_card_billing_country "
            "AS credit_card_billing_country FROM flop.dim_subscriptions )",
        )

    def test_admin_flip_flop(self):
        cleaned_sql = clean_sql_query("with admin.flip_flop_switch select * from table")
        self.assertTrue(cleaned_sql is None)

    def test_comments_at_end_of_line(self):
        cleaned_sql = clean_sql_query("SELECT * -- A comment\nFROM table")
        self.assertEqual(cleaned_sql, "SELECT * FROM table")

    def test_comments_in_the_middle_of_query(self):
        cleaned_sql = clean_sql_query("SELECT * -- A comment\nFROM table WHERE /* 1 = 1*/ 2 = 2")
        self.assertEqual(cleaned_sql, "SELECT * FROM table WHERE 2 = 2")

    def test_remove_declare_with_a_new_line(self):
        cleaned_sql = clean_sql_query("DECLARE UserId=123\nSELECT * FROM table WHERE 2 = 2")
        self.assertEqual(cleaned_sql, "SELECT * FROM table WHERE 2 = 2")

    def test_remove_declare_with_command(self):
        cleaned_sql = clean_sql_query("DECLARE UserId=123; SELECT * FROM table WHERE 2 = 2")
        self.assertEqual(cleaned_sql, "SELECT * FROM table WHERE 2 = 2")

    def test_remove_declare_until_select(self):
        cleaned_sql = clean_sql_query("DECLARE UserId=123\nSELECT * FROM table WHERE 2 = 2")
        self.assertEqual(cleaned_sql, "SELECT * FROM table WHERE 2 = 2")

    def test_remove_non_ascii_chars(self):
        cleaned_sql = clean_sql_query("SELECT * FROM table WHERE value = 'ã�aa'")
        self.assertEqual(cleaned_sql, "SELECT * FROM table WHERE value = 'aa'")

    def test_remove_aliases_in_tsql(self):
        cleaned_sql = clean_sql_query("SELECT id as [User Id] FROM table")
        self.assertEqual(cleaned_sql, "SELECT id as user_id FROM table")

    def test_insert_into_hashtag(self):
        cleaned_sql = clean_sql_query("INSERT INTO # (SELECT id as [User Id] FROM table)")
        self.assertTrue(cleaned_sql is None)

    def test_remove_comments_at_end_of_query(self):
        cleaned_sql = clean_sql_query("SELECT id FROM table -- are you sure this is comment?")
        self.assertEqual(cleaned_sql, "SELECT id FROM table")

    def test_remove_long_query(self):
        cleaned_sql = clean_sql_query(f"SELECT id FROM table where value = '{'a a' * 600}'")
        self.assertTrue(cleaned_sql is None)

    def test_multiple_queries(self):
        cleaned_sql = clean_sql_query("SELECT id FROM table; SELECT * from table2;")
        self.assertTrue(cleaned_sql is None)

    def test_not_replace_apostrophes(self):
        cleaned_sql = clean_sql_query('SELECT * FROM table WHERE value = "a"')
        self.assertEqual(cleaned_sql, 'SELECT * FROM table WHERE value = "a"')

    def test_new_lines(self):
        cleaned_sql = clean_sql_query("SELECT *\nFROM table\nWHERE value = a")
        self.assertEqual(cleaned_sql, "SELECT * FROM table WHERE value = a")

    def test_where_not_in(self):
        cleaned_sql = clean_sql_query(
            """select
                t.id as ticket_id,
                t.org_id,
                t.group_id,
                t.created,
                s.stage_name as status,
                `subject`,
                t.`user_id`,
                is_ephemeral,
                modified,
                owner_id,
                tsi.is_analysis_shared,
                tt.name as type,
                tog.name as origin,
                tp.name as priority,
                t.effort,
                t.assisted_by_rupert,
                array_agg(distinct topic ignore nulls) as topics,
                array_agg(distinct topic_type ignore nulls) as topic_types
            from
                prod_rupert_src.mirr_all_tickets t
                left join prod_rupert_src.mirr_all_statuses s on t.org_id = s.org_id
                and t.status_id = s.id
                left join prod_rupert_src.mirr_all_tickets_slack_info tsi on t.org_id = tsi.org_id
                and t.id = tsi.ticket_id
                left join prod_rupert_src.mirr_all_ticket_types tt on t.org_id = tt.org_id
                and t.type_id = tt.id
                left join prod_rupert_src.mirr_all_ticket_origins tog on t.org_id = tog.org_id
                and t.origin_id = tog.id
                left join prod_rupert_src.mirr_all_ticket_priorities tp on t.org_id = tp.org_id
                and t.priority_id = tp.id
            where
                o.organization not in (
                    'WeWork',
                    'Bizzabo',
                    'Dog',
                    'BH90210',
                    'Country Hall of Famers',
                    'Thomas and Co.',
                    'The Muppets',
                    'Superheroes LLC',
                    'Greece Team 2004',
                    'Tennis Bests',
                    'Bark',
                    'Test',
                    'GroundUp',
                    'Juul',
                    'Create',
                    'Covid-19',
                    'Demo',
                    'Rupert',
                    'Dogfood',
                    'test',
                    'Wix'
                )
            group by
                t.id,
                t.org_id,
                t.group_id,
                t.created,
                s.stage_name,
                `subject`,
                t.`user_id`,
                is_ephemeral,
                modified,
                owner_id,
                tsi.is_analysis_shared,
                tt.name,
                tog.name,
                tp.name,
                t.effort,
                t.assisted_by_rupert
            """
        )
        self.assertEqual(
            cleaned_sql,
            "select t.id as ticket_id, t.org_id, t.group_id, t.created, s.stage_name as status, subject, "
            "t.user_id, is_ephemeral, modified, owner_id, tsi.is_analysis_shared, tt.name as type, "
            "tog.name as origin, tp.name as priority, t.effort, t.assisted_by_rupert, "
            "array_agg(distinct topic ignore nulls) as topics, array_agg(distinct topic_type ignore nulls)"
            " as topic_types from prod_rupert_src.mirr_all_tickets t left join prod_rupert_src."
            "mirr_all_statuses s on t.org_id = s.org_id and t.status_id = s.id left join "
            "prod_rupert_src.mirr_all_tickets_slack_info tsi on t.org_id = tsi.org_id and t.id = "
            "tsi.ticket_id left join prod_rupert_src.mirr_all_ticket_types tt on t.org_id = tt.org_id "
            "and t.type_id = tt.id left join prod_rupert_src.mirr_all_ticket_origins tog on t.org_id = "
            "tog.org_id and t.origin_id = tog.id left join prod_rupert_src.mirr_all_ticket_priorities tp "
            "on t.org_id = tp.org_id and t.priority_id = tp.id where o.organization not in "
            "( 'WeWork', 'Bizzabo', 'Dog', 'BH90210', 'Country Hall of Famers', 'Thomas and Co.', "
            "'The Muppets', 'Superheroes LLC', 'Greece Team 2004', 'Tennis Bests', 'Bark', 'Test', "
            "'GroundUp', 'Juul', 'Create', 'Covid-19', 'Demo', 'Rupert', 'Dogfood', 'test', 'Wix' ) "
            "group by t.id, t.org_id, t.group_id, t.created, s.stage_name, subject, t.user_id, "
            "is_ephemeral, modified, owner_id, tsi.is_analysis_shared, tt.name, tog.name, tp.name, "
            "t.effort, t.assisted_by_rupert",
        )

    def test_beginning_with_result_comment(self):
        cleaned_sql = clean_sql_query(
            "----------------------------------------------------------------------------- -- result --------"
            "--------------------------------------------------------------------- SELECT DISTINCT owner_id, "
            "package_id FROM owners_packages_non_free_missing_subscription"
        )
        self.assertEqual(
            cleaned_sql, "SELECT DISTINCT owner_id, package_id FROM owners_packages_non_free_missing_subscription"
        )
