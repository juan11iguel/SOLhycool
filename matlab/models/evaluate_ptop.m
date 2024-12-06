function [costes, detailed] = evaluate_ptop(x, Tamb_C, HR, Mv_kgs, Tv_C, varargin)%, R1, R2, mc_m3h, Tdc_out, Twct_out)

    R1  = x(1);
    R2  = x(2);
    
    % Check if mc_m3h is provided as an input
    if nargin > 5 && ~isempty(varargin{1})
        mc_m3h = varargin{1};
        Tdc_out = x(3);
        Twct_out = x(4);
    else
        % Default value or handling for mc_m3h when not provided
        mc_m3h  = x(3); % m3/h
        Tdc_out = x(4);
        Twct_out = x(5);
    end
    % Tc_in  = x(6);

    % Create an input parser object
    % p = inputParser;
    % 
    % % Define the optional parameter 'exportResults' with a default value of false
    % addOptional(p, 'export_results', false, @islogical);
    % addOptional(p, 'log', false, @islogical)

    % Parse the inputs
    % parse(p, varargin{:});
    % exportResults = p.Results.export_results;
    % log = p.Results.log;
    
    % [~, ~, ~, ~, ~, ~, Twb] = Psychrometricsnew('Tdb', Tamb_C, 'phi', HR, 'P', 101.325);

    % Restrictions. Checked in function check_restrictions
    % deltaT_min = 1;  % Minimum temperature difference between vapor and condenser outlet (ºC)
    % deltaTc_min = 1; % Mnimum temperature difference between inlet and outlet of condenser (ºC)
    % Cw_max = 200;    % Maximum allowed water cost (L/h)
    w_fan_min = 0;   % (%)
    w_fan_wct_max = 93.4; % (%)
    w_fan_dc_max  = 99.18; % (%)
    mc_m3h_min = 12; % Minimum condenser flow rate (m3/h)
    mc_m3h_max = 24; % Maximum condenser flow rate (m3/h)
    % mc_kgs_max = mc_m3h_max*3600*densW(25, Pc); % m3/h -> kg/s
    % Tc_out_max = Tv_C - deltaT_min; % Maximum condenser outlet temperature (ºC)
    % Tc_in_max  = Tc_out_max - deltaTc_min; % Maximum condenser inlet temperature (ºC)
    % Tc_in_min = Twb; % Minimum condenser temperature (ºC)
    mdc_min = 5;    % Imposed by DC model (m3/h)
    mwct_min = 5.7; % Imposed by WCT model (m3/h)

    % Tdc_in_model_min = 33.16; % Minimum temperature evaluated in DC model (ºC)
    % Tdc_in_model_max = 41.92; % Maximum temperature evaluated in DC model (ºC)
    % Twct_in_model_min = 31.17; % Minimum temperature evaluated in WCT model (ºC)
    % Twct_in_model_max = 40.94; % Maximum temperature evaluated in WCT model (ºC)
    

    A = []; b = []; Aeq = []; beq = [];
    options_fmincon = optimoptions(@fmincon,'Display','none');%, 'UseParallel', true); % 'Algorithm','sqp',

    % Check direct limits
    if R1>1 || R1<0
        throw(MException('evaluate_ptop:invalid_input','R1 (%.2f) outisde of range [0,1]', R1))
    end
    if R2>1 || R2<0
        throw(MException('evaluate_ptop:invalid_input','R2 (%.2f) outisde of range [0,1]', R2))
    end
    if mc_m3h>mc_m3h_max || mc_m3h<mc_m3h_min
        throw(MException('evaluate_ptop:invalid_input','mc_m3h (%.2f) outisde of range [%.2f,%.2f]', mc_m3h, mc_m3h_min, mc_m3h_max))
    end
    % if Tdc_out>Tc_in_max || Tdc_out<Tc_in_min
    %     throw(MException('evaluate_ptop:invalid_input','Tdc_out (%.2f) outisde of range [%.2f,%.2f]', Tdc_out, Tc_in_min, Tc_in_max))
    % end
    % if Twct_out>Tc_in_max || Twct_out<Tc_in_min
    %     throw(MException('evaluate_ptop:invalid_input','Twct_out (%.2f) outisde of range [%.2f,%.2f]', Twct_out,Tc_in_min ,Tc_in_max))
    % end

    mdc = mc_m3h*(1-R1);
    mwct = mc_m3h*(R1*(1-R2)+R2);

    % Calculate Tc_in from given R1, R2, mc, Tdc_out and Twct_out
    Tc_in = (1-R1)*(1-R2)*Tdc_out + (R1*(1-R2)+R2)*Twct_out;

    % Evaluate surface condenser model
    [Tc_out, Ce_c, Pth] = surface_condenser_model(Mv_kgs, Tv_C, mc_m3h, Tc_in);
    % Tc_out = Tc_in + Mv_kgs*enthalpySatVapTW(Tv_C)/(mc_kgs*cpW(Tc_in, Pc));

   
    % Evaluate combined model to obtain consumptions
    
    % Check inlet temperature limits
    % DC
    % nueva estrategia, si alguna restriccion del modelo no se cumple,
    % combined_model hace que la salida del componente sea igual que a la
    % entrada
    Tdc_in = Tc_out;
    
    % WCT
    % nueva estrategia, si alguna restriccion del modelo no se cumple,
    % combined_model hace que la salida del componente sea igual que a la
    % entrada
    Twct_in = ( R1*Tc_out + ((1-R1)*R2)*Tdc_out ) / ( ((1-R1)*R2+R1) );


    % Solve w_dc_fan and w_wct_fan
    if mdc>mwct_min
        % DC working
        fun = @(x)calculo_w_dc(x, Tdc_out, Tamb_C, mdc, Tdc_in);
        lb = w_fan_min; ub = w_fan_dc_max; x0 = 50;

        w_dc_fan = fmincon(fun,x0,A,b,Aeq,beq,lb,ub,[],options_fmincon);

        % Evaluate if a solution was found
        try
            [Tout, ~] = dc_model_PSA(Tamb_C, Tdc_in, mdc, w_dc_fan);
        catch
            Tout=inf;

            % if log
            %     fprintf('No feasible fan velocity (DC) found to obtain Tout = %.2f (%.2f), given  a Tin=%.1f, Tamb=%.1f, q=%.1f\n', ...
            %         Tdc_out, Tout, Tdc_in, Tamb_C, mdc)
            % end
        end
        if abs(Tdc_out-Tout) > 0.01
            % No feasible fan speed was found, deactivate
            w_dc_fan = 0;
            
        end
    else
        w_dc_fan = 0;
    end
        
    if mwct>mwct_min
        % WCT working
        fun = @(x)calculo_w_wct(x, Twct_out, Tamb_C, HR, mwct, Twct_in);
        lb = w_fan_min; ub = w_fan_wct_max; x0 = 50;

        w_wct_fan = fmincon(fun,x0,A,b,Aeq,beq,lb,ub,[],options_fmincon);

        % Evaluate if a solution was found
        try
            [Tout, ~] = wct_model_PSA(Tamb_C, HR, Twct_in, mwct, w_wct_fan);
        catch 
            Tout=inf;
        end
        if abs(Twct_out-Tout) > 0.5
            % No feasible fan speed was found, deactivate
            w_wct_fan = 0;

            % if log
            %     fprintf('No feasible fan velocity (WCT) found to obtain Tout = %.2f (%.2f), given  a Tin=%.1f, Tamb=%.1f, HR=%.0f, q=%.1f\n', ...
            %         Twct_out, Tout, Twct_in, Tamb_C, HR, mwct)
            % end
        end
    else
        w_wct_fan = 0;
    end
   

    try
        [Tout, Cw, Ce_cc, d] = combined_model(Tamb_C, HR, mc_m3h, Tc_out, R1, R2, w_dc_fan, w_wct_fan);
    catch ME
        if strcmp(ME.identifier, 'WCT_model:invalid_input') || strcmp(ME.identifier, 'DC_model:invalid_input')
            if contains(ME.message, 'Tin')
                % Water recirculating from outlet of DC to WCT is colder
                % than minimum evaluated temperature at WCT
                warning("evaluate_ptop:unfeasible_operation", "primo has evaluao algo sin sentido")
                coste_e = 1e6;
                coste_w = 1e6;
                costes = [coste_e, coste_w];

                return
            end
        else 
            throw(ME)
        end
    end

    % Cost before evaluating if operation point within restrictions
    coste_e = Ce_cc + Ce_c; % kWhe
    coste_w = Cw; % l/h
    
    % Evaluate restrictions are not violated
    % En teoria, Tout==Tc_in, a menos que no se pueda alcanzar
    % referencia por saturar alguna variable como ventilador
    if abs(Tc_in-Tout) > 0.1
        % throw(MException('evaluate_ptop:model_error','Esto no esta buen hulio'))
        % The selected operation point is not feasible since one of the
        % setpoints (Tdc_out or Twct_out) saturates its actuator

        coste_e = 1.01e6;
        coste_w = 1.01e6;
    end

    % Maximum water consumption
    % if Cw > Cw_max
    %     coste_w = 1e6;
    % end
    
    % Inputs
    % d.Tamb = Tamb_C;
    % d.HR = HR;
    d.Tc_out = Tc_out;
    % Cooling requirements
    d.Tv = Tv_C;
    d.Mv = Mv_kgs;
    d.Pth = Pth;
    % Decision variables
    % d.R1 = R1;
    % d.R2 = R2;
    % d.q_c = mc_m3h; 
    % d.Tdc_out = d.Tdc_out;
    % d.Twct_out = d.Twct_out;

    % Outputs
    d.Tc_in = Tc_in;
    d.Ce = coste_e;
    d.Cw = coste_w;

    d.Ce_c = Ce_c;

    % Limits
    % d.Cw_max = Cw_max;
    d.q_c_min = mc_m3h_min;
    d.q_c_max= mc_m3h_max;
    d.q_dc_min = mdc_min;
    d.q_wct_min = mwct_min;
    % d.w_fan_min=w_fan_min;
    % d.w_fan_dc_max = w_fan_dc_max;
    % d.w_fan_wct_max = w_fan_wct_max;
    % d.Pth = Mv_kgs*enthalpySatVapTW(Tv_C);

    detailed = d;

    costes = [coste_e, coste_w];

    % if exportResults
    %     result_id = sprintf('ptop_Tamb%.0f_HR%.0f_Tv%.0f_Pth%.0f_R1%.0f_R2%.0f_mc%.1f_Tdc%.1f_Twct%.1f', ...
    %                         Tamb_C, HR, Tv_C, d.Pth, R1*100, R2*100, mc_m3h, d.Tdc_out, d.Twct_out);
    %     result_path = "resultados/optimization_V1/" + result_id + ".json";
    %     export_results(detailed, 'optimization_V1', true, result_path, true);
    % end

end