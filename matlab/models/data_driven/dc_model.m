function [Tout, Pe] = dc_model_PSA(Tamb, Tin, q, w_fan)
    % ANN model for the WASCOP DC cooler located at PSA
    % - Inputs
    % 	- $T_{amb}$  $[\degree C]$ Ambient temperature (Dry bulb)
    % 	- $T_{in}$  $[\degree C]$ Inlet temperature to dry cooling system
    % 	- $q$  $[m3/h]$ Volumetric flow of fluid to cool
    %   - $w_fan$ $[%]$ Fan load (0-100 -> 0-max_freq Hz) 
    % - Outputs
    % 	- $Tout$  $[\degree C]$ Outlet temperature
    %   - $Pe$ $[kWe]$ Electrical power consumed
    % - NOTE. On first run, the function will attempt to load
    %         the ANN object "net_dc" from dc_model_data.mat

    persistent net_dc

    if isempty(net_dc)
        load("dc_model_data.mat", "net_dc")
    end
    
    max_values = 1.1*[38.7500   41.9200, 24.1543, 99.1800];
    min_values = 0.9*[9.0600   33.1600, 5.2211, 11];
    vars = ["Tamb", "Tin", "q", "w_fan"];

    for idx=1:length(vars)
        var = vars(idx); value = eval(var);
        if value > ceil(max_values(idx)) || value < floor(min_values(idx))
            raise_error(var, value, min_values(idx), max_values(idx))
        end
    end


    Tout = evaluate_trained_ann([Tamb, Tin, q, w_fan], net_dc); % ºC

    Pe = power_consumption(w_fan); %+ ConsumoElectrico_P7(SC_pump_wct); % kWe
    % Pth = Mwct/3.6*(Twct_in - Twct_out)*4.186; % Mwct: m³/h -> kg/s; kWth
    

    function y = evaluate_trained_ann(x, ann)
        x_n = (x-ann.media_in)./ann.desviacion_in;
        
        y_n = ann.net(x_n');
    
        y = y_n .* ann.desviacion_out' + ann.media_out';
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
    
    P_fan=(p1.*w_fan.^4 + p2.*w_fan.^3 + p3.*w_fan.^2 + p4.*w_fan + p5)/1000; %kW
    
    end
    
    function raise_error(variable, value, lower_limit, upper_limit)
        msg = sprintf("Input %s=%.2f is outside limits (%.2f < %s < %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
        throw(MException('DC_model:invalid_input', msg))
    end

end