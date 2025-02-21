function [Tout, Ce] = dc_model(Tamb, Tin, q, w_fan, options)
    % ANN model for the WASCOP DC cooler located at PSA
    % - Inputs
    %   - $T_{amb}$  $[\degree C]$ Ambient temperature (Dry bulb)
    %   - $T_{in}$  $[\degree C]$ Inlet temperature to dry cooling system
    %   - $q$  $[m3/h]$ Volumetric flow of fluid to cool
    %   - $w_fan$ $[%]$ Fan load (0-100 -> 0-max_freq Hz) 
    % - Outputs
    %   - $Tout$  $[\degree C]$ Outlet temperature
    %   - $Ce$ $[kWe]$ Electrical power consumed
    % - NOTE. On first run, the function will attempt to load
    %         the ANN object "net_dc" from dc_model_data.mat

    arguments (Input)
        Tamb (1,1) double
        Tin (1,1) double
        q (1,1) double
        w_fan (1,1) double
        options.raise_error_on_invalid_inputs (1,1) logical = false
        options.model_data_path string = fullfile(fileparts(mfilename('fullpath')), "dc_model_data.mat")
        options.silence_warnings logical = false
    end

    arguments (Output)
        Tout (1,1) double
        Ce (1,1) double
    end

    persistent model

    if isempty(model)
        load(options.model_data_path, "model");
    end
    
    max_values = 1.1*[38.7500   41.9200, 24.1543, 99.1800];
    min_values = 0.9*[9.0600   33.1600, 5.2211, 11];
    vars = ["Tamb", "Tin", "q", "w_fan"];

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

    if valid_inputs
        [Tout, ~, ~] = predict(model, [Tamb, Tin, w_fan, q]);
        Ce = power_consumption(w_fan); %+ ConsumoElectrico_P7(SC_pump_wct); % kWe
        % Pth = Mwct/3.6*(Twct_in - Twct_out)*4.186; % Mwct: m³/h -> kg/s; kWth
    else
        % Skip dry cooler
        Tout = Tin;
        Ce = 0;
    end

    function P_fan = power_consumption(w_fan)
    % w_dc_fan (%) -> P_dc_fan (kW)
    %      f(x) = p1*x^4 + p2*x^3 + p3*x^2 + p4*x + p5
    % Coefficients (with 95% confidence bounds):
           p1 =  -0.0002431 ;
           p2 =     0.04761 ;
           p3 =        -2.2 ;
           p4 =       48.63 ;
           p5 =      -295.6 ;
    
    P_fan=max((p1.*w_fan.^4 + p2.*w_fan.^3 + p3.*w_fan.^2 + p4.*w_fan + p5)/1000, 0); %kW
    
    end
    
    function raise_error(variable, value, lower_limit, upper_limit)
        msg = sprintf("Input %s=%.2f is outside limits (%.2f < %s < %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
        throw(MException('model:invalid_input', msg))
    end

end