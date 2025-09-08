function [model, tr] = ann_training(inputs, outputs, varargin)

% ann_training. This is an utility function that initialializes a neural
% network object of the net_type type and trains it using inputs and 
% outputs, n_of_training times. 
% The most performant network is selected and returned together with the 
% training object

    iP = inputParser;
    
    addParameter(iP, 'net_type', "feedforward", @isstring)
    addParameter(iP, 'hiddenLayerSize', 10)
    addParameter(iP, 'divideInd', [])
    addParameter(iP, 'trainFcn', 'trainlm', @isstring)
    addParameter(iP, 'n_of_trainings', 10, @isinteger)
%     addParameter(iP, 'generate_report', false, check_num_scalar)

    parse(iP,varargin{:})
    hiddenLayerSize = iP.Results.hiddenLayerSize;
    divideInd = iP.Results.divideInd;
    net_type = iP.Results.net_type;
    n_of_trainings = iP.Results.n_of_trainings;
   
    % Create lists of variable names for inputs and outputs
    % input_var_names  = string( vars_table.Properties.VariableNames(input_vars_idx) );
    % output_var_names = string( vars_table.Properties.VariableNames(output_vars_idx) );

    % El nmero de parmetros ajustables debe de ser inferior a 1/30*n_muestras
    
    % Choose a Training Function
    % For a list of all training functions type: help nntrain
    % 'trainlm' is usually fastest.
    % 'trainbr' takes longer but may be better for challenging problems. % Bayesian Regularization backpropagation
    % 'trainscg' uses less memory. Suitable in low memory situations.
    trainFcn = iP.Results.trainFcn;

    % if size(inputs, 1) > size(inputs, 2)
    %     inputs = inputs';
    %     outputs = outputs';
    % end

    if strcmp(net_type, "feedforward")
        % Create a Feedforward Network
        net = fitnet(hiddenLayerSize,trainFcn); % Feedforward network


    elseif strcmp(net_type, "cascadeforwardnet")
        net = cascadeforwardnet(hiddenLayerSize,trainFcn);

    else
        throw(MException('ann_training:unsupported_net_type', 'Unsupported network type %s', net_type))
    end
    
    % Setup Division of Data for Training, Validation, Testing
    if isempty(divideInd)
        net.divideParam.trainRatio = 70/100;
        net.divideParam.valRatio = 15/100;
        net.divideParam.testRatio = 15/100;

    else
        net.divideFcn = 'divideind';
        net.divideParam.trainInd = divideInd{1,:};
        net.divideParam.valInd   = divideInd{2,:};
        net.divideParam.testInd  = divideInd{3,:};

        % entradas = vars_table{net.divideParam.trainInd,input_vars_idx};
        % salidas  = vars_table{net.divideParam.trainInd,output_vars_idx};
    end

    % Performance weights
    % TODO: Should be a parameter
    errorWeights = {1.0; 0.5}; % Give the first output double the weight

    net.performParam.normalization = 'standard';
    net.performParam.regularization = 0.2;
    net.performParam.normalization = 'standard';
    
    % Normalize data. Method: Z-score
    % Update 202403. This is not really needed, networks when they are
    % created already include some "processFcns":
    % net.inputs{1}.processFcns -> {'mapminmax'}
    % net.outputs{2}.processFcns -> {'mapminmax'}

    % Train the network several times
    mean_errors = 9999 * ones(1,n_of_trainings);
    nets = cell(1,n_of_trainings); trs = cell(1,n_of_trainings);
    for train_idx=1:n_of_trainings
    % for train_idx=1
        
        % TODO: Should be a parameter
        net.trainParam.showWindow = false;
        net.trainParam.showCommandLine = false;

        % Train the Network
        % Nomenclature: x for inputs and t for targets
        % TODO: Add weights to perform during training
        [nets{train_idx},trs{train_idx}] = train(net,inputs,outputs);
        
        %% Test the Network
        % Error for each iteration
        mean_errors(train_idx) = perform(nets{train_idx}, outputs, nets{train_idx}(inputs), errorWeights);

        fprintf('Error in iteration %d: %.3f\n', train_idx, mean_errors(train_idx))
    end

    min_error_idx = find(min(mean_errors) == mean_errors);
    model = nets{min_error_idx};
    tr = trs{min_error_idx};
    tr.error_test = mean_errors(min_error_idx);

    fprintf('Training alg.: %s | Chose net with idx=%d, topology: %s since it has the best performance\n', trainFcn, min_error_idx, print_network_topology(net))

end