# SOLhycool. Simulations

## Generating dataset for simulations

The dataset used for the simulation is the result of the combination of 4 sources:
- [Electricity price data](./notebooks/process_electricity_price_data.ipynb)
- [Thermal load data](./notebooks/generate_thermal_load_profile.ipynb)
- [Weather data](./notebooks/process_weather_data.ipynb)
- [Water data](./notebooks/generate_water_context.ipynb)

Run each notebook adjusting its names and sources and finally run the [generate ennvironment notebook](./notebooks/generate_environment.ipynb) to combine all individual sources into one single dataset.

Visualizations of the different datasets are stored in the [visualizations](./results/visualizations/) folder.

## Run simulations in the background

container_name = festive_hypatia

- Yearly simulation of static systems
```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/simulation/scripts/yearly_simulation_static2.py --problem_id wct --n_parallel_evals 20 --env_path data/datasets/environment_data_andasol_20220101_20241231.h5 --evaluation_id andasol > /workspaces/SOLhycool/simulation/results/output.log 2>&1"
```
```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/simulation/scripts/yearly_simulation_static2.py > /workspaces/SOLhycool/simulation/results/output.log 2>&1"
```

Check the logs:

```bash
docker exec -it festive_hypatia bash tail -f /workspaces/SOLhycool/simulation/results/output.log
```