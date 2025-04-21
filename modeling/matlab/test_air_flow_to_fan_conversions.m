addpath(genpath("utils/"))
addpath(genpath("component_models/"))

wwct = linspace(21, 100, 10);

ma = fan_speed_to_air_mass_flow_rate_fit(wwct);
[wwct_computed, valid] = air_mass_flow_rate_to_fan_speed(ma);


[wwct' wwct_computed' valid' ma']