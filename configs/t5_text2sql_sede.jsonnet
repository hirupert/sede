local model_name = "t5-base";
local train_data = "data/sede";
local dev_data = "data/sede/val.jsonl";
local tables_file = "stackexchange_schema/tables_so.json";

local num_gpus = 0;

{
    "train_data_path": train_data,
    "validation_data_path": dev_data,
    "dataset_reader": {
        "type": "text2sql",
        "source_tokenizer": {
            "type": "pretrained_transformer",
            "model_name": model_name
        },
        "source_token_indexers": {
            "tokens": {
                "type": "pretrained_transformer",
                "model_name": model_name,
                "namespace": "tokens"
            }
        },
        "train_data_files": ["train.jsonl"],
        "dataset_name": "sede",
        "source_max_tokens": 512,
        "target_max_tokens": 250,
        "source_add_start_token": false,
        "source_add_end_token": false,
        "target_add_start_token": true,
        "target_add_end_token": false,
        "start_symbol": "<s>",
        "end_symbol": "</s>",
        "uncased": true,
        "truncate_long_sequences_in_train": false, // if false, will skip long sequences in train set
        "shuffle_schema": false,
        "use_schema": false,
        "tables_file_path": tables_file,
        "add_column_types": false,
        "keep_sql_values": true,
        "use_description": false,
        "upper_sql": false,
        "filter_failed_parsed": true
//         "max_instances": 10 // DEBUG setting
    },
    "model": {
        "type": "t5",
        "model_name": model_name,
        "beam_size": 6,
        "measure_partial_match": true,
        "max_decoding_steps": 250,
        "punish_invalid_sql": true,
        "debug_mode": false,
        "measure_sql_match": false,
        "label_smoothing": null,
        "cross_entropy_average": "batch"  # token/batch
    },
    [if num_gpus > 1 then "distributed"]: {
        # "cuda_devices": std.range(0, num_gpus - 1) # Use this for running on GPU
        "cuda_devices": std.repeat([-1], num_gpus)  # Use this for debugging on CPU
    },
    "data_loader": {
        "batch_size": 6,
        "shuffle": true
    },
    "trainer": {
        "num_epochs": 60,
        "optimizer": {
            "type": "huggingface_adamw",
            "lr": 5e-5,
            "betas": [0.9, 0.999],
            "eps": 1e-8,
            "correct_bias": true
        },
        "checkpointer": {
            "num_serialized_models_to_keep": 1
        },
        "grad_norm": 1.0,
        # num_gradient_accumulation_steps: 21,
        "validation_metric": "+partial_match_f1",
        callbacks: [
            {
                type: "wandb",
                project: "sede-text-to-sql",
            }
        ]
    }
}
