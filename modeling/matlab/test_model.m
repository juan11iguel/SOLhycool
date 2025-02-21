%% Test component models
clear all
clc

addpath(genpath("utils/"))
addpath(genpath("component_models/"))

data = readtable("../assets/data.csv");
% To update/modify data, load the new data, modify it, and finally export it
% writetable(data, "assets/data.csv")

N = height(data);

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

%% DC

% Data based
model_id = "dc_model.m";
model_type = "data";
model_fun_data = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));
% First principles
% model_type = "physical";
% model_fun_physical = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));

% [Tout, Pe] = model_dc(Tamb, Tin, w_fan, q)
Tout_data = zeros(1, N); Tout_physical = zeros(1, N);
Ce_data = zeros(1, N); Ce_physical = zeros(1, N);
for i=1:N
    [Tout_data(i), Ce_data(i)] = model_fun_data(data.Tamb(i), data.Tdc_in(i), data.qdc(i), data.wdc(i));
    % [Tout_physical(i), Ce_physical(i)] = model_fun_data(data.Tamb(i), data.Tdc_in(i), data.wdc(i), data.qdc(i));
end
% print out model performance
fprintf("DC model Tdc_out RMSE (ºC) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Tdc_out', Tout_data), nan)
results = array2table([Tout_data', Ce_data'], "VariableNames", ["Tdc_out", "Ce"]);
regression_plot(data, rearrangeTable(data, results), [15], output_vars_sensor_types=repmat("pt100", 1, 1));

%% WCT

% Data based
model_id = "wct_model.m";
model_type = "data";
model_fun_data = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));
% First principle
% model_type = "physical";
% model_fun_physical = function_handle(char(fullfile('.', 'component_models', model_type, model_id)));

% [Tout, Ce, Cw] = wct_model(Tamb, HR, Tin, q, w_fan)
Tout_data = zeros(1, N); Tout_physical = zeros(1, N);
Ce_data = zeros(1, N); Ce_physical = zeros(1, N);
Cw_data = zeros(1, N); Cw_physical = zeros(1, N);
for i=1:N
    [Tout_data(i), Ce_data(i), Cw_data(i)] = model_fun_data(data.Tamb(i), data.HR(i), data.Twct_in(i), data.qwct(i), data.wwct(i));
    % [Tout_physical(i), Ce_physical(i)] = model_fun_data(data.Tamb(i), data.Tdc_in(i), data.wdc(i), data.qdc(i));
end
% print out model performance
fprintf("WCT model Twct_out RMSE (ºC)\t| Data based = %.2f / Physical = %.2f\n", rmse(data.Twct_out', Tout_data), nan)
fprintf("WCT model Cw RMSE (l/h) \t| Data based = %.2f / Physical = %.2f\n", rmse(data.Cw', Cw_data), nan)

results = array2table([Tout_data', Ce_data', Cw_data'], "VariableNames", ["Twct_out", "Ce", "Cw"]);
regression_plot(data, rearrangeTable(data, results), [16, 13], output_vars_sensor_types=["pt100", "paddle_flow_meter"], units=["ºC", "l/h"]);


%% Combined model
clc

% Tv_data = zeros(1, N); Tout_physical = zeros(1, N);
Ce_data = zeros(1, N); Ce_physical = zeros(1, N);
Cw_data = zeros(1, N); Cw_physical = zeros(1, N);
detailed_data = [];
parameters = default_parameters();
parameters.condenser_option = 3;
for i=1:N
    [Ce_data(i), Cw_data(i), detailed] = combined_cooler_model( ...
        data.Tamb(i), data.HR(i), data.mv(i), data.qc(i), data.Rp(i), data.Rs(i), ...
        data.wdc(i), data.wwct(i), data.Tv(i), ...
        struct("model_type",'data', "silence_warnings", true, "parameters", parameters ,"lb", data.Tv(i), "ub", data.Tv(i)));

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

%% Visualization of results

visualization