%% Batch training

% This script contains the code to train and validate different modelling
% approaches with different architectures (simple or series/cascade)
%
% - Simple is a model that integrates the prediction of the two output
%   variables internally (e.g. ann with two outputs)
% - Series / cascade on the other hand separates each output variable in 
% different models, where one of them uses the output from the other.

addpath("utilities/")


%% Actual function code

% Load validation data
if ~isempty(data_validation_path)
    data_val = readtable(data_validation_path);
    [~, fname, ext] = fileparts(data_validation_path);
    validation_filename = fname+ext;
else
    fprintf("No validation (test) data path provided. Test set will be extracted from the training-validation set\n")
    data_val = [];
end

% Get a list of all files in the directory
files = dir(fullfile(data_path, filename_to_test + "*.csv"));

% Check if the directory exists
if isempty(files)
    error('Not a single valid file found in the specified directory.');
end

% Initialize empty divideInd
divideInd = cell(0);

% Extract the file names from the structure
if ~filter_filenames
    filenames = cellfun(@(x) strtok(x, '.'), {files.name}, 'UniformOutput', false);
    filenames=string(filenames);
else
    filenames = [filename_to_test];
end

n_outputs = length(output_vars_idx);

if n_outputs > 3
    error("This function only supports 1 (Tout), 2 (Tout, Cw) or 3 (Tout, Cw, Ce) outputs")
end

fitrgp_auto = @(x,y) fitrgp(x, y);
% fitrgp_auto = @(x,y) fitrgp(x, y, ...
%     'KernelFunction','squaredexponential', ...
%     'FitMethod','sr', ...
%     'ActiveSetSize', 200, ...
%     'BasisFunction','none', ...
%     'Standardize', true ...
% );

% fitrgp_auto = @(x,y) fitrgp(x, y, ...
%     'KernelFunction','squaredexponential', ...
%     'FitMethod','sr', ...
%     'ActiveSetSize', 200, ...
%     'BasisFunction','none', ...
%     'Standardize', true ...
% );
    % 'OptimizeHyperparameters','auto', ...
    % 'HyperparameterOptimizationOptions', ...
    % struct('AcquisitionFunctionName','expected-improvement-plus'));

%% Alternative methods

% for filename=[filenames(1)]
for filename=filenames
    case_study_id = strrep(filename, filename_to_test, '');

%     if ~strcmp(filename, filename_to_test) && filter_filenames
%         continue
%     end

    % Create import options for the file
    file_path = sprintf("%s/%s.csv", data_path, filename);
    % Read the table using the specified options
    data_tr = readtable(file_path);

    inputs_tr = table2array( data_tr(:, input_vars_idx) );
    out_ref_tr = table2array( data_tr(:, output_vars_idx) );
    
    if ~isempty(data_val)
        data_net = [data_tr; data_val];
    else
        data_net = data_tr;
        validation_filename = filename+".csv";
    end
    inputs_net = table2array( data_net(:, input_vars_idx) );
    out_ref_net = table2array( data_net(:, output_vars_idx) );

    for configuration_type=configuration_types
        % Assign train and validation from train data, and test from
        % validation set if provided
        % Otherwise take it from train data too
        divideInd = cell(3,1);
        
        % Train, validation, test sets
        [divideInd{1,:}, divideInd{2,:}, divideInd{3,:}] = dividerand(height(data_tr), trainRatio, valRatio, testRatio);
        
        if isempty(data_val)
            % Validation data not provided
            data_val = data_net(divideInd{3,:}, :);
        else
            % Validation set provided
            divideInd{3,:} = height(data_tr)+1:height(data_net);
        end
        inputs_val = table2array( data_val(:, input_vars_idx) );
        outputs_val = table2array( data_val(:, output_vars_idx) );

        for alternative=alternatives

            tr = struct;

            if strcmp(configuration_type, "simple")
                % Just override `simple` to `mimo` when saving the files
                configuration_type_str = "mimo";
            else
                configuration_type_str = configuration_type;
            end
            % {system: dc}_{optional: fp_}{alternative: gaussian}_{}_{configuration: mimo}
            if strlength(case_study_id) == 0
                test_id = sprintf( '%s_%s%s_%s', system_to_model, auxiliary_id, alternative, configuration_type_str );
            else
                test_id = sprintf( '%s_%s%s_%s_%s', system_to_model, auxiliary_id, alternative, case_study_id, configuration_type_str );
            end
            
            % load(sprintf("datos/conjuntos datos reducidos/%s.mat", filename), "data_new");
            % data_tr = data_new;
            out_mod_tr = zeros(height(data_tr), n_outputs);
            model = cell(n_outputs,1);

            diary(sprintf('%s/logs/%s.txt', results_path, test_id));

            fprintf('\nStarting evaluation of %s \n', test_id)

            init_time_training = tic;
            % Train and validate alternative
            if strcmp(alternative, "gaussian")

                % Only one output
                if isscalar(output_vars_idx)

                    % Calibrate model
    
                    % Fit for Tout
                    model = fitrgp_auto(inputs_tr, out_ref_tr);
                    model = compact(model); % Model compact version

                
                elseif ~strcmp(configuration_type, "cascade")
                    % Only cascade
                    continue
                else
    
                    % Calibrate model
    
                    % Fit for Tout
                    model{1} = fitrgp_auto(inputs_tr, out_ref_tr(:,1));
                    % Predict Tout for the training set to use it for Mlost
                    [out_mod_tr(:,1), ~, ~] = predict(model{1}, inputs_tr);
                    % Fit for Mlost
                    model{2} = fitrgp_auto([inputs_tr, out_mod_tr(:,1)], out_ref_tr(:,2));

                    model{1} = compact(model{1}); % Model compact version
                    model{2} = compact(model{2}); % Model compact version

                    % Fit for Ce, not cascade
                    if n_outputs == 3
                        model{3} = fitrgp(inputs_tr, out_ref_tr(:,3));
                        model{3} = compact(model{3}); % Model compact version
                    end
                end

            elseif strcmp(alternative, "radial_basis")

                spread = linspace(0.1, 30, 15);
                errors = 9999 * ones(1, length(spread));
                
                % Calibrate model
                if strcmp(configuration_type, "simple")
                    % Fit for Tout and Mlost
                    for idx=1:length(spread)
                        model = newgrnn(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},:)', spread(idx));
                        out = sim(model, inputs_tr(divideInd{2},:)')';
                        errors(idx) = mse(out_ref_tr(divideInd{2},1), out(:,1)); %'Normalization', 'standard');
                    end
                    % Choose for best temperature prediction and train the
                    % new network
                    model = newgrnn(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},:)', spread(min(errors) == errors));

                elseif strcmp(configuration_type, "cascade")
                    model = cell(1,2);
                    outputs_mod = zeros(2, length(divideInd{2}));
                    
                    % Fit for Tout
                    for idx=1:length(spread)
                        model{1} = newgrnn(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},1)', spread(idx));
                        errors(idx) = mse(out_ref_tr(divideInd{2},1)', sim(model{1}, inputs_tr(divideInd{2},:)')); %'Normalization', 'standard');
                    end
                    % Choose for best model
                    model{1} = newgrnn(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},1)', spread(min(errors) == errors));
                    
                    % Fit for Mloss
                    for idx=1:length(spread)
                        model{2} = newgrnn([inputs_tr(divideInd{1},:), out_ref_tr(divideInd{1},1)]', out_ref_tr(divideInd{1},2)', spread(idx));
                        errors(idx) = mse( out_ref_tr(divideInd{2},2), sim(model{2}, [inputs_tr(divideInd{2},:), out_ref_tr(divideInd{2},1)]')' ); %'Normalization', 'standard');
                    end
                    % Choose the best model
                    model{2} = newgrnn([inputs_tr(divideInd{1},:), out_ref_tr(divideInd{1},1)]', out_ref_tr(divideInd{1},2)', spread(min(errors) == errors));
                else
                    raise_unknown_configuration(configuration_type)
                end

                tr.topology = print_network_topology(model);
                tr.spread = spread(min(errors) == errors);
                tr.divideInd = divideInd;

            elseif strcmp(alternative, "radial_basis2")

                % It uses newrb instead of newgrnn
                % The error to choose the best spread uses both Tout and
                % Mlost

                spread = linspace(0.1, 30, 15);
                errors = 9999 * ones(1, length(spread));
                max_neurons = 120;
                neurons_to_add = 20;
                
                % Calibrate model
                if strcmp(configuration_type, "simple")

                    goal = 10; % MSE

                    % Fit for Tout and Mlost
                    for idx=1:length(spread)
                        model = newrb(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},:)', goal, spread(idx), max_neurons, neurons_to_add);
                        out = sim(model, inputs_tr(divideInd{2},:)')';
                        errors(idx) = mse(out_ref_tr(divideInd{2},:), out); %'Normalization', 'standard');
                    end
                    % Choose for best temperature prediction and train the
                    % new network
                    model = newrb(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},:)', goal, spread(min(errors) == errors), max_neurons, neurons_to_add);

                    best_spread = spread(min(errors) == errors);

                elseif strcmp(configuration_type, "cascade")

                    model = cell(1,2);
                    outputs_mod = zeros(2, length(divideInd{2}));
                    best_spread = zeros(1,2);
                    
                    % Fit for Tout
                    goal = 0; % MSE

                    for idx=1:length(spread)
                        model{1} = newrb(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},1)', goal, spread(idx), max_neurons, neurons_to_add);
                        errors(idx) = mse(out_ref_tr(divideInd{2},1)', sim(model{1}, inputs_tr(divideInd{2},:)')); %'Normalization', 'standard');
                    end
                    % Choose for best model
                    model{1} = newrb(inputs_tr(divideInd{1},:)', out_ref_tr(divideInd{1},1)', goal, spread(min(errors) == errors), max_neurons, neurons_to_add);
                    best_spread(1) = spread(min(errors) == errors);


                    % Fit for Mloss
                    goal = 20; % MSE

                    for idx=1:length(spread)
                        model{2} = newrb([inputs_tr(divideInd{1},:), out_ref_tr(divideInd{1},1)]', out_ref_tr(divideInd{1},2)', goal, spread(idx), max_neurons, neurons_to_add);
                        errors(idx) = mse( out_ref_tr(divideInd{2},2), sim(model{2}, [inputs_tr(divideInd{2},:), out_ref_tr(divideInd{2},1)]')' ); %'Normalization', 'standard');
                    end
                    % Choose the best model
                    model{2} = newrb([inputs_tr(divideInd{1},:), out_ref_tr(divideInd{1},1)]', out_ref_tr(divideInd{1},2)', goal, spread(min(errors) == errors), max_neurons, neurons_to_add);
                
                    best_spread(2) = spread(min(errors) == errors);
                
                else
                    raise_unknown_configuration(configuration_type)
                end

                tr.topology = print_network_topology(model);
                tr.divideInd = divideInd;
                tr.spread = best_spread;


            elseif strcmp(alternative, "random_forest")
                
                % Only one output
                if isscalar(output_vars_idx)

                    % Calibrate model
    
                    % Fit for Tout
                    model = TreeBagger(200, inputs_tr, out_ref_tr(:,1), 'Method', 'regression');

    
                % More than one output
                else
                    
                    if ~strcmp(configuration_type, "cascade")
                        % Only cascade
                        continue
    
                    end
                    % Calibrate model
    
                    % Fit for Tout
                    model{1} = TreeBagger(200, inputs_tr, out_ref_tr(:,1), 'Method', 'regression');
    
                    % Fit for Mlost
                    model{2} = TreeBagger(100, [inputs_tr, out_ref_tr(:,1)], out_ref_tr(:,2), 'Method', 'regression');
                
                end


            elseif strcmp(alternative, "gradient_boosting")
                % Only one output
                if isscalar(output_vars_idx)

                    % Calibrate model
    
                    % Fit for Tout, only needs to be run like this once, then the
                    % hiperparameters could be reused (as long as the training data does not
                    % change)
                    t = templateTree('Reproducible',true);
    
                    model = fitrensemble(inputs_tr, out_ref_tr(:,1), ...
                        'OptimizeHyperparameters','auto','Learners',t, ...
                        'HyperparameterOptimizationOptions',struct('AcquisitionFunctionName','expected-improvement-plus'), ...
                        'Options',statset('UseParallel',false), ...
                        'HyperparameterOptimizationOptions',struct('MaxObjectiveEvaluations',60));
        
                else
                % More than one output
                
                if ~strcmp(configuration_type, "cascade")
                    % Only cascade
                    continue

                end
                
                % Calibrate model
                % Fit for Tout, only needs to be run like this once, then the
                % hiperparameters could be reused (as long as the training data does not
                % change)
                t = templateTree('Reproducible',true);

                model{1} = fitrensemble(inputs_tr, out_ref_tr(:,1), ...
                    'OptimizeHyperparameters','auto','Learners',t, ...
                    'HyperparameterOptimizationOptions',struct('AcquisitionFunctionName','expected-improvement-plus'), ...
                    'Options',statset('UseParallel',false), ...
                    'HyperparameterOptimizationOptions',struct('MaxObjectiveEvaluations',60));
                
                % Fit for Mlost
                model{2} = fitrensemble([inputs_tr, out_ref_tr(:,1)], out_ref_tr(:,2), ...
                    'OptimizeHyperparameters','auto','Learners',t, ...
                    'HyperparameterOptimizationOptions',struct('AcquisitionFunctionName','expected-improvement-plus'), ...
                    'Options',statset('UseParallel',false), ...
                    'HyperparameterOptimizationOptions',struct('MaxObjectiveEvaluations',60));
                
                end


            elseif strcmp(alternative, "feedforward") || strcmp(alternative, "cascadeforwardnet")
                % Calibrate model
                [model, tr] = train_net(inputs_net, out_ref_net, net_type = alternative, divideInd=divideInd, configuration_type=configuration_type, trainFcn=train_algorithm);
                % if length(tr) > 1
                %     tr{1}.topology = print_network_topology(model);
                % else
                %     tr.topology = print_network_topology(model);
                % end
            else
                throw(MException('ann_training_batch:unknown_alternative', 'Alternative %s is unsupported', alternative))
            end

            out_mod_tr = evaluate_model(inputs_net, alternative, model);
            elapsed_time_training = toc(init_time_training);
            fprintf('Elapsed time for training the model: %.4f seconds\n', elapsed_time_training);


            init_time_validation = tic;
            out_mod_val = evaluate_model(inputs_val, alternative, model);
            elapsed_time_validation = toc(init_time_validation);

            % Display the elapsed time
            fprintf('Elapsed time for evaluating validation set: %.4f seconds\n', elapsed_time_validation);

            % Output filenames
            model_data_filename = sprintf("model_data_%s.mat", test_id);
            training_results_filename = sprintf("training_%s.csv", test_id);
            validation_results_filename = sprintf("validation_%s.csv", test_id);
        
            % % Save trained  / calibrated / fitted alternative
            % Define shared fields once
            aux.alternative = alternative;
            aux.configuration = configuration_type_str;
            aux.data_tr = data_tr;
            aux.data_val = data_val;
            aux.input_vars_idx = input_vars_idx;
            aux.output_vars_idx = output_vars_idx;
            aux.elapsed_time_validation = elapsed_time_validation;
            aux.elapsed_time_training = elapsed_time_training;
            aux.case_study = case_study_id;
            aux.system = system_to_model;
            aux.training_data_filename = filename+".csv";
            aux.validation_data_filename = validation_filename;
            aux.training_results_filename = training_results_filename;
            aux.validation_results_filename = validation_results_filename;
            aux.model_data_filename = model_data_filename;
            aux.auxiliary_id = auxiliary_id;
            
            % Assign to tr (struct or cell of structs)
            if length(tr) > 1
                for tr_idx = 1:length(tr)
                    tr{tr_idx} = set_fields(tr{tr_idx}, aux);
                end
            else
                tr = set_fields(tr, aux);
            end

            % Save model object
            name = sprintf("%s/%s", models_data_path, model_data_filename);
            save(name, "model", "tr") %'-append')
            fprintf('Saved model object and additional data in %s\n', name)
            
            % Save validation results as csv
            name = sprintf("%s/%s", results_path, validation_results_filename);
            writetable(array2table(out_mod_val, "VariableNames", output_var_names), name)
            fprintf('Saved validation results in %s\n', name)

            % Save training results as csv
            name = sprintf("%s/%s", results_path, training_results_filename);
            writetable(array2table(out_mod_tr, "VariableNames", output_var_names), name)
            fprintf('Saved training/calibration/tunning results in %s\n', name)

            diary off;
        
            if visualize_validation == true
                fig = represent_result( ...
                    data_tr, output_vars_idx, input_vars_idx, output_vars_sensor_types, ...
                    alternative=alternative, data_val=data_val, ...
                    model=model ...
                );
                fig.Name = test_id;
            end
        end
    end

end

function raise_unknown_configuration(input)
    throw(MException("evaluate_model:unsupported_input", "Unsupported configuration_type %s", input))
end

