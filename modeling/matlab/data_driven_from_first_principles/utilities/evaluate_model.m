function out = evaluate_model(inputs, varargin)
    %EVALUATE_MODEL Summary of this function goes here
    %   Detailed explanation goes here

    iP = inputParser;

    addRequired(iP, 'model_type', @isstring)
    addRequired(iP, 'model')
    % addParameter(iP, 'configuration_type',  "simple", @isstring)

    parse(iP,varargin{:})

    model = iP.Results.model;
    model_type = iP.Results.model_type;
    % configuration_type = iP.Results.configuration_type;

    if iscell(model)
        configuration_type = "cascade";
    else
        configuration_type = "simple";
    end


    out = zeros(size(inputs, 1), 2);

    if strcmp(model_type, "gaussian") || strcmp(model_type, "random_forest")
        % Gaussian

        % Gaussian approach only predicts one variable at a time
        % configuration_type = "cascade";

        if strcmp(configuration_type, "simple")
            
            [out, ~, ~] = predict(model, inputs);

        elseif strcmp(configuration_type, "cascade")

            % Predict first variable
            [out(:,1), ~, ~] = predict(model{1}, inputs);
    
            % Predict for the second variable
            [out(:,2), ~, ~] = predict(model{2}, [inputs, out(:,1)]);

        end

    elseif strcmp(model_type, "gradient_boosting")
        % only cascade
        % Predict first variable
        if length(model) > 1
            out(:,1) = predict(model{1}, inputs);
    
            % Predict for the second variable
            out(:,2) = predict(model{2}, [inputs, out(:,1)]);
        else
            out = predict(model, inputs);
        end

    elseif strcmp(model_type, "radial_basis") || strcmp(model_type, "radial_basis2")
        if strcmp(configuration_type, "simple")
            
            out = sim(model, inputs')';

        elseif strcmp(configuration_type, "cascade")

            try

            % Predict first variable
            out(:,1) = sim(model{1}, inputs')';
    
            % Predict for the second variable
            out(:,2) = sim(model{2}, [inputs, out(:,1)]')';

            catch

                % Predict first variable
                out(:,1) = sim(model{1}, inputs')';
        
                % Predict for the second variable
                out(:,2) = sim(model{2}, inputs')';

            end
        else
            raise_unknown_configuration(configuration_type)
        end

    elseif strcmp(model_type, "net") || strcmp(model_type, "ann") || strcmp(model_type, "feedforward") || strcmp(model_type, "cascadeforwardnet")
        if strcmp(configuration_type, "simple")
            
            out = model(inputs')';

        elseif strcmp(configuration_type, "cascade")

            % Predict first variable
            out(:,1) = model{1}(inputs')';
    
            % Predict for the second variable
            out(:,2) = model{2}([inputs, out(:,1)]')';
        else
            raise_unknown_configuration(configuration_type)
        end

    else
        throw(MException("evaluate_model:unsupported_model", "Unknown model %s", model_type))
    end

end

function raise_unknown_configuration(input)
    throw(MException("evaluate_model:unsupported_input", "Unsupported configuration_type %s", input))
end

