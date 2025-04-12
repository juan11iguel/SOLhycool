#!/bin/bash

# Usage: ./run_simulations.sh [container_name]
CONTAINER_NAME=${1:-festive_hypatia}

COMMON_PREFIX="docker exec -d $CONTAINER_NAME bash -c \"source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/simulation/scripts/yearly_simulation_static.py"
COMMON_SUFFIX="--n_parallel_evals 5 --env_path data/datasets/environment_data_med_20220101_20241231.h5 --evaluation_id eds_Q_constant > /workspaces/SOLhycool/simulation/results/output.log 2>&1"

$COMMON_PREFIX --problem_id med_75_parallel $COMMON_SUFFIX
$COMMON_PREFIX --problem_id med_wct_only $COMMON_SUFFIX
$COMMON_PREFIX --problem_id med_50_parallel $COMMON_SUFFIX
$COMMON_PREFIX --problem_id med_100_series $COMMON_SUFFIX

# Show the logs
docker exec -it $CONTAINER_NAME tail -f /workspaces/SOLhycool/simulation/results/output.log
