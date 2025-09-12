%% Test component models
clear all
clc

addpath(genpath("utils/"))
addpath(genpath("component_models/"))

data = readtable("../data/cc_out_exp.csv");
% To update/modify data, load the new data, modify it, and finally export it
% writetable(data, "assets/data.csv")

N = height(data);

options_struct = default_parameters();

%% Visualize loh caloreh
compute_condenser_heats(data, 7, visualize=true);
fontsize(16, "points")

%% Ratios to flows and viceversa

Rp = zeros(1, N);
Rs = zeros(1, N);
qdc = zeros(1, N);
qwct = zeros(1, N);

for i=1:N
    [Rp(i), Rs(i)] = flows_to_ratios(data.qc(i), data.qdc(i), data.qwct(i));
    [qdc(i), qwct(i)] = ratios_to_flows(data.qc(i), Rp(i), Rs(i));
end

fprintf("Ratios to flows and viceversa\n")
fprintf("qc experimental: \t%s\n", strjoin(string(data.qc), ', '));
fprintf("qdc experimental: \t%s\n", strjoin(string(data.qdc), ', '));
fprintf("qwct experimental: \t%s\n", strjoin(string(data.qwct), ', '));

fprintf("Rp estimated: \t\t%s\n", strjoin(string(Rp), ', '));
% Replace NaN values with 'NaN' for printing
RsString = arrayfun(@(x) num2str(x, '%.4f'), Rs, 'UniformOutput', false);
RsString(isnan(Rs)) = {'NaN'}; % Replace NaN entries with the string 'NaN'
fprintf("Rs estimated: \t\t%s\n", strjoin(RsString, ', '));

fprintf("qdc from ratios: \t%s\n", strjoin(string(qdc), ', '));
fprintf("qwct from ratios: \t%s\n", strjoin(string(qwct), ', '));

fprintf("dc error: \t%s\n", strjoin(string(abs(data.qdc'-qdc)), ', '));
fprintf("wct error: \t%s\n", strjoin(string(abs(data.qwct'-qwct)), ', '));

%% DC
clc

% Data based
% model_id = "dc_model.m";
% model_type = "data";
% model_fun_data = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));
% First principles
% model_type = "physical";
% model_fun_physical = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));

model_fun = @dc_model_data;
dc_model_data_path = "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_dc_fp_pilot_plant_gaussian_cascade.mat";
n_dc = 1;

% [Tout, Pe] = model_dc(Tamb, Tin, w_fan, q)
Tout_data = zeros(1, N); Tout_physical = zeros(1, N);
Ce_data = zeros(1, N); Ce_physical = zeros(1, N);
inactive_idxs = [];
for i=1:N
    fprintf("Evaluating step %d\n", i)
    [Tout_data(i), Ce_data(i)] = model_fun(...
        data.Tamb(i), ...
        data.Tdc_in(i), ...
        data.qdc(i), ...
        data.wdc(i), ...
        model_data_path=dc_model_data_path, ...
        lb=options_struct.dc_lb, ...
        ub=options_struct.dc_ub, ...
        ce_coeffs=options_struct.dc_ce_coeffs,....
        n_dc=n_dc...
    );
    % [Tout_physical(i), Ce_physical(i)] = model_fun_data(data.Tamb(i), data.Tdc_in(i), data.wdc(i), data.qdc(i));
    if Ce_data(i) < 1e-3
        inactive_idxs = [inactive_idxs, i];
    end
end
inactive_idxs
active_idxs = ~ismember(1:height(data), inactive_idxs);
% print out model performance
fprintf("DC model Tdc_out RMSE (ºC) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Tdc_out', Tout_data), nan)
results = array2table([Tout_data', Ce_data'], "VariableNames", ["Tdc_out", "Ce"]);
regression_plot(data(active_idxs, :), rearrangeTable(data(active_idxs, :), results(active_idxs, :)), [15], output_vars_sensor_types=repmat("pt100", 1, 1));

%% WCT
clc
% Data based
% model_id = "wct_model.m";
% model_type = "data";
% model_fun_data = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));
% First principle
% model_type = "physical";
% model_fun_physical = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));

model_fun = @wct_model_data; % wct_model_physical; % wct_model_data

c_poppe = 1.52; % 1.52;
n_poppe = -0.69; % -0.69;
wct_model_data_path = "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_fp_pilot_plant_gaussian_cascade.mat";
% wct_model_data_path = "/home/patomareao/development/SOLhycool/modeling/matlab/component_models/wct_model_data.mat";
% [Tout, Ce, Cw] = wct_model(Tamb, HR, Tin, q, w_fan)
Tout_data = zeros(1, N); Tout_physical = zeros(1, N);
Ce_data = zeros(1, N); Ce_physical = zeros(1, N);
Cw_data = zeros(1, N); Cw_physical = zeros(1, N);
inactive_idxs = [];
for i=1:N
    fprintf("Evaluating step %d\n", i)
    [Tout_data(i), Ce_data(i), Cw_data(i)] = model_fun(...
        data.Tamb(i), ...
        data.HR(i), ...
        data.Twct_in(i), ...
        data.qwct(i), ...
        data.wwct(i), ...
        model_data_path=wct_model_data_path, ...
        lb=options_struct.wct_lb, ...
        ub=options_struct.wct_ub, ...
        ce_coeffs=options_struct.wct_ce_coeffs ...
    );
        % c_poppe=c_poppe, ...
        % n_poppe=n_poppe...

    % [Tout_physical(i), Ce_physical(i)] = model_fun_data(data.Tamb(i), data.Tdc_in(i), data.wdc(i), data.qdc(i));
    if Cw_data(i) < 1e-3
        inactive_idxs = [inactive_idxs, i];
    end
end
active_idxs = ~ismember(1:height(data), inactive_idxs);
% print out model performance
fprintf("WCT model Twct_out RMSE (ºC)\t| Data based = %.2f / Physical = %.2f\n", rmse(data.Twct_out', Tout_data), nan)
fprintf("WCT model Cw RMSE (l/h) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Cw', Cw_data), nan)

results = array2table([Tout_data', Ce_data', Cw_data'], "VariableNames", ["Twct_out", "Ce", "Cw"]);
regression_plot(data(active_idxs,:), rearrangeTable(data(active_idxs,:), results(active_idxs,:)), [16, 13], output_vars_sensor_types=["pt100", "paddle_flow_meter"], units=["ºC", "l/h"]);


%% Combined model
clc

options_struct = default_parameters();
% DC                       "Tamb",    "Tin",   "q", "w_fan"
options_struct.dc_lb = 0.9*[5.0600   10.0, 5.2211, 11];
options_struct.dc_ub = 1.1*[50.7500   50.0, 24.1543, 99.1800];
options_struct.dc_model_data_path = "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_dc_fp_pilot_plant_gaussian_cascade.mat";

% WCT               "Tamb",     "HR",    "Tin",      "q",     "w_fan"
options_struct.wct_lb = [0.1    0.1     5.0    5.0       0.];
options_struct.wct_ub = [50.0   99.99   55.0   24.8400   95.];
options_struct.wct_model_data_path = "/home/patomareao/development/SOLhycool/modeling/data/models_data/model_data_wct_fp_pilot_plant_gaussian_cascade.mat";

% end
options_struct.model_type = "physical";

% Tv_data = zeros(1, N); Tout_physical = zeros(1, N);
Ce_data = zeros(1, N); Ce_physical = zeros(1, N);
Cw_data = zeros(1, N); Cw_physical = zeros(1, N);
detailed_data = [];
% parameters.condenser_option = 3;
for i=1:N
    fprintf("Evaluating step %d\n", i)

    [Ce_data(i), Cw_data(i), detailed] = combined_cooler_model( ...
        data.Tamb(i), ...
        data.HR(i), ...
        data.mv(i), ...
        data.qc(i), ...
        data.Rp(i), ...
        data.Rs(i), ...
        data.wdc(i), ...
        data.wwct(i), ...
        data.Tv(i), ...
        options_struct,...
        silence_warnings=false ...
    );

    detailed_data = [detailed_data detailed];

    fprintf("%d | Tc_in_ref= %.2f, Tc_in_mod=%.2f | Tc_out_ref= %.2f, Tc_out_mod=%.2f | Tdc_out_ref= %.2f, Tdc_out_mod=%.2f | Twct_out_ref= %.2f, Twct_out_mod=%.2f\n", ...
        i, data.Tc_in(i), detailed.Tc_in, data.Tc_out(i), detailed.Tc_out, data.Tdc_out(i), detailed.Tdc_out, data.Twct_out(i), detailed.Twct_out)

    % [Tvphysical(i), Ce_physical(i), Cw_physical(i), detailed] = combined_cooler_model( ...
    %     data.Tamb(i), data.HR(i),
    % data.mv(i), data.qc(i), data.Rs(i), data.Rp(i), ...
    %     data.wdc(i), data.wwct(i), model_type="physical");
    % 
    % detailed_physical = [detailed_physical detailed];
end

% print out model performance
% fprintf("CS model Tv_out RMSE (ºC)\t| Data based = %.2f / Physical = %.2f\n", rmse(data.Tv', Tv_data), nan)
fprintf("CS model Ce RMSE (kWe) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Ce', Ce_data), nan)
fprintf("CS model Cw RMSE (l/h) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Cw', Cw_data), nan)
fprintf("CS model Tdc_out RMSE (ºC) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Tdc_out', [detailed_data.Tdc_out]), nan)
fprintf("CS model Twct_out RMSE (ºC)\t| Data based = %.2f / Physical = %.2f\n", rmse(data.Twct_out', [detailed_data.Twct_out]), nan)

results = struct2table(detailed_data);
% tableData = data;
% 
% commonColumns = intersect(results.Properties.VariableNames, tableData.Properties.VariableNames);
% 
% % Step 3: Calculate absolute differences for common columns
% for i = 1:numel(commonColumns)
%     col = commonColumns{i};
%     tableData.(['AbsDiff_' col]) = abs(tableData.(col) - results.(col));
% end
% 
% % Display the resulting table
% disp(tableData);
%%
regression_plot(data, rearrangeTable(data, results), ...
    [2, 6, 10, 11, 12, 13, 15, 16, 20], ...
    output_vars_sensor_types=repmat("pt100", 1, 9));
fontsize(16, "points")


%% Visualization of results

visualization