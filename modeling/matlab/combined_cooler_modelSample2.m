% Sample script to demonstrate execution of function [Tv_C, Ce_kWe, Cw_lh, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, options)
Tamb_C = 20.923332922359200; % Initialize Tamb_C here
HR_pp = 42.056076841053000; % Initialize HR_pp here
mv_kgh = 303.4643039111180; % Initialize mv_kgh here
qc_m3h = 17.998551582805800; % Initialize qc_m3h here
Rp = 0.346000000000000; % Initialize Rp here
Rs = 0; % Initialize Rs here
wdc = 59.506663978673800; % Initialize wdc here
wwct = 24.675237054315400; % Initialize wwct here
Tv = 43.324458513828800;
Tv_in = [];

options = struct('model_type', 'data', 'lb', Tv, 'ub', Tv, 'x0', nan, 'parameters', default_parameters()); % Default values
options.parameters.condenser_option = 5;

[Ce_kWe, Cw_lh, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, Tv_in, options);
