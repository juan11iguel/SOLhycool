# Project deployment with airflow

In order to streamling the evaluation of the optimization and annual simulations, 
instead of relying on running the scripts manually 
(see [optimization/README.md](../optimization/README.md)), a better approach is
to setup workflows with [Apache Airflow](https://airflow.apache.org/).

This repository uses a custom Dockerfile, which using the base Dockerfile that is 
used for development, extends it to add Airflow to the conda environment.

## Getting started

### Developement environment

Within the devcontainer, just run the following command to start up Airflow:

```bash
airflow standalone
```

If it fails, it an issue with some configuration parameter missing in some airflow version!

Add:
`socket_cleanup_timeout = 30`

Under `[workers]` section in the airflow.cfg. See [pull 52705](https://github.com/apache/airflow/pull/52705)

In order for it to persist even when exiting the devcontainer, run the following command on the host:
```bash
docker exec -d CONTAINER_NAME bash -c "source /miniconda3/bin/activate conda-env && airflow standalone"
```
Though the web interface will only be available if forwarding the 8080 port. This can be done in VSCode in the ports settings.
![alt text](../data/assets/port-forwarding-vscode.png)

### Development deployment

This allows to make use of the development conda environment which changes dynamically with changes to the codebase.
Just find the devcontainer image name with `docker images` and replace it in the following command:

```bash
docker compose -f SOLhycool/docker-compose.dev.yml up -d --build
```

Check the password:
```bash
docker exec solhycool-airflow-dev /bin/zsh -c "cat simple_auth_manager_passwords.json.generated"
```

(We use 8090 to avoid potential conflicts if the "production" deployment is also running)

### Production deployment

(Proably calling it production is a bit far fetched)

1. Initialize the database
```bash
docker compose up airflow-init
```

2. Start up all services
```bash
docker compose up -d
```

After initializing the container, the passwords can be consulted by running the following command:

```bash
docker exec solhycool-airflow cat /app/airflow/simple_auth_manager_passwords.json.generated
```

# To start from schratch
[Source](https://airflow.apache.org/docs/apache-airflow/stable/tutorial/pipeline.html)

In a while, maybe the docker-compose.yaml file will be updated, to get the latest version, you can run the following commands:

```bash
### Download the docker-compose.yaml file
curl -LfO 'https://airflow.apache.org/docs/apache-airflow/stable/docker-compose.yaml'

### Make expected directories and set an expected environment variable
mkdir -p ./dags ./logs ./plugins
echo -e "AIRFLOW_UID=$(id -u)" > .env

### Initialize the database
docker compose up airflow-init

### Start up all services
docker compose up
```

# Testing the DAGs

## Basic test

Just activate the python environment and run the dag file:

```bash
python dag.py
```

It will raise any errors preventing the dag from being loaded, but no runtime errors. For that the complete test is used.

## Complete test

Run `airflow dags test DAG_ID`. To specify some parameters different to the default one, add them as a `json` string:

```bash
airflow dags test horizon_optimization_day_report --conf '{"plt_config_path":"../data/plot_config_day_test.hjson"}'
```

To test the annual simulation:
```bash
airflow dags test sim_year_horizon_optimization \
  --conf '{
    "sim_id": "andasol_pilot_plant_wct100",
    "sim_config_path": "/workspaces/SOLhycool/simulation/data/simulations_config.json",
    "env_path": "/workspaces/SOLhycool/data/datasets/",
    "output_path": "/workspaces/SOLhycool/simulation/results/",
    "date_span": ["20220101", "20221231"],
    "n_parallel_steps": 24,
    "n_parallel_days": 5,
    "previous_results_id": "sim_results"
  }'
  ```

```bash
airflow dags test sim_year_horizon_optimization \
  --conf '{
    "sim_id": "andasol_pilot_plant_wct100"
  }'
  ```