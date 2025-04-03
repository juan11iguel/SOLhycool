function [wdc,wwct,detailed] = fans_calculator(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, Tv_C, options)
    % FANS CALCULATOR calculates the frequency (%) of the fans for a specific CC configuration.
    % The system is composed by a condenser and a combined cooler.
    %
    %   Inputs:
    %       Tamb_C      - Ambient temperature (°C)
    %       HR_pp       - Relative humidity in percentage, e.g., 50% (%)
    %       mv_kgh      - Steam mass flow rate (kg/h)
    %       qc_m3h      - Cooling flow rate (m³/h)
    %       Rs          - Series distribution ratio (-)
    %       Rp          - Parallel distribution ratio (-)
    %       wdc         - DC fan percentage (%)
    %       wwct        - WCT fan percentage (%)
    %       model_type  - Type of model to use ('first_principles' or 'data_based')
    %       parameters  - Model parameters such as limits, models data paths, etc (optional)
    %
    %   Outputs:
    %       Tv_C        - Vapour temperature in the condenser (°C)
    %       Ce_kWe      - Electrical consumption of the cooler (kWe)
    %       Cw_lh       - Water consumption (l/h)
    %       detailed    - Struct containing detailed simulation results


arguments (Input)
    Tamb_C (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(Tamb_C, 50)}
    HR_pp (1,1) double {mustBeNonnegative, mustBeLessThanOrEqual(HR_pp, 100)}
    mv_kgh (1,1) double {mustBePositive}
    qc_m3h (1,1) double {mustBePositive}
    Rp (1,1) double {mustBeLessThanOrEqual(Rp, 1)}
    Rs (1,1) double {mustBeLessThanOrEqual(Rs, 1)}
    Tv_C double {mustBeGreaterThanOrEqual(Tv_C, 20), mustBeLessThanOrEqual(Tv_C, 60)} = []

    % Using keyword arguments does not work when exporting the model to
    % python
    options = struct('model_type', 'data', 'silence_warnings', true, 'parameters', default_parameters()); % Default values

    
end

arguments (Output)
    wdc (1,1) double
    wwct (1,1) double
    detailed (1,1) struct
end

% Unpack options
parameters = options.parameters;
model_type = options.model_type;
silence_warnings = options.silence_warnings;
    
% Add utilities path
addpath(genpath('utils\'));
addpath(genpath('component_models\'));

if silence_warnings
    display_solver = 'none';
else
    display_solver = 'final-detailed';
end

%% Condiciones de entrada
% % Tamb_C=32;
% % HR_pp=50;
A_SC=parameters.condenser_A; %19.59;  %% Calculado por Patricia ->> Hay que pasarlo como parámetro de entrada
% Tv_C=34.62; %% Calculado por Patricia
% ms_kgh=295.2; %% Calculado por Patricia (kg/h)
% mc=24;    %% Lo fijamos a este valor en principio (m3/h)
model_type = options.model_type;
tm=1; % por defecto modelo basado en datos
if model_type ~= "data"
    tm=2;
end;


%% Condiciones en los ventildores
w_fan_dc_min = 11;   % (%)
w_fan_dc_max  = 99; % (%)
w_fan_dc_fijo = 20; % (%) establecido para configuración serie. Este valor puede cambiar al máximo bajo algunas condiciones
w_fan_wct_min = 21; %
w_fan_wct_max = 93.4161; %

%% Calcula setpoint de temperatura a la entrada del surface condenser
ms_u=mv_kgh/3600; % kg/s
mc_u=qc_m3h*1000/3600; % kg/s
landa=XSteam('hV_T',Tv_C)-XSteam('hL_T',Tv_C);
% Cp=XSteam('Cp_pT',2,(x(4)+x(3))/2);
Q=ms_u*landa;

% Poner fmincon con restricciones en Q, Tv_C
fun = @(x) SurfaceCondeser_v4(x, A_SC, Tv_C, Q, qc_m3h); 
options2 = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11, 'Display',display_solver);
lb=[10,10]; 
ub=[Tv_C,Tv_C];

x0 = [Tv_C-10,Tv_C-2];
[x,fval]=fmincon(fun,x0,[],[],[],[],lb,ub,[],options2);
Tcin_sp=x(1);
Tcout=x(2);

Twct_out=Tcin_sp;
Tdc_out=Tcin_sp;

ParoDC=0;
MaxDC=0;


%% Chequeo si se puede operar con DC o no
dT=2; %rango para chequear si se puede emplear DC o no
if Tcout<(Tamb_C-dT)
    ParoDC=1; %no tiene sentido trabajar con el DC
    Rp = 1; % fuerzo a configuración solo WCT
else
    if (Tcin_sp<(Tamb_C-dT) && Rs<0.01) %solo tiene sentido este check en paralelo o DC
        MaxDC=1; %estado DC al máximo
        wdc = w_fan_dc_max;
        if Rp<1
            Rp=1; % en el caso de Solo DC lo paso a serie
            w_fan_dc_fijo=w_fan_dc_max;
        else % caso paralelo
            %hay que recalcular valor de setpoint en WCT
            % primero calcular la Tout_dc (empleo modelo de datos)
            qdc = qc_m3h*(1-Rp); %m3/h
            Tout_dc = dc_model(Tamb_C, Tcout, qdc, wdc);
            % segundo calcular SP en Toutwct
            qwct_p = qc_m3h*Rp;
            Twct_out=(qc_m3h*Tcin_sp-qdc*Tout_dc)/qwct_p;
        end;
    end;
end;

%% Tipo de configuración
% Rp=0;
% Rs=0;
qdc = qc_m3h*(1-Rp); %m3/h
qwct_p = qc_m3h*Rp;
qwct_s = qdc*Rs;
qwct = qwct_p + qwct_s;


%% Calcula frecuencia de ventiladores
w_dc_fan=0; % valoresa iniciales
w_wct_fan=0;

A = []; b = []; Aeq = []; beq = [];
%options_fmincon = optimoptions(@fmincon,'Algorithm','sqp','TolFun',1e-9,'MaxIterations', 10);
options_fmincon = optimoptions('fmincon', 'Algorithm', 'sqp', 'OptimalityTolerance', 1e-10, 'StepTolerance', 1e-11,'MaxIterations', 6, 'Display',display_solver); 


% if Rs>0
%     Tdc_out=decidir;
% end
if (Rp~=1 && Rs<0.01 && ParoDC==0 && MaxDC==0) % DC funcionando y no está en serie y no está al máximo por la Tamb
    fun = @(x)calculo_w_dc(x, Tdc_out, Tamb_C, qdc, Tcout, tm);
    lb = w_fan_dc_min; ub = w_fan_dc_max; x0 = 50;

    %Hay que meter la búsqueda con distintas condiciones iniciales
    [w_dc_fan , fval_initial, exitflag, output] = fmincon(fun,x0,A,b,Aeq,beq,lb,ub,[],options_fmincon);

    if contains(output.message, 'Initial point is a local minimum')
        if ~silence_warnings
            fprintf('Initial point detected as local minimum. Running random restarts...\n');
        end
    
        % Random Restart settings
        numRestarts = 5;
        bestSolution = w_dc_fan;
        bestFval = 1e10000; %fval_initial
    
        x0_rand=100*(rand(1,numRestarts));
        x0_rand=min(x0_rand,w_fan_dc_max);
        x0_rand=max(x0_rand,w_fan_dc_min);

        for i = 1:numRestarts
            x0_perturbed = x0_rand(i);
    
            % Run fmincon with the perturbed initial guess
            [x, fval, exitflag, output] = fmincon(fun,x0_perturbed,A,b,Aeq,beq,lb,ub,[],options_fmincon);
            if ~silence_warnings
                fprintf('Restart %d: fval = %f, x = %f\n', i, fval, x);
            end
    
            % Update best solution if found
            if fval < bestFval
                bestFval = fval;
                w_dc_fan = x;
            end
            
        end
    
        % Display the best solution from random restarts
        if ~silence_warnings
            fprintf('Best solution found via random restarts: %f with fval = %f\n', w_dc_fan, bestFval);
        end
    else
       if ~silence_warnings
            fprintf('Initial point was not detected as a local minimum, so no random restarts are performed.\n');
       end
    end;  
%     % Chequeo si está al máximo el DC
%     if w_dc_fan==w_fan_dc_max
%         % primero calcular la Tout_dc (empleo modelo de datos)
%         Tout_dc = dc_model(Tamb_C, Tcout, qdc, w_dc_fan);
%         % segundo calcular el nuevo SP en Toutwct
%         qwct_p = qc_m3h*Rp;
%         Twct_out=(qc_m3h*Tcin_sp-qdc*Tout_dc)/qwct_p; 
%     end;
else
    if (Rp~=1 && Rs>0.95 && ParoDC==0) %serie Rs~=0
        w_dc_fan=w_fan_dc_fijo;
    end;
end;

if Rp>0.1 %~=0  % WCT funcionando
    fun = @(x)calculo_w_wct(x, Twct_out, Tamb_C, qwct, Tcout, HR_pp, tm);
    %fun = @(x)calculo_w_wct(x, Tdc_out, Tamb_C, qwct, Tcout, HR_pp, tm);
    lb = w_fan_wct_min; ub = w_fan_wct_max; x0 = 50;

    %Hay que meter la búsqueda con distintas condiciones iniciales
    [w_wct_fan , fval_initial, exitflag, output] = fmincon(fun,x0,A,b,Aeq,beq,lb,ub,[],options_fmincon);

    if contains(output.message, 'Initial point is a local minimum')
        if ~silence_warnings
            fprintf('Initial point detected as local minimum. Running random restarts...\n');
        end
    
        % Random Restart settings
        numRestarts = 5;
        bestSolution = w_wct_fan;
        bestFval = 1e10000; %fval_initial;
    
        x0_rand=100*(rand(1,numRestarts));
        x0_rand=min(x0_rand,w_fan_dc_max);
        x0_rand=max(x0_rand,w_fan_dc_min);

        for i = 1:numRestarts
            x0_perturbed = x0_rand(i);
    
            % Run fmincon with the perturbed initial guess
            [x, fval, exitflag, output] = fmincon(fun,x0_perturbed,A,b,Aeq,beq,lb,ub,[],options_fmincon);
            if ~silence_warnings
                fprintf('Restart %d: fval = %f, x = %f\n', i, fval, x);
            end;
    
            % Update best solution if found
            if fval < bestFval
                bestFval = fval;
                w_wct_fan = x;
            end
        end
    
        if ~silence_warnings
            % Display the best solution from random restarts
            fprintf('Best solution found via random restarts: %f with fval = %f\n', w_wct_fan, bestFval);
        end;
    else
        if ~silence_warnings
            fprintf('Initial point was not detected as a local minimum, so no random restarts are performed.\n');
        end;
    end; 
else
    %solo DC
    w_wct_fan=0;
end;

wdc=w_dc_fan;
wwct= w_wct_fan;

% With wwct, evaluate model
[~, ~, detailed] = combined_cooler_model(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, wdc, wwct, Tv_C, options);
