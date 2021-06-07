# SEDE
![sede ci](https://github.com/hirupert/sede/actions/workflows/ci.yml/badge.svg)

Code and data from the paper: "Text-to-SQL in the Wild: A Naturally-Occurring Dataset Based on Stack Exchange Data".

### Setup Instructions

Create a new Python 3.7 virtual environment:

```
python3.7 -m venv .venv
```

Activate the virtual environment:

```
source .venv/bin/activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Add the project directory to python PATH:
```
export PYTHONPATH=/your/projects-directories/sede:$PYTHONPATH
```

One can run all commands by just running ``make`` command, or running them step by step by the following commands:


Run pylint:

```
make lint
```

Run black:

```
make black_check
```

Run tests (required JSQL running for this - please see "Running JSQLParser" chapter):

```
make unit_test
```

Add the virtual environment to Jupyter Notebook:

```
python3.7 -m ipykernel install --user --name=.venv
```

Now you can enter into Jupyter with the command `jupyter notebook` and when creating a new notebook you will need to choose the `.venv` environment.


### Folders Navigation
* `src` - source code
* `configs` - contains configuration files for running experiments
* `data/sede` - train/val/test sets of SEDE. Note - files with the `_original` suffix are the ones that we kept original as coming from SEDE without our fixes. See our paper for more details.
* `notebooks` - some helper Jupyter notebooks.
* `stackexchange_schema` - holds file that respresents the SEDE schema.

### Running JSQLParser

Clone JSQLParser-as-a-Service project: `git clone https://github.com/hirupert/jsqlparser-as-a-service.git`

Enter the folder with `cd jsqlparser-as-a-service`

Build the JSQLParser-as-a-Service image using the following command: `docker build -t jsqlparser-as-a-service .`

Running the image inside a docker container in port 8079: `docker run -d -p 8079:8079 jsqlparser-as-a-service`

Test that the docker is running by running the following command:
```
curl --location --request POST 'http://localhost:8079/sqltojson' \
--header 'Content-Type: application/json' \
--data-raw '{
    "sql":"select salary from employees where salary < (select max(salary) from employees)"
}'
```

### Downloading Spider dataset

In order to run our model + Partial Match F1 metric on Spider dataset,
one must download Spider dataset from here: https://yale-lily.github.io/spider and save it under `data/spider` folder inside the root project directory.

### Training

Training SEDE:
```
python main_allennlp.py train configs/t5_text2sql_sede.jsonnet -s experiments/name_of_experiment --include-package src
```

Training Spider:
```
python main_allennlp.py train configs/t5_text2sql_spider.jsonnet -s experiments/name_of_experiment --include-package src
```

### Evaluation

Run evaluation on val/test set with:
```
python main_allennlp.py evaluate experiments/name_of_experiment data/test.jsonl --output-file experiments/name_of_experiment/predictions.sql --cuda-device 0 --batch-size 10 --include-package src
```

### Inference

Predict with:
```
python main_allennlp.py predict experiments/name_of_experiment data/val.jsonl --output-file experiments/name_of_experiment/predictions.sql --use-dataset-reader --predictor seq2seq2 --cuda-device 0 --batch-size 10 --include-package src
```

## Acknowledgements

We thank Kevin Montrose and the rest of the Stack Exchange team for providing the raw query log.