TODO:

- [ ] Model water availability as a function of precipitation data and some evaporation rate



## Run simulations in the background

container_name = festive_hypatia

```bash
docker exec -d festive_hypatia bash -c "source /miniconda3/bin/activate conda-env && python /workspaces/SOLhycool/simulation/scripts/yearly_simulation_static.py > /workspaces/SOLhycool/simulation/results/output.log 2>&1"
```

Check the logs:

```bash
docker exec -it festive_hypatia bash tail -f /workspaces/SOLhycool/simulation/results/output.log
```