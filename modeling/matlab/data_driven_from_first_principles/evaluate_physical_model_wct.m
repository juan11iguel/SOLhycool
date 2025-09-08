%% 
% Generar conjunto de salidas con los modelos físicos para crear modelo
% basado en datos
% 
% This script should be run with the current path being the base MATLAB project folder
% 
% Author: Lidia Roca Sobrino
% -------------------------------------------------------------------------

clc
clear

% Parameters
input_data_path = "../results/model_inputs_sampling/pilot_plant_200kW/wct_in.csv";
output_data_path = "../results/model_outputs_physical/pilot_plant_200kW/wct_out.csv";

tic
%load wct_inputs.mat;
wct=readtable(input_data_path);


% Asegurarnos de que el parallel pool está activo
if isempty(gcp('nocreate'))
        parpool;  % Abre pool si no está
end

PV=ones(size(wct,1),1); % inicialmente todos son puntos válidos
for i=1:size(wct,1)
    pool = gcp(); % Obtener el pool de procesamiento paralelo  
    % --- Aquí va la función que podría tardar ---
    % Extraer parámetros necesarios
    Tamb     = wct.Tamb(i);
    HR       = wct.HR(i);
    Twct_in  = wct.Twct_in(i);
    qwct     = wct.qwct(i);
    wwct     = wct.wwct(i);

    miFuncion = @(Tamb, HR, Twct_in, qwct, wwct) ...
        wct_model_elx(Tamb, HR, Twct_in, qwct, wwct, ...
                  80, 'c_poppe', 1.52, 'n_poppe', -0.69);    
    
    % Llamar a la función en segundo plano
    future = parfeval(@() miFuncion(Tamb, HR, Twct_in, qwct, wwct), 2);

    % Tiempo máximo permitido
    timeout = 5; % segundos
    % Control de tiempo manual
    t0 = tic;
    while ~strcmp(future.State, 'finished')
        pause(0.1);  % Dejar respirar al sistema
    
        if toc(t0) > timeout
            cancel(future);
            disp(['⏱ Timeout alcanzado en i = ', num2str(i), '.']);
            Tout_simu(i) = NaN;
            Mw_lost_Lmin(i) = NaN;
            break
        end
    end

    % Solo recoger resultado si terminó bien
    if strcmp(future.State, 'finished')
        try
            [Tout_simu(i), Mw_lost_Lmin(i)] = fetchOutputs(future);
            disp(['✅ i = ', num2str(i), ' completado / ', num2str(size(wct,1))]);
            
        catch ME
            disp(['❌ Error interno en función: ', ME.message]);
            Tout_simu(i) = NaN;
            Mw_lost_Lmin(i) = NaN;
            PV(i) = 0;
        end
    end   

%     % Esperar con tiempo límite (por ejemplo, 5 segundos)
%     tiempo_limite = 5; % segundos  
% 
%     % Esperar con límite
%     exito = wait(future, tiempo_limite);
% 
%     if exito
%         % Obtener resultados con límite de tiempo
%         [Tout_simu_i, Mw_lost_i] = fetchOutputs(future);
%     
%         % Asignar resultados a los arrays
%         Tout_simu(i)     = Tout_simu_i;
%         Mw_lost_Lmin(i)  = Mw_lost_i;
%     
%         disp(['✅ i = ', num2str(i), ' completado.']);
%     
%     else
%         cancel(future);  % Cancelar si se pasó de tiempo
%         Tout_simu(i)     = NaN;
%         Mw_lost_Lmin(i)  = NaN;
%         disp(['⏱ Tiempo excedido en i = ', num2str(i), '. Se usó NaN.']);
%         PV(i) = 0;
%     end

%     if PV(i)==1
%       % [Tdb(i), w, phi, h, Tdp, v, Twb] = Psychrometricsnew('Tdb',wct.Tamb(i),'phi',wct.HR(i)); 
%        [Tdb, w, phi, h, Tdp, v, Twb(i)] = Psychrometricsnew('Tdb',wct.Tamb(i),'phi',wct.HR(i)); 
%     else
%        % Tdb(i) = NaN;
%         Twb(i) = NaN;
%     end;

end

%% Guardo datos con el formato deseado
wct_out=wct(:,2:end); % la primera columna no la queremos
wct_out.Properties.VariableNames(3) = "Tin";
wct_out.Properties.VariableNames(4) = "q";
wct_out.Properties.VariableNames(5) = "w_fan";
wct_out = removevars(wct_out, "Twb");
wct_out = removevars(wct_out, "mw_ma_ratio");

wct_out.Twct_out=Tout_simu';
wct_out.Cw_lh=Mw_lost_Lmin'.*60;
wct_out.Properties.VariableNames(6) = "Tout";
wct_out.Properties.VariableNames(7) = "m_w_lost";

%% Elimino NaNs
% Encuentra las filas que tienen al menos un NaN
filasConNaN = any(ismissing(wct_out), 2);

% Elimina esas filas
wct_out_sinnan = wct_out(~filasConNaN, :);

%% Guardo en .csv
writetable(wct_out_sinnan, output_data_path);

%% Dibujo figura para chequear si tiene buena pinta las salidas
for i=1:size(wct_out_sinnan,1)
    [Tdb, w, phi, h, Tdp, v, Twb(i)] = Psychrometricsnew('Tdb',wct_out_sinnan.Tamb(i),'phi',wct_out_sinnan.HR(i)); 
    Tww =wct_out_sinnan.Tin(i);
    Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
   ma(i) = ajuste_m_dot_aT(wct_out_sinnan.w_fan(i),wct_out_sinnan.Tamb(i)); 
   %ma(i) = ajuste_m_dot_a(wct_out_sinnan.q(i)); 
    Mwct(i) = wct_out_sinnan.q(i);
    mw(i) = Mwct(i) * Dens_agua /3600;
    ratio(i)=(mw(i)/ma(i));
    dT(i) = wct_out_sinnan.Tin(i)-wct_out_sinnan.Tout(i); %Tout_simu(i);
    
end
% Crear gráfico de dispersión 3D
figure
scatter3(Twb, ratio, dT, 'filled')
xlabel('T_{wb}')
ylabel('ratio')
zlabel('dT')

figure
scatter3(Twb, ratio, wct_out_sinnan.m_w_lost, 'filled')
xlabel('T_{wb}')
ylabel('ratio')
zlabel('Mw_lost_Lmin')

elapsed_time=toc;
fprintf('Terminado en %0.1f s', elapsed_time)


%% Compruebo los nan y números complejos que había
total_nan=sum(isnan(Tout_simu));
fprintf('Soluciones no encontradas (=NaN): %0.0f \n', total_nan)

tol = 1e-10;
Tout_simu_valid = Tout_simu;
Mwlost_simu_valid = Mw_lost_Lmin;
for i=1:size(Tout_simu,1)
    if abs(imag(Tout_simu(i))) ~= 0
        Tout_simu_valid = NaN;
        Nwlost_simu_valid = NaN;
    end;
end;

total_nan=sum(isnan(Tout_simu_valid));
fprintf('Soluciones no encontradas (=NaN) y no complejas: %0.0f \n', total_nan)


%% Functions

function m_dot_a = ajuste_m_dot_aT(SC_fan_wct,Tamb)
    p00 =   -0.0433;
    p10 =   0.1650;
    p01 =   -0.0273;   
    p20 =   -0.0013;  
    p11 =   0.0000;    
    p02 =   0.0003;    
    m_dot_a = p00 + p10*(SC_fan_wct/2) + p01*Tamb + p20*(SC_fan_wct/2)^2 + p11*(SC_fan_wct/2)*Tamb + p02*Tamb^2;
end

function m_dot_a = ajuste_m_dot_a(SC_fan_wct)
        p1 = -0.0014;
        p2 = 0.1743;
        p3 = -0.7251;
        m_dot_a = p1*(SC_fan_wct/2)^2 + p2*SC_fan_wct/2 + p3;
end

