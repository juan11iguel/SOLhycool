
function [model, tr] = train_net(inputs, outputs, varargin)

% This function trains a model based on ANN using the specificied
% configuration in configuration_type. Several networks are trained with 
% different number of layers and neurons per layer, the most performant one
% is selected.

    % While two-layer feedforward networks can potentially learn virtually
    % any input-output relationship, feedforward networks with more layers
    % might learn complex relationships more quickly. For most problems, 
    % it is best to start with two layers, and then increase to three 
    % layers, if the performance with two layers is not satisfactory.
    % neuronas = {5};
    % neuronas = {5, 10, 15, [10, 5], [8, 3], [15 5]};

    iP = inputParser;
    
    addParameter(iP, 'net_type', "feedforward", @isstring)
    addParameter(iP, 'hiddenLayerSizes', {5, 10, 20, [5, 5], [5, 10], [10 5], [10 10]})
    addParameter(iP, 'divideInd', [])
    addParameter(iP, 'trainFcn', "trarinlm", @isstring)
    addParameter(iP, 'configuration_type', "simple", @isstring)
%     addParameter(iP, 'generate_report', false, check_num_scalar)

    parse(iP,varargin{:})
    hiddenLayerSizes = iP.Results.hiddenLayerSizes;
    divideInd = iP.Results.divideInd;
    net_type = iP.Results.net_type;
    configuration_type = iP.Results.configuration_type;
    errorWeights = {1;0.5};
    trainFcn = iP.Results.trainFcn;

    if size(inputs, 1) > size(inputs, 2)
        inputs = inputs';
        outputs = outputs';

        warning('train_net:wrong_orientation', 'Transposing data')
    end

    if strcmp(configuration_type, "simple")
        [model, tr] = train_simple_network(inputs, outputs, divideInd);
        tr.topology = print_network_topology(model);

    elseif strcmp(configuration_type, "cascade")
        model = cell(1,2);
        tr = cell(1,2);

        % Train network for the first output
        [model{1}, tr{1}] = train_simple_network(inputs, outputs(1,:), divideInd);
        tr{1}.topology_individual = print_network_topology(model{1});
        
        % Evaluate the output from the first network and use it as input for the
        % second network
        % y = evaluate_trained_ann(table2array(vars_table(tr_tout.trainInd, input_vars_idx)), net_tout); %#ok<*AGROW>
        y = model{1}(inputs);
        inputs = [inputs; y];

        % Train the second network
        [model{2}, tr{2}] = train_simple_network(inputs, outputs(2,:), {tr{1}.trainInd; tr{1}.valInd; tr{1}.testInd});
        tr{2}.topology_individual = print_network_topology(model{2});
    
        topology = print_network_topology(model);
        tr{1}.topology = topology;
        tr{2}.topology = topology;

    else
        error('train_net:unsupported_input', 'Unknown net_type')
    end


    % Nested function to train each net configuration and choose the best
    % one
    function [model, tr] = train_simple_network(inputs, outputs, divideInd)
        
        nets = cell(length(hiddenLayerSizes));
        trs = cell(length(hiddenLayerSizes));
        errors = 9999 * ones(1, length(hiddenLayerSizes));

        for idx=1:length(hiddenLayerSizes)

            [nets{idx}, trs{idx}] = ann_training(inputs, outputs, hiddenLayerSize = hiddenLayerSizes{idx}, divideInd=divideInd, net_type=net_type, trainFcn=trainFcn); 
            errors(idx) = perform(nets{idx}, outputs, nets{idx}(inputs), errorWeights);

        end

        % TODO: Refactor performance metric evaluation
        % Seleccionar de entre las opciones el que tenga menor error
        % Suma total de errores normalizados, se le da un 20 mas de peso a Tout

        best_net_idx = find(min(errors)==errors);
    
        % fprintf('Best net is with hidden layers: %s, since error = %.2f\n', string(hiddenLayerSize), errors(best_net_idx))
        if length(hiddenLayerSizes{best_net_idx}) > 1
            fprintf('Best net is with %d-%d neurons, since errors_total = %.2f\n', ...
                hiddenLayerSizes{best_net_idx}(1), hiddenLayerSizes{best_net_idx}(2), errors(best_net_idx))
        else
            fprintf('Best net is with %d neurons, since errors_total = %.2f\n', ...
                hiddenLayerSizes{best_net_idx}, errors(best_net_idx))
        end

        model = nets{best_net_idx};
        tr = trs{best_net_idx};

    end

end