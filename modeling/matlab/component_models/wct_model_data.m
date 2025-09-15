function [Tout, Ce, Cw] = wct_model_data(Tamb, HR, Tin, q, w_fan, options_struct, options)
    % WCT_MODEL  Predicts outlet temperature, electrical and water consumption for the WASCOP wet cooling tower.
    % 
    % Inputs:
    %   Tamb    - Ambient temperature (ºC)
    %   HR      - Relative humidity (%)
    %   Tin     - Inlet temperature (ºC)
    %   q       - Volumetric flow rate (m³/h)
    %   w_fan   - Fan load (%)
    %   options - Struct with optional fields:
    %       .raise_error_on_invalid_inputs (logical)
    %       .model_data_path (string)
    %       .lb, .ub (double vectors)
    %       .silence_warnings (logical)
    %       .ce_coeffs (double vector)
    %
    % Outputs:
    %   Tout    - Outlet temperature (ºC)
    %   Ce      - Electrical consumption (kWe)
    %   Cw      - Water consumption (l/h)
    %
    % Notes:
    %   Uses a data-driven model that can be called with the predict function
    %   loaded from wct_model_data.mat.

    % To force MATLAB to package the Deep Learning Toolbox when exporting
    % the code
    %#function network

    arguments (Input)
        Tamb (1,1) double
        HR (1,1) double
        Tin (1,1) double
        q (1,1) double
        w_fan (1,1) double
        % Using keyword arguments does not work when exporting the model to
        % python. Offer an alternative
        options_struct = []
        options.model = []
        options.n_wct (1,1) double {mustBeInteger,mustBePositive} = 1
        options.ce_coeffs (1,:) double = [0.4118, -11.54, 189.4]; % Default quadratic coefficients
        options.model_data_path string = fullfile(fileparts(mfilename('fullpath')), "wct_model_data.mat")
        options.lb (1,5) double = [0.1    0.1     5.0    5.0       0.];
        options.ub (1,5) double = [50.0   99.99   55.0   24.8400   95.];
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.silence_warnings logical = false
    end

    arguments (Output)
        Tout (1,1) double
        Ce (1,1) double
        Cw (1,1) double
    end

    persistent model

    % Terrible
    % Apply optional arguments from the alternative struct if provided
    if ~isempty(options_struct)
        apply_options();
    end

    if ~isempty(options.model)
        model = options.model;
    elseif isempty(model)
        fprintf('I am wct_model, man better pass me some model\n')
        load(options.model_data_path, "model");
    end

    % fprintf("wct model path: %s\n", options.model_data_path)

    % Limits of flow rate considering the number of WCTs in parallel
    options.ub(4)=options.ub(4)*options.n_wct;
    options.lb(4)=options.lb(4)*options.n_wct;
    
    max_values = options.ub;
    min_values = options.lb;
    vars = ["Tamb", "HR", "Tin", "q", "w_fan"];

    valid_inputs = true;
    for idx=1:length(vars)
        var = vars(idx); value = eval(var);
        if value > ceil(max_values(idx)) || value < floor(min_values(idx))
            if options.raise_error_on_invalid_inputs
                raise_error(var, value, min_values(idx), max_values(idx))
            else
                if ~options.silence_warnings
                    warning("%s outside limits (%.2f <! %.2f <! %.2f)", var, min_values(idx), value, max_values(idx))
                end
                valid_inputs = false;
            end
        end
    end

    if valid_inputs
        inputs = [Tamb, HR, Tin, q/options.n_wct, w_fan];

        % Predict first variable
        Tout = evalModel(model{1}, inputs);
        % Predict for the second variable
        Cw = evalModel(model{2}, [inputs, Tout]);
        Cw = max(0.0, Cw * options.n_wct); % l/h
        
        if length(model) > 2
            % Electrical consumption is another GPR
            Ce = evalModel(model{3}, [inputs, [Tout, Cw]]);
            Ce = max(0.0, Ce);
        else
            % Otherwise estimate consumption using the polynomium
            Ce = options.n_wct * power_consumption(w_fan) * 1e-3; % kWe
        end
        % Pth = q/3.6*(Tin - Tout)*4.186; % Mwct: m³/h -> kg/s; % kWth
    else
        % Skip wet cooler
        Tout = Tin;
        Ce = 0;
        Cw = 0;
    end

    function P_fan_W = power_consumption(w_fan)
        % Use polyval for fan power calculation
        P_fan_W = max(0, polyval(options.ce_coeffs, w_fan)); % W
    end

    function raise_error(variable, value, lower_limit, upper_limit)
         msg = sprintf("Input %s=%.2f is outside limits (%.2f > %s > %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
%         throw(MException('model:invalid_input', msg))
         warning(msg)
    end

    function apply_options()
        for field_name = fieldnames(options)'
            field_name = string(field_name);
            % fprintf('%s\n', field_name)
            if isfield(options_struct, field_name)
                % fprintf('Using option from struct: %s: %s\n', field_name, options_struct.(field_name))
                options.(field_name) = options_struct.(field_name);
            end
        end
    end
    
    function y = evalModel(model, x)
        % Detect class
        if isa(model, 'network')
            % Neural network expects column input
            if isrow(x)
                x = x';
            end
            y = model(x);  % same as sim(model,x)
        elseif isa(model, 'RegressionGP')
            % GPR expects row input
            if iscolumn(x)
                x = x';
            end
            y = predict(model, x);
        else
            error('Unsupported model type: %s', class(model));
        end
    end

end