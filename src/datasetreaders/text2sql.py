import json
import logging
import os
from random import Random
from typing import Dict, Optional, Iterable, List

import srsly
from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from allennlp.data.fields import TextField, MetadataField
from allennlp.data.instance import Instance
from allennlp.data.token_indexers import TokenIndexer, SingleIdTokenIndexer
from allennlp.data.tokenizers import Tokenizer, SpacyTokenizer, Token
from overrides import overrides

from src.data_classes.data_classes import AnnotatedSQL
from src.ext_services.jsql_parser import JSQLParser
from src.preprocessing.preprocess import clean_str, add_schema_description, SQL_TOKENS
from src.preprocessing.sql_utils import anonymize_values
from src.preprocessing.sql_utils import preprocess_for_jsql

logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes,too-many-arguments
@DatasetReader.register("text2sql")
class Seq2SeqDatasetReader(DatasetReader):
    def __init__(
        self,
        dataset_name: str,
        tables_file_path: str,
        train_data_files=None,
        source_tokenizer: Tokenizer = None,
        target_tokenizer: Tokenizer = None,
        source_token_indexers: Dict[str, TokenIndexer] = None,
        target_token_indexers: Dict[str, TokenIndexer] = None,
        source_max_tokens: Optional[int] = None,
        target_max_tokens: Optional[int] = None,
        shuffle_schema: bool = False,
        use_schema: bool = True,
        start_symbol: str = "<s>",
        end_symbol: str = "</s>",
        source_add_start_token: bool = False,
        source_add_end_token: bool = False,
        target_add_start_token: bool = True,
        target_add_end_token: bool = False,
        truncate_long_sequences_in_train: bool = None,
        uncased: bool = None,
        add_column_types: bool = False,
        keep_sql_values: bool = True,
        upper_sql: bool = False,
        use_description: bool = False,
        replace_column_underscore: bool = True,
        filter_failed_parsed: bool = True,
        random_seed: Optional[int] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        if train_data_files is None:
            train_data_files = []
        self._train_data_files = train_data_files

        with open(tables_file_path) as in_fp:
            self._tables_json = json.load(in_fp)

        self._dataset_name = dataset_name

        self._source_tokenizer = source_tokenizer or SpacyTokenizer()
        self._target_tokenizer = target_tokenizer or self._source_tokenizer
        self._source_token_indexers = source_token_indexers or {"tokens": SingleIdTokenIndexer()}
        self._target_token_indexers = target_token_indexers or self._source_token_indexers

        self._start_token: Optional[Token] = None
        self._end_token: Optional[Token] = None

        self._truncate_long_sequences_in_train = (
            False if truncate_long_sequences_in_train is None else truncate_long_sequences_in_train
        )
        logger.info("truncate_long_sequences_in_train=%s", str(self._truncate_long_sequences_in_train))
        self._truncate_long_sequences = True

        self._uncased = True if uncased is None else uncased
        logger.info("uncased=%s", str(self._uncased))

        self._source_max_tokens = source_max_tokens
        self._target_max_tokens = target_max_tokens
        self._source_max_truncated = 0
        self._target_max_truncated = 0
        self._target_max_skipped = 0
        self._invalid_cleaning_sql_count = 0
        self._invalid_parsing_sql_count = 0

        self._start_symbol = start_symbol
        self._end_symbol = end_symbol
        self._source_add_start_token = source_add_start_token
        self._source_add_end_token = source_add_end_token
        self._target_add_start_token = target_add_start_token
        self._target_add_end_token = target_add_end_token

        self._random_seed = random_seed
        self._shuffle_schema = shuffle_schema
        self._use_schema = use_schema

        self._add_column_types = add_column_types
        self._keep_sql_values = keep_sql_values
        self._upper_sql = upper_sql

        self._replace_column_underscore = replace_column_underscore

        self._use_description = use_description

        self._filter_failed_parsed = filter_failed_parsed

        self._random = Random(random_seed)

        self._sql_parser = JSQLParser()

    @overrides
    def _read(self, file_path: str) -> Iterable[Instance]:
        # Reset truncated/skipped counts
        self._source_max_truncated = 0
        self._target_max_truncated = 0
        self._target_max_skipped = 0
        self._invalid_cleaning_sql_count = 0
        self._invalid_parsing_sql_count = 0

        is_train = os.path.isdir(file_path)

        self._truncate_long_sequences = True
        if is_train and not self._truncate_long_sequences_in_train:
            self._truncate_long_sequences = False
        logger.info("truncate_long_sequences=%s", str(self._truncate_long_sequences))

        lines = self._read_lines_from_path(file_path, is_train)

        for line in lines:
            if self._dataset_name == "sede":
                annotated_sql: AnnotatedSQL = AnnotatedSQL(
                    line["QuerySetId"],
                    line["Title"],
                    line["QueryBody"],
                    "stackexchange",
                    line["Description"],
                )
            elif self._dataset_name == "spider":
                annotated_sql: AnnotatedSQL = AnnotatedSQL(
                    -1,
                    line["question"],
                    line["query"],
                    line["db_id"],
                    None,
                )
            else:
                raise ValueError(f"Dataset name {self._dataset_name} is not supported")

            annotated_sql = self._preprocess_sample(annotated_sql, need_to_parse_sql=True)

            line_is_valid = self._validate_line(annotated_sql, filter_failed_parsed=self._filter_failed_parsed)

            if not line_is_valid:
                continue
            yield self.text_to_instance(annotated_sql)

        self._log_statistics()

    def _read_lines_from_path(self, file_path: str, is_train: bool) -> List[Dict]:
        if self._dataset_name == "sede":
            if is_train:
                lines = []
                for train_data_path in self._train_data_files:
                    lines.extend(srsly.read_jsonl(os.path.join(file_path, train_data_path)))
            else:
                lines = srsly.read_jsonl(file_path)
        elif self._dataset_name == "spider":
            if is_train:
                lines = []
                for train_data_path in self._train_data_files:
                    with open(os.path.join(file_path, train_data_path)) as in_fp:
                        lines.extend(json.load(in_fp))
            else:
                with open(file_path) as in_fp:
                    lines = json.load(in_fp)
        else:
            raise ValueError(f"Dataset name {self._dataset_name} is not supported")

        return lines

    # pylint: disable=too-many-branches
    def _preprocess_sample(self, annotated_sql: AnnotatedSQL, need_to_parse_sql: bool) -> AnnotatedSQL:
        # clean title and description
        cleaned_title = clean_str(annotated_sql.title)
        cleaned_description = clean_str(annotated_sql.description)

        if self._uncased:
            if cleaned_title:
                cleaned_title = cleaned_title.lower()
            if cleaned_description:
                cleaned_description = cleaned_description.lower()

        # clean SQL query
        cleaned_sql = None
        cleaned_sql_with_values = None
        if annotated_sql.query_body:
            target_with_values = preprocess_for_jsql(annotated_sql.query_body)
            if target_with_values:
                target_tokens = target_with_values.strip(";").split()
                if not self._keep_sql_values:
                    target_tokens = anonymize_values(target_tokens)

                if self._uncased:
                    target_tokens = [token.lower() for token in target_tokens]
                    target_with_values = target_with_values.lower()

                if self._upper_sql:
                    target_tokens = [token.upper() if token.lower() in SQL_TOKENS else token for token in target_tokens]

                target = " ".join(target_tokens)
                cleaned_sql = target
                cleaned_sql_with_values = target_with_values

        db_json = [db for db in self._tables_json if db["db_id"] == annotated_sql.db_id][0]
        schema_description, schema_structured = add_schema_description(
            self._uncased, self._add_column_types, db_json, self._shuffle_schema, self._random
        )

        if self._use_description and cleaned_description:
            if cleaned_title:
                cleaned_title += f" {self._end_symbol} {cleaned_description}"

        if self._use_schema:
            if cleaned_title:
                cleaned_title += f" {schema_description}"

        parsed_sql = None
        if need_to_parse_sql:
            parsed_sql = self._sql_parser.translate(cleaned_sql_with_values, clean=False)

        preprocessed_annotated_sql: AnnotatedSQL = AnnotatedSQL(
            annotated_sql.query_set_id,
            annotated_sql.title,
            annotated_sql.query_body,
            annotated_sql.db_id,
            description=annotated_sql.description,
            cleaned_title=cleaned_title,
            cleaned_description=cleaned_description,
            cleaned_query_body=cleaned_sql,
            cleaned_query_body_with_values=cleaned_sql_with_values,
            schema=schema_structured,
            parsed_sql=parsed_sql,
        )

        return preprocessed_annotated_sql

    def _validate_line(self, annotated_sql: AnnotatedSQL, filter_failed_parsed: bool = False) -> bool:

        # we don't have either title and SQL
        if not annotated_sql.title or not annotated_sql.query_body:
            return False

        # cleaning of the SQL query left us with an empty SQL
        if annotated_sql.query_body and not annotated_sql.cleaned_query_body:
            self._invalid_cleaning_sql_count += 1
            return False

        # parsing of the SQL query left us with an empty SQL
        if annotated_sql.query_body and (not annotated_sql.parsed_sql) and filter_failed_parsed:
            self._invalid_parsing_sql_count += 1
            return False

        # check length of target
        if annotated_sql.cleaned_query_body is not None:
            tokenized_target = [Token("<pad>")] + self._target_tokenizer.tokenize(annotated_sql.cleaned_query_body)
            if (
                self._target_max_tokens
                and len(tokenized_target) > self._target_max_tokens
                and not self._truncate_long_sequences
            ):
                self._target_max_skipped += 1
                return False

        return True

    def _log_statistics(self):
        if self._source_max_tokens and self._source_max_truncated:
            logger.info(
                "In %d instances, the source token length exceeded the max limit (%d) and were truncated.",
                self._source_max_truncated,
                self._source_max_tokens,
            )
        if self._target_max_tokens and (self._target_max_truncated or self._target_max_skipped):
            logger.info(
                "In %d instances, the target token length exceeded the max limit (%d) and were %s.",
                self._target_max_truncated if self._truncate_long_sequences else self._target_max_skipped,
                self._target_max_tokens,
                "truncated" if self._truncate_long_sequences else "skipped",
            )
        if self._invalid_cleaning_sql_count > 0:
            logger.info(
                "In %d instances, the SQL query was invalid after SQL cleaning and skipped.",
                self._invalid_cleaning_sql_count,
            )
        if self._invalid_parsing_sql_count > 0:
            logger.info(
                "In %d instances, the SQL query was invalid after SQL parsing and skipped.",
                self._invalid_parsing_sql_count,
            )

    # pylint: disable=arguments-differ
    @overrides
    def text_to_instance(self, annotated_sql: AnnotatedSQL) -> Instance:
        source = annotated_sql.cleaned_title

        tokenized_source = self._source_tokenizer.tokenize(source)
        if self._source_max_tokens and len(tokenized_source) > self._source_max_tokens:
            self._source_max_truncated += 1
            tokenized_source = tokenized_source[: self._source_max_tokens]
        source_field = TextField(tokenized_source, self._source_token_indexers)

        metadata = {"query_set_id": annotated_sql.query_set_id}

        fields = {
            "source_tokens": source_field,
        }

        if annotated_sql.cleaned_query_body is not None:
            target = annotated_sql.cleaned_query_body

            tokenized_target = [Token("<pad>")] + self._target_tokenizer.tokenize(target)
            if self._target_max_tokens and len(tokenized_target) > self._target_max_tokens:
                self._target_max_truncated += 1
                if self._truncate_long_sequences:
                    tokenized_target = tokenized_target[: self._target_max_tokens]
            target_field = TextField(tokenized_target, self._target_token_indexers)

            fields["target_tokens"] = target_field

            metadata["gold_sql"] = annotated_sql.query_body
            metadata["db_id"] = annotated_sql.db_id
            metadata["parsed_sql"] = annotated_sql.parsed_sql

        fields["metadata"] = MetadataField(metadata)

        return Instance(fields)
