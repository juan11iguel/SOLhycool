function [Tout, Mw_lost, Pth, Pe] = wct_model_PSA(Tamb, HR, Tin, q, w_fan)
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

    persistent net_wct

    if isempty(net_wct)
        load("wct_model_data_pid2024.mat", "net_wct")
    end
    
    max_values = 1.1*[38.7500   89.2500   40.9400   24     93.4161];
    min_values = 0.9*[9.0600   10.3300   31.1700    5.7049 21];
    vars = ["Tamb", "HR", "Tin", "q", "w_fan"];

    for idx=1:length(vars)
        var = vars(idx); value = eval(var);
        if value > ceil(max_values(idx)) || value < floor(min_values(idx))
            raise_error(var, value, min_values(idx), max_values(idx))
        end
    end


%     [Twct_out, M_lost_Pewct]
    out = evaluate_trained_ann([Tamb, HR, Tin, q, w_fan], net_wct); % ºC, L/min
    [Tout, Mw_lost] = deal(out(1), out(2));

    Pe = power_consumption(w_fan); %+ ConsumoElectrico_P7(SC_pump_wct); % kWe
    Pth = q/3.6*(Tin - Tout)*4.186; % Mwct: m³/h -> kg/s; kWth
    

    function y = evaluate_trained_ann(x, ann)
        x_n = (x-ann.media_in)./ann.desviacion_in;
        
        y_n = ann.net(x_n');
    
        y = y_n .* ann.desviacion_out' + ann.media_out';
    end

    function P_fan = power_consumption(w_fan)
        
        % w_wct_fan (%) -> P_wct_fan (kW)   
               p1 =      0.4118  ;
               p2 =      -11.54   ;
               p3 =       189.4   ;
               
        P_fan=(p1.*w_fan.^2 + p2.*w_fan + p3)/1000; %kW
        
    end


    function raise_error(variable, value, lower_limit, upper_limit)
        msg = sprintf("Input %s=%.2f is outside limits (%.2f < %s < %.2f)", string(variable), value, lower_limit, string(variable), upper_limit);
        throw(MException('WCT_model:invalid_input', msg))
    end

end