function [Tout, Ce, Cw] = wct_model(Tamb, HR, Tin, q, w_fan, options)
    % ANN model for the WASCOP wet cooling tower located at PSA
    % - Inputs
    % 	- $T_{amb}$  $[\degree C]$ Ambient temperature (Dry bulb)
    %   - $HR$ $[\%]$ Relative humidity
    % 	- $T_{in}$  $[\degree C]$ Inlet temperature
    % 	- $q$  $[m3/h]$ Volumetric flow of fluid to cool
    %   - $w_fan$ $[%]$ Fan load (0-100 -> 0-max_freq Hz) 
    % - Outputs
    % 	- $Tout$  $[\degree C]$ Outlet temperature
    % 	- $Mw_lost$  $[m^3/h]$ Water consumption
    %   - $Pth$ $[kWth]$ Thermal power dissipated
    %   - $Pe$ $[kWe]$ Electrical power consumed
    % - NOTE. On first run, the function will attempt to load
    %         the ANN object "net_wct_elche" from wct_model_data.mat

    arguments (Input)
        Tamb (1,1) double
        HR (1,1) double
        Tin (1,1) double
        q (1,1) double
        w_fan (1,1) double
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.model_data_path string = fullfile(fileparts(mfilename('fullpath')), "wct_model_data.mat")
        options.lb (1,5) double = 0.9*[9.0600   10.3300   31.1700    5.7049         0];
        options.ub (1,5) double = 1.1*[38.7500   89.2500   40.9400   24.8400   93.4161];
        options.silence_warnings logical = false
        options.ce_coeffs (1,:) double = [0.4118, -11.54, 189.4]; % Default quadratic coefficients
    end

    arguments (Output)
        Tout (1,1) double
        Ce (1,1) double
        Cw (1,1) double
    end

    persistent model

    if isempty(model)
        load(options.model_data_path, "model");
    end
    
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
                    warning("%s outside limits (%.2f <! %s <! %.2f)", var, min_values(idx), value, max_values(idx))
                end
                valid_inputs = false;
            end
        end
    end

    inputs = [Tamb, HR, Tin, q, w_fan];
    out = zeros(size(inputs, 1), 2);
    if valid_inputs
        % Predict first variable
        [out(:,1), ~, ~] = predict(model{1}, inputs);
        % Predict for the second variable
        [out(:,2), ~, ~] = predict(model{2}, [inputs, out(:,1)]);
        [Tout, Cw] = deal(out(1), out(2));
        Ce = power_consumption(w_fan); %+ ConsumoElectrico_P7(SC_pump_wct); % kWe
        % Pth = q/3.6*(Tin - Tout)*4.186; % Mwct: m³/h -> kg/s; kWth
    else
        % Skip wet cooler
        Tout = Tin;
        Ce = 0;
        Cw = 0;
    end

    function P_fan = power_consumption(w_fan)
        % Use polyval for fan power calculation
        P_fan = max(0, polyval(options.ce_coeffs, w_fan)); % kW
    end

    function raise_error(variable, value, lower_limit, upper_limit)
         msg = sprintf("Input %s=%.2f is outside limits (%.2f > %s > %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
%         throw(MException('model:invalid_input', msg))
         warning(msg)
    end

end