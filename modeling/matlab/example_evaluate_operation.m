data = readtable("../data/data.csv");
addpath("component_models/")

parameters = default_parameters();
p = parameters;

%% Evaluate wct fan speed given outlet temperature
for i=1:height(data)
    if ~(data.qwct(i) > 0.5)
        continue
    end
    [wwct, valid] = wct_inverse_model(data.Tamb(i), data.HR(i), data.Twct_in(i), data.qwct(i), data.Twct_out(i), ...
        model_data_path=parameters.wct_model_data_path, silence_warnings=false, lb=p.wct_lb, ub=p.wct_ub);

    fprintf("Point %d | wwct model: %.2f, wwct experimental: %.2f | Valid: %s\n", i, wwct, data.wwct(i), string(valid))
    fprintf("Tamb=%.2f, HR=%.2f, Twct_in=%.2f, qwct=%.2f, Twct_out=%.2f\n", data.Tamb(i), data.HR(i), data.Twct_in(i), data.qwct(i), data.Twct_out(i))
end

%% Evaluate operation point given everything but the wct fan frequency
clc

tic

% parameters = default_parameters();

for i=1:height(data)
    % if ~(data.qwct(i) > 0.5)
    %     continue
    % end
    clear evaluate_operation

    [Ce_kWe, Cw_lh, detailed, valid] = evaluate_operation(data.Tamb(i), data.HR(i), data.mv(i), data.qc(i), data.Rp(i), data.Rs(i), data.wdc(i), data.Tv(i), ...
        condenser_option=6, wct_model_data_path="/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_fp_pilot_plant_gaussian_cascade.mat");
    
    fprintf("Point %d | Valid: %s | wwct model: %.2f, wwct experimental: %.2f \n", i, string(valid), detailed.wwct, data.wwct(i))
    fprintf("Experimental data: Tamb=%.2f, HR=%.2f, Twct_in=%.2f, qwct=%.2f, Twct_out=%.2f\n", data.Tamb(i), data.HR(i), data.Twct_in(i), data.qwct(i), data.Twct_out(i))
    fprintf("Tc_in_ref= %.2f, Tc_in_mod=%.2f | Tc_out_ref= %.2f, Tc_out_mod=%.2f | Tdc_out_ref= %.2f, Tdc_out_mod=%.2f | Twct_in_ref= %.2f, Twct_in_mod=%.2f | Twct_out_ref= %.2f, Twct_out_mod=%.2f\n\n", ...
        data.Tc_in(i), detailed.Tc_in, data.Tc_out(i), detailed.Tc_out, data.Tdc_out(i), detailed.Tdc_out, data.Twct_in(i), detailed.Twct_in, data.Twct_out(i), detailed.Twct_out)
    % display(detailed.qwct)
end

fprintf('%.2f eval/sec\n', height(data)/(toc))