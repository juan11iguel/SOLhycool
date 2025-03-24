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

for option=1:7
    parameters = default_parameters();
    parameters.condenser_option = option;
    options = struct('model_type', 'data', 'lb', nan, 'ub', nan, 'x0', nan, 'silence_warnings', true, 'parameters', parameters); % Default values
    
    [Ce_kWe, Cw_lh, detailed] = combined_cooler_model(9.06, 84.0, 297.7741653659358, 21.5378350834096, 0.6713585696276376, 0.0037038855982315, 11.0004372409649, 43.471340302871646, 35.0, options);
    fprintf("Option %d\n", option)
    fprintf("Qc transfered: %.2f\n", detailed.Qc_transfered)
    fprintf("Qc absorbed: %.2f\n\n", detailed.Qc_absorbed)
end