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
        % Accept scalars or vectors for inputs (vectorized support)
        Tamb double
        HR double
        Tin double
        q double
        w_fan double
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
        % Return scalars or column vectors
        Tout (:,1) double
        Ce (:,1) double
        Cw (:,1) double
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
        % fprintf('I am wct_model, man better pass me some model\n')
        load(options.model_data_path, "model");
    end

    % fprintf("wct model path: %s\n", options.model_data_path)

    % Limits of flow rate considering the number of WCTs in parallel
    options.ub(4)=options.ub(4)*options.n_wct;
    options.lb(4)=options.lb(4)*options.n_wct;

    % Determine whether inputs are vectors (any non-scalar input)
    is_vector_input = ~(isscalar(Tamb) && isscalar(HR) && isscalar(Tin) && isscalar(q) && isscalar(w_fan));

    % Compute the batch size and expand scalars to match
    N = max([numel(Tamb), numel(HR), numel(Tin), numel(q), numel(w_fan)]);
    Tamb_v  = expand_to_length(Tamb,  N);
    HR_v    = expand_to_length(HR,    N);
    Tin_v   = expand_to_length(Tin,   N);
    q_v     = expand_to_length(q,     N);
    w_fan_v = expand_to_length(w_fan, N);

    % Prepare bounds for (optional) scalar validation
    max_values = options.ub;
    min_values = options.lb;

    % Validate only in scalar mode; skip when vectorized to speed up
    valid_inputs = true;
    if ~is_vector_input
        vars = ["Tamb", "HR", "Tin", "q", "w_fan"];
        vals = [Tamb, HR, Tin, q, w_fan];
        for idx=1:length(vars)
            if vals(idx) > ceil(max_values(idx)) || vals(idx) < floor(min_values(idx))
                if options.raise_error_on_invalid_inputs
                    raise_error(vars(idx), vals(idx), min_values(idx), max_values(idx))
                else
                    if ~options.silence_warnings
                        warning("%s outside limits (%.2f <! %.2f <! %.2f)", vars(idx), min_values(idx), vals(idx), max_values(idx))
                    end
                    valid_inputs = false;
                end
            end
        end
    end

    if valid_inputs
        % Build input matrix with samples in rows (N x F)
        inputs_mat = [Tamb_v, HR_v, Tin_v, q_v/options.n_wct, w_fan_v];

        % Predict first variable: Tout (N x 1)
        Tout = evalModel(model{1}, inputs_mat);

        % Predict the second variable: Cw uses inputs and Tout
        Cw = evalModel(model{2}, [inputs_mat, Tout]);
        Cw = max(0.0, Cw * options.n_wct); % l/h, element-wise

        if length(model) > 2
            % Electrical consumption is another model
            Ce = evalModel(model{3}, [inputs_mat, [Tout, Cw]]);
            Ce = max(0.0, Ce);
        else
            % Otherwise estimate consumption using the polynomial
            Ce = options.n_wct * power_consumption(w_fan_v) * 1e-3; % kWe
        end
    else
        % Invalid scalar inputs: bypass wet cooler
        Tout = Tin_v;
        Ce   = zeros(N,1);
        Cw   = zeros(N,1);
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
    
    function y = evalModel(model, X)
        % Evaluate model for vectorized inputs.
        % X is expected to be N x F (samples in rows). This function
        % adapts X to the required shape for each model type.
        if isa(model, 'network')
            % Neural networks expect inputs as features-by-N
            if isvector(X)
                X = X(:)'; % make it 1 x F
            end
            X_nn = X';     % F x N
            y_pred = model(X_nn); % usually 1 x N for regression
            y = y_pred(:); % N x 1
        elseif isa(model, 'RegressionGP') || isa(model, 'classreg.learning.regr.CompactRegressionGP')
            % GPR expects rows as samples (N x F)
            if iscolumn(X)
                X = X';
            end
            y = predict(model, X);
            if ~iscolumn(y)
                y = y(:);
            end
        else
            error('Unsupported model type: %s', class(model));
        end
    end

    function v = expand_to_length(x, N)
        % Expand scalar to length N; validate vector lengths
        if isscalar(x)
            v = repmat(x, N, 1);
        else
            if numel(x) ~= N
                error('Inputs must be scalars or vectors of the same length.');
            end
            v = x(:);
        end
    end

end