function [Twct_out, Pe, M_lost_wct] = wct_model_physical_andasol(Tamb, HR, Twct_in, Mwct, SC_fan_wct, varargin)

    % Model originally created by Pedro Navarro, adapted and scaled by Lidia Roca Sobrino
    % Modified by Juan Miguel Serrano:
    % Key Improvements Implemented:
    % True Asynchronous Timeout: Replaced the timer/global flag approach with parfeval for genuine solver interruption
    % Robust Multi-Initial Point Solver: Uses multiple initial points (-12 to -3 in steps of 2) to find the best solution
    % How the New System Works:
    % - Main Solver Loop: For each initial point, uses parfeval to run the solver asynchronously
    % - True Timeout Control: Monitors the solver state and can truly cancel it if it exceeds the time limit (2 seconds per attempt)
    % - Best Solution Selection: Keeps track of the best solution found across all initial points
    % - Fallback Strategy: If the main loop fails, tries a single fallback attempt with relaxed tolerances (1 second timeout)
    % - Final Fallback: If everything fails, uses a physics-based approximation based on approach temperature to wet bulb
    % Pe (kWe)
    % M_lost_wct (l/h)

    iP = inputParser;        
    addParameter(iP, 'c_poppe', 1.52); %1.4889)
    addParameter(iP, 'n_poppe', -0.69); %-0.71)
    addParameter(iP, 'Ta_out', 40)
    addParameter(iP, 'HR2', 100)
    
    % Output from scaling script wct_scaling.m
    addParameter(iP, 'Mwct_min', 320*3600/1000)
    addParameter(iP, 'Mwct_max', 1100*3600/1000)
    addParameter(iP, 'params_pc2mair', [-0.01032,2.43,501.1])

    
    parse(iP,varargin{:})
    c_poppe = iP.Results.c_poppe;
    n_poppe = iP.Results.n_poppe;
    Ta_out = iP.Results.Ta_out;
    HR2 = iP.Results.HR2;
    Mwct_min = iP.Results.Mwct_min;
    Mwct_max = iP.Results.Mwct_max;
    params_pc2mair = iP.Results.params_pc2mair;
    
    max_values = [50, 100, 50, Mwct_max, 100];
    min_values = [ 0.1,   0.1, 10,  Mwct_min,  20];
    vars = ["Tamb", "HR", "Twct_in", "Mwct", "SC_fan_wct"];
    
    valid_inputs = true;
    vals = [Tamb, HR, Twct_in, Mwct, SC_fan_wct];
    for idx=1:length(vars)
        if vals(idx) > ceil(max_values(idx)) || vals(idx) < floor(min_values(idx))
            % if options.raise_error_on_invalid_inputs
            %     raise_error(vars(idx), vals(idx), min_values(idx), max_values(idx))
            % else
                % if ~options.silence_warnings
                    warning("%s outside limits (%.2f <! %.2f <! %.2f)", vars(idx), min_values(idx), vals(idx), max_values(idx))
                % end
                valid_inputs = false;
        end
            % end
    end

    if ~valid_inputs
        Twct_out = Twct_in;
        Pe = 0;
        M_lost_wct = 0;
        
        return
    end

    m_drift= 0;%0.1; % caudal perdido por separador a pesar de contraflujo, dato fabricante (%)
    
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    ma = ajuste_m_dot_a_andasol(SC_fan_wct);
   % ma = ajuste_m_dot_aT(SC_fan_wct,Tamb);   
% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    [Tdb, w, phi, h, Tdp, v, Twb] = Psychrometricsnew('Tdb',Tamb,'phi',HR); % Salidas: [Tdb, humratio, phi, entalphy, Tdp, volume, Twb]
    Tww =Twct_in;
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
    mw = Mwct * Dens_agua /3600;

    % Obtener correlación de Merkel a partir de ajuste y ratio de flujos
    Me_corr = c_poppe*(mw/ma)^(n_poppe);

    % Calcular temperatura de salida y consumo de agua - Robust solver with multiple initial points
    options = optimset('Display', 'off', 'TolFun', 1e-6, 'TolX', 1e-6, ...
                      'MaxIter', 50, 'MaxFunEvals', 200);%, ...
                      % 'Algorithm', 'trust-region-dogleg');
    
    % Create alias for Me_Poppe_cc function with fixed parameters
    Me_Poppe_func = @(Twct_out) Me_Poppe_cc(Twct_in+273.15, Twct_out+273.15, Tamb+273.15, Twb+273.15, ma, mw, 101325);
    
    fun=@(Twct_out) (Me_Poppe_func(Twct_out) - Me_corr);
    
    % % BRUTE FORCE PARALLEL APPROACH
    % % Define parameters for brute force search
    % N = 150; % Number of temperature values to test
    % max_eval_time = 2.; % Maximum time per evaluation in seconds (2s)
    % 
    % % Create array of possible outlet temperatures (delta from inlet)
    % delta_T_min = -20; % Minimum cooling (°C) - outlet can be 20°C below inlet
    % delta_T_max = -0.5;  % Maximum cooling (°C) - outlet should be at least 1°C below inlet
    % delta_T_array = linspace(delta_T_min, delta_T_max, N);
    % Twct_out_candidates = Twct_in + delta_T_array;
    % 
    % % Filter candidates to physically reasonable bounds
    % valid_indices = Twct_out_candidates > (Twb) & Twct_out_candidates < Twct_in;
    % Twct_out_candidates = Twct_out_candidates(valid_indices);
    % 
    % if isempty(Twct_out_candidates)
    %     warning('No valid temperature candidates found. Using fallback.');
    %     Twct_out = Twct_in - 5; % Simple fallback
    % else
    %     % Evaluate all candidates in parallel using parfeval
    %     num_candidates = length(Twct_out_candidates);
    %     futures = cell(num_candidates, 1);
    % 
    %     % Submit all evaluations
    %     for i = 1:num_candidates
    %         futures{i} = parfeval(@() evaluate_single_temperature(Me_Poppe_func, Me_corr, Twct_out_candidates(i)), 2);
    %     end
    % 
    %     % Collect results with timeout
    %     errors = inf(num_candidates, 1);
    %     valid_evals = false(num_candidates, 1);
    % 
    %     for i = 1:num_candidates
    %         try
    %             % Wait for result with timeout
    %             t0 = tic;
    %             while ~strcmp(futures{i}.State, 'finished')
    %                 pause(0.001); % Small pause
    % 
    %                 if toc(t0) > max_eval_time
    %                     cancel(futures{i});
    %                     break;
    %                 end
    %             end
    % 
    %             % Get result if completed
    %             if strcmp(futures{i}.State, 'finished')
    %                 [error_val, success] = fetchOutputs(futures{i});
    %                 if success && ~isnan(error_val) && ~isinf(error_val)
    %                     errors(i) = abs(error_val);
    %                     valid_evals(i) = true;
    %                 end
    %             end
    % 
    %         catch
    %             % Evaluation failed, keep default inf error
    %             continue;
    %         end
    %     end
    % 
    %     figure
    %     plot(Twct_out_candidates', errors)
    % 
    %     % Find best solution
    %     if any(valid_evals)
    %         [~, best_idx] = min(errors);
    %         Twct_out = Twct_out_candidates(best_idx);
    %         fprintf('Brute force found solution: Twct_out = %.2f°C with error = %.2e\n', Twct_out, errors(best_idx));
    %     else
    %         warning('All brute force evaluations failed. Using physics-based approximation.');
    %         % Physics-based approximation
    %         approach_temp = max(2, 0.1 * (Twct_in - Twb));
    %         Twct_out = max(Twb + approach_temp, Twct_in - 10);
    %     end
    % end
    
    % Try multiple initial points for robustness using parfeval for timeout control
    initial_offsets = -3:-2:-20; % Coarser grid for faster convergence (from -12 to -3 in steps of 2)
    best_solution = [];
    best_residual = inf;
    best_exitflag = -1;
    max_solve_time = 1; % Maximum time per solve attempt in seconds

    for offset = initial_offsets
        x0 = Twct_in + offset;

        % Skip clearly unreasonable initial points
        if x0 <= (Twb)
           continue;
        end

        try
            % Use parfeval for true timeout control
            future = parfeval(@() solve_wct_with_initial_point(fun, x0, options), 3);

            % Wait for completion with timeout
            t0 = tic;
            while ~strcmp(future.State, 'finished')
                pause(0.01); % Small pause to prevent busy waiting

                if toc(t0) > max_solve_time
                    cancel(future);
                    warning('Solver timed out for initial point %.1f', x0);
                    break;
                end
            end

            % Get results if completed successfully
            if strcmp(future.State, 'finished')
                [x_temp, fval, exitflag] = fetchOutputs(future);

                % Check if solution is valid and better than previous attempts
                if exitflag > 0 && abs(fval) < abs(best_residual) && ~isnan(x_temp) && ~isinf(x_temp)
                    % Additional physical constraints: outlet should be lower than inlet
                    if x_temp < Twct_in && x_temp > (Tamb - 5) % reasonable bounds
                        best_solution = x_temp;
                        best_residual = fval;
                        best_exitflag = exitflag;

                        % Early termination if residual is very small
                        if abs(fval) < 1e-6
                            break;
                        end
                    end
                end
            end

        catch ME
            % Log the error but continue to next initial point
            if contains(ME.message, 'Maximum') || contains(ME.message, 'timeout')
                warning('Solver hit limits for initial point %.1f: %s', x0, ME.message);
            end
            continue;
        end
    end

    % Use best solution or fallback to simple approach if all failed
    if ~isempty(best_solution) && best_exitflag > 0
        Twct_out = best_solution;
    else
        % Fallback: try original approach with tighter constraints and timeout
        fallback_options = optimset('Display', 'off', 'TolFun', 1e-4, 'TolX', 1e-4, ...
                                   'MaxIter', 25, 'MaxFunEvals', 100);
        x0 = Twct_in - 10;
        try
            % Use parfeval for fallback with shorter timeout (1 second)
            fallback_future = parfeval(@() solve_wct_with_initial_point(fun, x0, fallback_options), 3);

            % Wait for completion with timeout
            t0 = tic;
            while ~strcmp(fallback_future.State, 'finished')
                pause(0.01);

                if toc(t0) > 1 % 1 second timeout
                    cancel(fallback_future);
                    error('Fallback solver timed out');
                end
            end

            % Get results if completed successfully
            if strcmp(fallback_future.State, 'finished')
                [Twct_out, fval, exitflag] = fetchOutputs(fallback_future);

                % Check if fallback solution is reasonable
                if isnan(Twct_out) || isinf(Twct_out) || Twct_out >= Twct_in || exitflag <= 0
                    error('Fallback solver failed validation');
                end
            else
                error('Fallback solver did not complete');
            end

        catch
            % If everything fails, use a physics-based approximation
            warning('WCT solver failed to converge.');
            Twct_out = nan;
            Pe = nan;
            M_lost_wct = nan;

            return
            % Approximate based on approach temperature to wet bulb
            % approach_temp = max(2, 0.1 * (Twct_in - Twb)); % Reasonable approach temperature
            % Twct_out = max(Twb + approach_temp, Twct_in - 10); % Conservative estimate
        end
    end

    [~, M_lost_wct] = Me_Poppe_func(Twct_out);
    M_lost_wct = m_drift/100 * mw + M_lost_wct;

    % Converir M_lost_wct de kg/s a L/h
    Tww =Twct_out;
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
    M_lost_wct = M_lost_wct / Dens_agua  * 1000*3600;

    % Consumo eléctrico
    Pe = ConsumoElectrico_E01_andasol(SC_fan_wct); %,Tamb,HR); % + ConsumoElectrico_P7(SC_pump_wct); % kWe
    % Pth = Mwct/3.6*(Twct_in - Twct_out)*4.186; % Mwct: m³/h -> kg/s; kWth
  


%     function v_aire = ajuste_v_aire(SC_fan_wct)
%         % SC_fan_wct -> v_aire (kg/s)
%         %      f(x) = p1*x^2 + p2*x + p3
%         % Coefficients (with 95% confidence bounds):
%         p1 = -0.00027051;
%         p2 = 0.06744305;
%         p3 = 0.40447051;
%         v_aire = p1*(SC_fan_wct)^2 + p2*SC_fan_wct - p3;
%     end

%     function m_dot_a = ajuste_m_dot_a(SC_fan_wct)
%         p1 = -0.0014;
%         p2 = 0.1743;
%         p3 = -0.7251;
%         m_dot_a = p1*(SC_fan_wct/2)^2 + p2*SC_fan_wct/2 + p3;
%     end

% %% variador de frecuencia (%) - caudal de aire (m3/h) WCT planta andasol
%     function m_dot_a = ajuste_m_dot_a_andasol(SC_fan_wct)
%        p1 =     -0.1461;
%        p2 =       36.37;
%        p3 =       130.7;
%        m_dot_a = p1*SC_fan_wct^2 + p2*SC_fan_wct + p3;
%     end

%% variador de frecuencia (%) - flujo másico de aire (kg/s) WCT planta andasol
    function m_dot_a = ajuste_m_dot_a_andasol(SC_fan_wct)
       % p1 =     params_pc2mair(1); %-0.01032;
       % p2 =     params_pc2mair(2); %  2.43;
       % p3 =     params_pc2mair(3); % 501.1;
       p1 = -0.3434;
       p2 = 68.65;
       p3 = -1210;
       m_dot_a = p1*SC_fan_wct^2 + p2*SC_fan_wct + p3;
    end

%     function m_dot_a = ajuste_m_dot_aT(SC_fan_wct,Tamb)
%         p00 =   -0.0433;
%         p10 =   0.1650;
%         p01 =   -0.0273;   
%         p20 =   -0.0013;  
%         p11 =   0.0000;    
%         p02 =   0.0003;    
%         m_dot_a = p00 + p10*(SC_fan_wct/2) + p01*Tamb + p20*(SC_fan_wct/2)^2 + p11*(SC_fan_wct/2)*Tamb + p02*Tamb^2;
%     end

%     function [CE] = ConsumoElectrico_E01_andasol(x,T,HR)
%         % Nota: estoy tomando la T del ambiente, no del aire a la salida
%         % para calcular la densidad del aire.
%         ef=0.7;
%         [Tdb_2, w_2, phi_2, h_2, Tdp_2, v_2, Twb_2] = Psychrometricsnew('Tdb',T,'phi',HR); % Salidas: [Tdb, humratio, phi, entalphy, Tdp, volume, Twb]
%         rho_air=1/v_2;
%         Qair= (ajuste_m_dot_a_andasol(x))/rho_air; % m3/s
%         CE=(dp_wct(x)* Qair/1000)/ef; %kW        
%     end

    function Ce = ConsumoElectrico_E01_andasol(SC) % solo 1 WCT
        % SC (%)
        % Ce (kW)
        % f(x) = p1*x^3 + p2*x^2 + p3*x + p4
           p1 =    5.35e-05 ;
           p2 =    0.01149;
           p3 =    -0.0141;
           p4 =    0.1433;
        Ce =max(p1.*SC.^3 + p2.*SC.^2 + p3.*SC + p4, 0); %kW
    end



    function [dp_est] = dp_wct(fan)
        p1 =     0.06322  ;
        p2 =      -1.503  ;
        p3 =       100.9  ;
        dp_est = p1*fan^2 + p2*fan + p3; %Pa
    end

    function [CE] = ConsumoElectrico_P7(x)
    % x -> SC E01 (%)
    % f(x) = p1*x^3 + p2*x^2 + p3*x + p4
           p1 =    0.005245  ;
           p2 =    -0.08947  ;
           p3 =       4.514  ;
           p4 =       45.41 ;
    CE=(p1.*x.^3 + p2.*x.^2 + p3.*x + p4)/1000; %kW
    
    end

    function raise_error(variable, lower_limit, upper_limit)
        msg = sprintf("Input %s is outside limits (%.2f > %s > %.2f)", string(variable), lower_limit, string(variable), upper_limit);
        throw(MException('MED_model:invalid_input', msg))
    end
    
end

% Helper functions for timeout mechanism
function set_timeout_flag()
    global solver_timeout_flag;
    solver_timeout_flag = true;
end

function result = check_timeout_and_eval(func, Twct_out, Me_corr)
    global solver_timeout_flag;
    if solver_timeout_flag
        error('Solver timeout interrupted');
    end
    result = func(Twct_out) - Me_corr;
end

function [Tda_ss] = T_da_ss(h,w,pT)
    %La función T_da_ss devuelve la temperatura del aire (K) que, en
    %condiciones de sobresaturación, verifica los valores de entalpía y humedad
    %específica introducidos como inputs. 

    opts = optimset('Display', 'off','MaxIter', 10);
    
    %% Ejemplo de cálculo Kloppers
    
    % h=50.01967;
    % w=0.0133338;
    % pT=101712.27;
    % [Tda_ss] = T_da_ss(50,0.0133,101712.27)
    % El resultado (página 8 apéndice G) Tda_ss=290.8448 K.
    
    %% Constantes para el cálculo de las propiedades termofíscas del aire y vapor de agua Kröger (Anexo A AIR-COOLED HEAT EXCHANGERS AND COOLING TOWERS)
    
    To= 273.15;
    C1=1.045356*10^3;
    C2=3.161783*10^(-1);
    C3=7.083814*10^(-4);
    C4=2.705209*10^(-7);
    C5=1.3605*10^3;
    C6=2.31334;
    C7=2.46784*10^(-10);
    C8=5.91332*10^(-13);
    C9=3.4831814*10^6;
    C10=5.8627703*10^3;
    C11=12.139568;
    C12=1.40290431*10^(-2);
    C13=8.15599*10^3;
    C14=2.80627*10^1;
    C15=5.11283*10^(-2);
    C16=2.17582*10^(-13);
    C17=2501.6;
    C18=2.3263;
    C19=1.8577;
    C20=4.184;
    C21=0.62509;
    C22=1.005;
    C23=1.00416;
    C24=10.79586;
    C25=5.02808;
    C26=1.50474*10^(-4);
    C27=4.2873*10^(-4);
    C28=2.786118312;
    C29=0.865;
    C30=0.667;
    C31=0.622;
    
    h_fg=C9-C10*To+C11*(To^2)-C12*(To^3); % Entalpía de vaporización (evaluada en 273.15 K)
    
    f=@(x)((((C1-C2*((x(1)+273.15)/2)+C3*(((x(1)+273.15)/2))^2-C4*(((x(1)+273.15)/2))^3)*(x(1)-273.15)+((0.62198*(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) )/(pT-(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) ))*(h_fg+(C13-C14*((x(1)+273.15)/2)+C15*(((x(1)+273.15)/2))^2-C16*(((x(1)+273.15)/2))^6)*(x(1)-273.15))+(w-((0.62198*(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) )/(pT-(10^(C24*(1-(To/x(1)))+C25*(log10(To/x(1)))+C26*(1-10^((-8.29692)*((x(1)/To)-1)))+C27*(10^((4.76955)*(1-(To/x(1))))-1)+C28)) )))*(C13-C14*((x(1)+273.15)/2)+C15*(((x(1)+273.15)/2))^2-C16*(((x(1)+273.15)/2))^6)*(x(1)-273.15))/1000)-h);
    x0=[273.15]; 
    x=fsolve(f,x0,opts);
    
    Tda_ss=x;
    
end
    
function [w_a] = w_a(Tda,HR,pT)
    %La función w devuelve la humedad del aire en (kg/kg) a partir de la temperatura seca del aire (K), la humedad relativa (%) y la presión total del aire (Pa)
    
    % Tda=9.7+273.15;
    % HR=82.54;
    % pT=101712.27;
    
    %% Constantes para el cálculo de las propiedades termofíscas del aire y vapor de agua Kröger (Anexo A AIR-COOLED HEAT EXCHANGERS AND COOLING TOWERS)
    
    To= 273.15;
    C1=1.045356*10^3;
    C2=3.161783*10^(-1);
    C3=7.083814*10^(-4);
    C4=2.705209*10^(-7);
    C5=1.3605*10^3;
    C6=2.31334;
    C7=2.46784*10^(-10);
    C8=5.91332*10^(-13);
    C9=3.4831814*10^6;
    C10=5.8627703*10^3;
    C11=12.139568;
    C12=1.40290431*10^(-2);
    C13=8.15599*10^3;
    C14=2.80627*10^1;
    C15=5.11283*10^(-2);
    C16=2.17582*10^(-13);
    C17=2501.6;
    C18=2.3263;
    C19=1.8577;
    C20=4.184;
    C21=0.62509;
    C22=1.005;
    C23=1.00416;
    C24=10.79586;
    C25=5.02808;
    C26=1.50474*10^(-4);
    C27=4.2873*10^(-4);
    C28=2.786118312;
    C29=0.865;
    C30=0.667;
    C31=0.622;
    
    %% Cálculo humedad
    
    pvs=10^(C24*(1-(To/Tda))+C25*(log10(To/Tda))+C26*(1-10^((-8.29692)*((Tda/To)-1)))+C27*(10^((4.76955)*(1-(To/Tda)))-1)+C28);   % pvs
    w_a = (0.62198 * pvs * (HR / 100)) / (pT - pvs * (HR / 100)); %w

end

function [Me_Poppe, M_lost_wct] = Me_Poppe_cc(Tw1,Tw2,Tas1,Tbh,ma,mw,pT)
    %% Experimento 1 Ghazani
    
    % Tw1=52+273.15;
    % Tw2=40+273.15;
    % Tas1=30+273.15;
    % Tbh=25+273.15;
    % ma =265/3600;
    % mw=235/3600;
    % pT=101712.27;
    % 
    % T_0=25+273.15;
    % phi_0=50;
    % p_0=pT;
    % N=10;
    % [R,Res,Me_Poppe_cc] =  Me_Poppe_cc(52+273.15,40+273.15,30+273.15,25+273.15,265/3600,235/3600,101325,10)
    %% Ejemplo aleatorio para torre de refrigeracion 
    
    %Tw1=312.82; %(TEMPERATURA DE ENTRADA DEL AGUA)
    %Tw2=300.92; %(TEMPERATURA DE SALIDA DEL AGUA)
    %Tas1=282.85;%(TEMPERATURA DE ENTRADA DEL AIRE)
    %Tbh=281.38; %(TEMPERATURA DE BULBO HUMEDO DE ENTRADA DE AIRE)
    %HR1=82.54; %(HUMEDAD RELATIVA)
    %ma =4.1340; %(FLUJO MASICO DE AIRE SECO)
    %mw=3.999; %(FLUJO MASICO DE AGUA)
    %pT=101712.27; %(PRESION ATMOSFERICA)
    
    %% Constantes para el cálculo de las propiedades termofíscas del aire y vapor de agua Kröger (Anexo A AIR-COOLED HEAT EXCHANGERS AND COOLING TOWERS)
    N=5;
    To= 273.15;
    C1=1.045356*10^3;
    C2=3.161783*10^(-1);
    C3=7.083814*10^(-4);
    C4=2.705209*10^(-7);
    C5=1.3605*10^3;
    C6=2.31334;
    C7=2.46784*10^(-10);
    C8=5.91332*10^(-13);
    C9=3.4831814*10^6;
    C10=5.8627703*10^3;
    C11=12.139568;
    C12=1.40290431*10^(-2);
    C13=8.15599*10^3;
    C14=2.80627*10^1;
    C15=5.11283*10^(-2);
    C16=2.17582*10^(-13);
    C17=2501.6;
    C18=2.3263;
    C19=1.8577;
    C20=4.184;
    C21=0.62509;
    C22=1.005;
    C23=1.00416;
    C24=10.79586;
    C25=5.02808;
    C26=1.50474*10^(-4);
    C27=4.2873*10^(-4);
    C28=2.786118312;
    C29=0.865;
    C30=0.667;
    C31=0.622;
    
    hfg=C9-C10*To+C11*(To^2)-C12*(To^3); % Calor latente del agua a  la temperatura T=To 
    
    % Con la función Psychrometricsnew calculo las propiedades en la entrada
    [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('Tdb',Tas1-273.15,'Twb',Tbh-273.15);
    
    %SIENDO tdb TEMPERATURA DE BULBO SECO, humratio HUMEDAD ESPECIFICA, phi
    %HUMEDAD RELATIVA, entalphy ENTALPIA, tdp (), volume VOLUMEN, twb
    %TEMPERATURA DE BULBO HUMEDO.
    
    %% Inicio Runge-Kutta 4º orden 
    % Número de intervalos y DeltaTw
    
    DeltaTw=(Tw1-Tw2)/N;
    
    % Prevemos las dimensiones de las matrices de resultados y de cálculo y
    % definimos el primer nivel de la matriz de resultados
    R_cc=zeros(19,4*N);
    Res_cc=zeros(7,N+1);
    
    
    % Creamos la primera columna matriz resultados Res(:,1).
    % Res(:,1)=[humratio;entalphy/1000;Tw2;0;Tas1;phi;Tbh;0;0;0;0;0;0;0];
    Res_cc(1,1)=humratio; %HUMEDAD ESPECIFICA
    Res_cc(2,1)=entalphy/1000; %ENTALPIA
    Res_cc(3,1)=Tw2; %TEMPERATURA DE SALIDA DEL AGUA
    Res_cc(4,1)=0; % Me al inicio es nulo
    Res_cc(5,1)=Tas1; %TEMPERATURA DE ENTRADA DEL AIRE
    Res_cc(6,1)=phi;%HUMEDAD RELATIVA
    Res_cc(7,1)=Tbh;%TEMPERATURA DE BULBO HUMEDO EN LA ENTRADA DE AIRE.
    
    %% El cálculo de Me depende de la humedad absoluta a la salida. Al ser desconocida realizamos la programación en torno a ella. 
    % Para ello, calculamos un vector de humedades que debe converger en el
    % valor de humedad a la salida. El primer valor será el correspondiente a
    % la entrada y el segundo lo aumentamos un 5% para que entre en el bucle
    % del while
    
    % Humedad específica en la sección de entrada (ya calculada)
    w(1)=Res_cc(1,1);
    wo=w(1,1);  %LA HUMEDAD QUE TENGO A LA SALIDA DIGO QUE VA A SER IGUAL QUE LA QUE TENGO EN LA ENTRADA
    
    f=2;  
    w(f)=1.05*wo;
    
    while abs(w(f)-w(f-1))*100/w(f)>0.1 %ESTE BUCLE VA HACIENDO LAS ITERACIONES HASTA QUE EL ERROR SEA MENOR DE 0.1 
     f=f+1;
     
    for i=1:N;
        if Res_cc(6,i)<100; % Evaluamos HR. Si HR<100 al final del intervalo calculamos normal. De lo contrario consideramos sobresaturación
            %Todo lo que va aqui dentro es el cálculo sin saturación
            for k=1:4; % Cálculo de subetapas en cada intervalo
                j=4*(i-1)+k; 
                 if j==1 % Sirve para identificar que la primera etapa es la entrada del aire y salida del agua
                    R_cc(1,j)=Res_cc(1,i); %GUARDO LA HUMEDAD ESPECIFICA
                    R_cc(2,j)=Res_cc(2,i)*1000; %GUARDO LA ENTALPIA
                    R_cc(3,j)=Res_cc(3,i); %TEMPERATURA DE SALIDA DEL AGUA
                 else % Si no es la primera etapa 
                    if k==1
                    R_cc(1,j)=Res_cc(1,i); % Humedad en el step anterior
                    R_cc(2,j)=Res_cc(2,i)*1000; %h
                    R_cc(3,j)=Res_cc(3,i);
                    R_cc(17,j)=Res_cc(4,i); %Me
                    elseif k==2
                    R_cc(1,j)=R_cc(1,j-1)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-1)+R_cc(15,j-1)/2; 
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;
                    elseif k==3
                    R_cc(1,j)=R_cc(1,j-2)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-2)+R_cc(15,j-1)/2;
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;                
                    else
                    R_cc(1,j)=R_cc(1,j-3)+R_cc(14,j-1);
                    R_cc(2,j)=R_cc(2,j-3)+R_cc(15,j-1);
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw;
                    end
                 end
            R_cc(4,j)=(R_cc(3,j)+273.15)/2;   %Tªcps (TEMPERATURA A LA QUE TIENEN QUE SER EVALUADOS LOS CALORES ESPECIFICOS)
            R_cc(5,j)=C1-C2*R_cc(4,j)+C3*(R_cc(4,j))^2-C4*(R_cc(4,j))^3;   %Cpa (CALOR ESPECIFICO DEL AIRE SECO)
            R_cc(6,j)=C5+C6*R_cc(4,j)-C7*(R_cc(4,j))^5+C8*(R_cc(4,j))^6;   %Cpv (CALOR ESPECIFICO DEL VAPOR DE AGUA)
            R_cc(7,j)=C13-C14*R_cc(4,j)+C15*(R_cc(4,j))^2-C16*(R_cc(4,j))^6;   %Cpw (CALOR ESPECIFICO DEL AGUA)
            R_cc(8,j)=10^(C24*(1-(To/R_cc(3,j)))+C25*(log10(To/R_cc(3,j)))+C26*(1-10^((-8.29692)*((R_cc(3,j)/To)-1)))+C27*(10^((4.76955)*(1-(To/R_cc(3,j))))-1)+C28);   % pvs (PRESION DE VAPOR DE AGUA EVALUADA EN TO)
            R_cc(9,j)=(C21*R_cc(8,j))/(pT-(C22*R_cc(8,j))); %wsw (RELACION DE HUMEDAD PARA AIRE SATURADO)
            R_cc(10,j)=hfg+(R_cc(6,j)*(R_cc(3,j)-To));   %hv (ENTALPIA DEL VAPOR DE AGUA A LA TEMPERATURA LOCAL, EN RELACION CON EL AGUA A 0ºC)
            R_cc(11,j)=(R_cc(5,j)*(R_cc(3,j)-To))+R_cc(9,j)*R_cc(10,j); %hmasw (ENTALPIA DE AIRE SATURADO A LA TEMPERATURA DEL AGUA)
            R_cc(12,j)=(C29^C30)*((((C31+R_cc(9,j))/(C31+R_cc(1,j)))-1)/(log(((C31+R_cc(9,j))/(C31+R_cc(1,j))))));   %Le (NUMERO DE LEWIS)
            R_cc(13,j)=(mw/ma)*(1-((ma/mw)*(wo-R_cc(1,j))));  %Balance de masa (BALANCE DE MASA)
            R_cc(14,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j)*(R_cc(9,j)-R_cc(1,j)))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(1,j))*R_cc(10,j))-((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))); %j (CALCULO DE LA J)
            R_cc(15,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j))*(1+(((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(1,j))*R_cc(10,j))-((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))))); %k (CALCULO DE LA K)
            R_cc(16,j)=(DeltaTw*R_cc(7,j))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(1,j))*R_cc(10,j))-((R_cc(9,j)-R_cc(1,j))*R_cc(7,j)*(R_cc(3,j)-To))); %l (CALCULO DE LA L)
            [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('h',R_cc(2,j),'w',R_cc(1,j)); %PARA ESA ENTALPIA Y HUMEDAD ESPECIFICA DE ESE SUBNIVEL OBTENGO LOS VALORES PSICROMETRICOS
            R_cc(18,j)=Tdb+273.15; % Tas puede que difiera del valor real si dentro del intervalo se produce sobresaturación. Si se activan los siguientes comandos se puede evaluar
            end
             
     % Al final del ciclo de k completamos la matriz de resultados. Dejamos en
     % blanco la temperatura del aire, la humedad y el bulbo húmedo al no saber si estamos en condiciones de
     % sobresaturación. Completamos i+1 ya que estamos en k=4 del nivel
     % anterior 
    % Res(:,i+1)=[Res(1,i)+(R(14,j-3)+2*R(14,j-2)+2*R(14,j-1)+R(14,j))/6;(1000*Res(2,i)+(R(15,j-3)+2*R(15,j-2)+2*R(15,j-1)+R(15,j))/6)/1000;Res(3,i)+DeltaTw;Res(4,i)+(R(16,j-3)+2*R(16,j-2)+2*R(16,j-1)+R(16,j))/6;0;0;0;0;0;0;0;0;0;0];     
    Res_cc(1,i+1)=Res_cc(1,i)+(R_cc(14,j-3)+2*R_cc(14,j-2)+2*R_cc(14,j-1)+R_cc(14,j))/6; %RELACION DE HUMEDAD EN EL NIVEL CORRESPONDIENTE
    Res_cc(2,i+1)=(1000*Res_cc(2,i)+(R_cc(15,j-3)+2*R_cc(15,j-2)+2*R_cc(15,j-1)+R_cc(15,j))/6)/1000; %ENTALPIA DEL AIRE EN EL NIVEL CORRESPONDIENTE
    Res_cc(3,i+1)=Res_cc(3,i)+DeltaTw;
    Res_cc(4,i+1)=Res_cc(4,i)+(R_cc(16,j-3)+2*R_cc(16,j-2)+2*R_cc(16,j-1)+R_cc(16,j))/6; %NUMERO DE MERKEL EN EL NIVEL CORRESPONDIENTE
     % Con la función Psychrometricsnew calculo las propiedades a partir h y w
    % de la matriz Res
     [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('h',1000*Res_cc(2,i+1),'w',Res_cc(1,i+1));
     
     % Asumimos aire no saturado, E INTRODUCIMOS LOS VALORES QUE NOS INTERESAN
     % DEL DIAGRAMA PICROMETRICO
     Res_cc(5,i+1)=Tdb+273.15; %TEMPERATURA DE BULBO SECO
     Res_cc(6,i+1)=phi;%HUMEDAD RELATIVA
     Res_cc(7,i+1)=Twb+273.15; %TEMPERATURA DE BULBO HUMEDO
     
      
        if Res_cc(6,i+1)<100; %SI LA HUMEDAD RELATIVA ES MENOR DE 100
            % Confirmamos si no está saturado
            Res_cc(5,i+1)=Tdb+273.15;
            Res_cc(6,i+1)=phi;
            Res_cc(7,i+1)=Twb+273.15;
         else
         % Corregimos si está sobresaturado
            Res_cc(5,i+1)=T_da_ss(Res_cc(2,i+1),Res_cc(1,i+1),pT); 
            % La función T_da_ss devuelve la temperatura del aire (K) que, en
            %condiciones de sobresaturación, verifica los valores de entalpía y humedad
            %específica introducidos como inputs.
            Res_cc(6,i+1)=100; %EN ESTE CASO AL ESTAR SOBRESATURADO LA HUMEDAD RELATIVA ES 100
            Res_cc(7,i+1)=Res_cc(5,i+1);      
        end
            
                         
        else %ESTE VA CON EL IF QUE ESTA JUSTO ANTES DEL FOR DE ARRIBA DE MANERA QUE
            %COMO EN ESE NOS SALE QUE EL AIRE YA ESTA SATURADO DA EL SALTO A
            %ESTAS ECUACIONES Y NO HACE EL CALCULO DE NO SATURADO Y DESPUES
            %CORREGIR.
            %Todo lo que va aqui dentro es el cálculo con sobre saturación
             for k=1:4; % Cálculo de subetapas en cada intervalo
                j=4*(i-1)+k; 
                    if k==1
                    R_cc(1,j)=Res_cc(1,i); % Humedad en el step anterior
                    R_cc(2,j)=Res_cc(2,i)*1000; %h
                    R_cc(3,j)=Res_cc(3,i);
                    R_cc(17,j)=Res_cc(4,i); %Me
                    elseif k==2
                    R_cc(1,j)=R_cc(1,j-1)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-1)+R_cc(15,j-1)/2; 
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;
                    elseif k==3
                    R_cc(1,j)=R_cc(1,j-2)+R_cc(14,j-1)/2;
                    R_cc(2,j)=R_cc(2,j-2)+R_cc(15,j-1)/2;
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw/2;                
                    else
                    R_cc(1,j)=R_cc(1,j-3)+R_cc(14,j-1);
                    R_cc(2,j)=R_cc(2,j-3)+R_cc(15,j-1);
                    R_cc(3,j)=Res_cc(3,i)+DeltaTw;
                    end
     % Para condiciones de sobresaturación se requiere la humedad específica
     % del aire  en condiciones de saturación a Tas. Se añade 1 fila con wsa
     % R(20,j). El cálculo de j, k y l cambia en condiciones de saturación
     % frente a aire no saturado.
     
            R_cc(4,j)=(R_cc(3,j)+273.15)/2;   %Tªcps
            R_cc(5,j)=C1-C2*R_cc(4,j)+C3*(R_cc(4,j))^2-C4*(R_cc(4,j))^3;   %Cpa
            R_cc(6,j)=C5+C6*R_cc(4,j)-C7*(R_cc(4,j))^5+C8*(R_cc(4,j))^6;   %Cpv
            R_cc(7,j)=C13-C14*R_cc(4,j)+C15*(R_cc(4,j))^2-C16*(R_cc(4,j))^6;   %Cpw
            R_cc(8,j)=10^(C24*(1-(To/R_cc(3,j)))+C25*(log10(To/R_cc(3,j)))+C26*(1-10^((-8.29692)*((R_cc(3,j)/To)-1)))+C27*(10^((4.76955)*(1-(To/R_cc(3,j))))-1)+C28);   % pvs
            R_cc(9,j)=(C21*R_cc(8,j))/(pT-(C22*R_cc(8,j))); %wsw
            R_cc(10,j)=hfg+(R_cc(6,j)*(R_cc(3,j)-To));   %hv
            R_cc(11,j)=(R_cc(5,j)*(R_cc(3,j)-To))+R_cc(9,j)*R_cc(10,j); %hmasw
            R_cc(18,j)=T_da_ss(R_cc(2,j)/1000,R_cc(1,j),pT); % Tas
    %         [Tdb, humratio, phi, entalphy, Tdp, volume, Twb] =Psychrometricsnew('Tdb',R(18,j),'phi',100);
            R_cc(19,j)=w_a(R_cc(18,j),100,pT); % wsa
    %         R(19,j)=humratio; % wsa
            R_cc(12,j)=(C29^C30)*((((C31+R_cc(9,j))/(C31+R_cc(19,j)))-1)/(log(((C31+R_cc(9,j))/(C31+R_cc(19,j))))));   %Le
            R_cc(13,j)=(mw/ma)*(1-((ma/mw)*(wo-R_cc(1,j))));  %Balance de masa
            R_cc(14,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j)*(R_cc(9,j)-R_cc(19,j)))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(19,j))*R_cc(10,j)+(R_cc(1,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))+((R_cc(1,j)-R_cc(9,j))*R_cc(7,j)*(R_cc(3,j)-To))); %j
            R_cc(15,j)=(DeltaTw*R_cc(7,j)*R_cc(13,j))*(1+(((R_cc(9,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(19,j))*R_cc(10,j)+(R_cc(1,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))+((R_cc(1,j)-R_cc(9,j))*R_cc(7,j)*(R_cc(3,j)-To))))); %k
            R_cc(16,j)=(DeltaTw*R_cc(7,j))/(R_cc(11,j)-R_cc(2,j)+(R_cc(12,j)-1)*(R_cc(11,j)-R_cc(2,j)-(R_cc(9,j)-R_cc(19,j))*R_cc(10,j)+(R_cc(1,j)-R_cc(19,j))*R_cc(7,j)*(R_cc(3,j)-To))+((R_cc(1,j)-R_cc(9,j))*R_cc(7,j)*(R_cc(3,j)-To))); %l
             end
             
    % Las 4 primeras filas son w, h, Tw y Me, calculadas con RK.          
    % Res(:,i+1)=[Res(1,i)+(R(14,j-3)+2*R(14,j-2)+2*R(14,j-1)+R(14,j))/6;(1000*Res(2,i)+(R(15,j-3)+2*R(15,j-2)+2*R(15,j-1)+R(15,j))/6)/1000;Res(3,i)+DeltaTw;Res(4,i)+(R(16,j-3)+2*R(16,j-2)+2*R(16,j-1)+R(16,j))/6;0;0;0;0;0;0;0;0;0;0];
            Res_cc(1,i+1)=Res_cc(1,i)+(R_cc(14,j-3)+2*R_cc(14,j-2)+2*R_cc(14,j-1)+R_cc(14,j))/6;
            Res_cc(2,i+1)=(1000*Res_cc(2,i)+(R_cc(15,j-3)+2*R_cc(15,j-2)+2*R_cc(15,j-1)+R_cc(15,j))/6)/1000;
            Res_cc(3,i+1)=Res_cc(3,i)+DeltaTw;
            Res_cc(4,i+1)=Res_cc(4,i)+(R_cc(16,j-3)+2*R_cc(16,j-2)+2*R_cc(16,j-1)+R_cc(16,j))/6;
            Res_cc(5,i+1)=T_da_ss(Res_cc(2,i+1),Res_cc(1,i+1),pT);
            Res_cc(6,i+1)=100;
            Res_cc(7,i+1)=Res_cc(5,i+1);
        end
    end
    
    w(f)=Res_cc(1,N+1);
    wo=w(f); 
    end
    
    %%%%-----------REPRESNTACION DE RESULTADOS POR PANTALLA-------
    %fprintf('\n                                                         RESULTADOS DE LA MATRIZ R');
    %fprintf('\nw(kg/kg)     |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(1,1),R_cc(1,2),R_cc(1,3),R_cc(1,4),R_cc(1,5),R_cc(1,6),R_cc(1,7),R_cc(1,8));
    %fprintf('\nhma(j/kg)    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |', R_cc(2,1),R_cc(2,2),R_cc(2,3),R_cc(2,4),R_cc(2,5),R_cc(2,6),R_cc(2,7),R_cc(2,8));
    %fprintf('\nTw(ºC)       |%f      |%f      |%f      |%f      |%f      |%f      |%f      |%f      |', R_cc(3,1),R_cc(3,2),R_cc(3,3),R_cc(3,4),R_cc(3,5),R_cc(3,6),R_cc(3,7),R_cc(3,8));
    %fprintf('\nTw Cp(ºC)    |%f      |%f      |%f      |%f      |%f      |%f      |%f      |%f      |', R_cc(4,1),R_cc(4,2),R_cc(4,3),R_cc(4,4),R_cc(4,5),R_cc(4,6),R_cc(4,7),R_cc(4,8));
    %fprintf('\nCpa(J/kg*K)  |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(5,1),R_cc(5,2),R_cc(5,3),R_cc(5,4),R_cc(5,5),R_cc(5,6),R_cc(5,7),R_cc(5,8));
    %fprintf('\nCpv(J/kg*K)  |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(6,1),R_cc(6,2),R_cc(6,3),R_cc(6,4),R_cc(6,5),R_cc(6,6),R_cc(6,7),R_cc(6,8));
    %fprintf('\nCpw(J/kg*K)  |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(7,1),R_cc(7,2),R_cc(7,3),R_cc(7,4),R_cc(7,5),R_cc(7,6),R_cc(7,7),R_cc(7,8));
    %fprintf('\nPv(Pa)       |%f     |%f     |%f     |%f     |%f     |%f     |%f     |%f     |', R_cc(8,1),R_cc(8,2),R_cc(8,3),R_cc(8,4),R_cc(8,5),R_cc(8,6),R_cc(8,7),R_cc(8,8));
    %fprintf('\nWsw(Kg/kg)   |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(9,1),R_cc(9,2),R_cc(9,3),R_cc(9,4),R_cc(9,5),R_cc(9,6),R_cc(9,7),R_cc(9,8));
    %fprintf('\nhv(J/kg)     |%f  |%f  |%f  |%f  |%f  |%f  |%f  |%f  |', R_cc(10,1),R_cc(10,2),R_cc(10,3),R_cc(10,4),R_cc(10,5),R_cc(10,6),R_cc(10,7),R_cc(10,8));
    %fprintf('\nhma,sw(J/kg) |%f    |%f   |%f   |%f   |%f   |%f  |%f   |%f  |', R_cc(11,1),R_cc(11,2),R_cc(11,3),R_cc(11,4),R_cc(11,5),R_cc(11,6),R_cc(11,7),R_cc(11,8));
    %fprintf('\nLe           |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(12,1),R_cc(12,2),R_cc(12,3),R_cc(12,4),R_cc(12,5),R_cc(12,6),R_cc(12,7),R_cc(12,8));
    %fprintf('\nL/G          |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(13,1),R_cc(13,2),R_cc(13,3),R_cc(13,4),R_cc(13,5),R_cc(13,6),R_cc(13,7),R_cc(13,8));
    %fprintf('\nj            |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(14,1),R_cc(14,2),R_cc(14,3),R_cc(14,4),R_cc(14,5),R_cc(14,6),R_cc(14,7),R_cc(14,8));
    %fprintf('\nk            |%f    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |', R_cc(15,1),R_cc(15,2),R_cc(15,3),R_cc(15,4),R_cc(15,5),R_cc(15,6),R_cc(15,7),R_cc(15,8));
    %fprintf('\nl            |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(16,1),R_cc(16,2),R_cc(16,3),R_cc(16,4),R_cc(16,5),R_cc(16,6),R_cc(16,7),R_cc(16,8));
    %fprintf('\nMe           |%f        |%f        |%f        |%f        |%f        |%f        |%f        |%f        |', R_cc(17,1),R_cc(17,2),R_cc(17,3),R_cc(17,4),R_cc(17,5),R_cc(17,6),R_cc(17,7),R_cc(17,8));
    %fprintf('\nk            |%f    |%f    |%f    |%f    |%f    |%f    |%f    |%f    |', R_cc(15,1),R_cc(15,2),R_cc(15,3),R_cc(15,4),R_cc(15,5),R_cc(15,6),R_cc(15,7),R_cc(15,8));
    
    
    
    %fprintf('\n\n\n                                                         RESULTADOS DE LA MATRIZ RES');
    %fprintf('\nw(kg/kg)     |%f      |%f      |%f      |', Res_cc(1,1),Res_cc(1,2),Res_cc(1,3));
    %fprintf('\nhma(j/kg)    |%f     |%f     |%f     |', Res_cc(2,1),Res_cc(2,2),Res_cc(2,3));
    %fprintf('\nTw(ºC)       |%f    |%f    |%f    |', Res_cc(3,1),Res_cc(3,2),Res_cc(3,3));
    %fprintf('\nMe           |%f      |%f      |%f      |', Res_cc(4,1),Res_cc(4,2),Res_cc(4,3));
    %fprintf('\nTdb(K)       |%f    |%f    |%f    |', Res_cc(5,1),Res_cc(5,2),Res_cc(5,3));
    %fprintf('\nPhi(-)   |%f     |%f    |%f    |', Res_cc(6,1),Res_cc(6,2),Res_cc(6,3));
    %fprintf('\nTwb(K)       |%f    |%f    |%f    |', Res_cc(7,1),Res_cc(7,2),Res_cc(7,3));
    
    Me_Poppe=Res_cc(4,N+1);
    %R_cc=R_cc;
    %Res_cc=Res_cc;
    
    %load PshycrometricChart.mat
    
    %figure, plot(PshycrometricChart(:,1),PshycrometricChart(:,3));
    %hold on, plot(PshycrometricChart(:,1),PshycrometricChart(:,4),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,5),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,6),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,7),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,8),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,9),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,10),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,11),'r:');
    %plot(PshycrometricChart(:,1),PshycrometricChart(:,12),'r:');
    %---------- axis([0 40 0 60])
    
    
    %plot((Res_cc(5,:)-273.15),(Res_cc(1,:)*1000),'k');
    
    %xlabel('Temperatura (ºC)','FontName','TrebuchetMS','FontSize', 11);
    %ylabel('Humedad (g_v / kg_{as})','FontName','TrebuchetMS','FontSize', 11);
    %text(3,45,'Presión = 101325 Pa','FontSize',7)
    %legend 'BOXOFF'
    
    M_lost_wct = ma*(Res_cc(1,N+1)-Res_cc(1,1));
    
end

% Helper function to solve with a single initial point (for parfeval)
function [x, fval, exitflag] = solve_wct_with_initial_point(fun, x0, options)
    [x, fval, exitflag] = fsolve(fun, x0, options);
end

% Helper function to evaluate a single temperature candidate
function [error_val, success] = evaluate_single_temperature(Me_Poppe_func, Me_corr, Twct_out_candidate)
    try
        Me_Poppe_val = Me_Poppe_func(Twct_out_candidate);
        error_val = Me_Poppe_val - Me_corr;
        success = true;
    catch
        error_val = inf;
        success = false;
    end
end
