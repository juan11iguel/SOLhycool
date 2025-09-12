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

addpath("component_models/")

%% Parameters

n_dc = 1; % 231; % 115; % 1 % 346
case_study_id = "pilot_plant_200kW"; % "andasol_25_90MW"; % "pilot_plant_200kW";

input_data_path = sprintf("../results/model_inputs_sampling/%s/dc_in.csv", case_study_id);
output_data_path = sprintf("../results/model_inputs_sampling/%s/dc_out.csv", case_study_id);

%% Load data and start parallel pool
%load dc_inputs.mat;
dc=readtable(input_data_path);

% Asegurarnos de que el parallel pool está activo
if isempty(gcp('nocreate'))
        parpool;  % Abre pool si no está
end

%% Evaluate inputs

tic
PV=ones(size(dc,1),1); % inicialmente todos son puntos válidos
for i=1:size(dc,1)
    pool = gcp(); % Obtener el pool de procesamiento paralelo  
    % --- Aquí va la función que podría tardar ---
    % Extraer parámetros necesarios
    Tamb     = dc.Tamb(i);
    Tdc_in   = dc.Tdc_in(i);
    qdc      = dc.qdc(i);
    wdc      = dc.wdc(i);
    
%     % Llamar a la función en segundo plano
     future = parfeval(@() dc_model_physical(Tamb, Tdc_in, qdc, wdc, n_dc), 1);
%     Tout_simu(i)= fetchOutputs(future);

    % Tiempo máximo permitido
    timeout = 2; % segundos
    % Control de tiempo manual
    t0 = tic;
    while ~strcmp(future.State, 'finished')
        pause(0.1);  % Dejar respirar al sistema
    
        if toc(t0) > timeout
            cancel(future);
            disp(['⏱ Timeout alcanzado en i = ', num2str(i), '.']);
            Tout_simu(i) = NaN;            
            break
        end
    end

    % Solo recoger resultado si terminó bien
    if strcmp(future.State, 'finished')
        try
            Tout_simu(i) = fetchOutputs(future);
             disp(['✅ i = ', num2str(i), ' completado / ', num2str(size(dc,1))]);
        catch ME
            disp(['❌ Error interno en función: ', ME.message]);
            Tout_simu(i) = NaN;
            Mw_lost_Lmin(i) = NaN;
            PV(i) = 0;
        end
    end   

end


%% Guardo datos con el formato deseado
% Renombrar columnas existentes
dc_out = dc(:,2:end); % quitar primera columna
dc_out.Properties.VariableNames(2:4) = ["Tin","q","w_fan"];

% Añadir nueva columna Tout
dc_out.Tdc_out = Tout_simu';
dc_out.Properties.VariableNames(end) = "Tout";

% Intercambiar columnas "q" y "w_fan"
dc_out = dc_out(:, ["Tamb", "Tin","w_fan","q","Tout"]);

%% Elimino NaNs
% Encuentra las filas que tienen al menos un NaN
filasConNaN = any(ismissing(dc_out), 2);

% Elimina esas filas
dc_out_sinnan = dc_out(~filasConNaN, :);

%%
writetable(dc_out_sinnan, output_data_path);
fprintf("Results saved to %s\n", output_data_path)

%% Dibujo figura para chequear si tiene buena pinta las salidas
% for i=1:length(Tout_simu)
%     %[Tdb(i), w, phi, h, Tdp, v, Twb] = Psychrometricsnew('Tdb',wct.Tamb(i),'phi',wct.HR(i)); 
% %     Tww =wct.Tdc_in(i);
% %     Dens_agua=-1.72087973954183E-07*Tww^4+0.0000480220158358691*Tww^3-0.00782109015813148*Tww^2+0.0563115452841885*Tww+999.8;
% %     ma(i) = ajuste_m_dot_aT(wct.wdc(i),wct.Tamb(i)); 
% %     Mwct(i) = wct.qdc(i);
% %     mw(i) = Mwct(i) * Dens_agua /3600;
% %     ratio(i)=(mw(i)/ma(i));
%     dT(i) = dc.Tdc_in(i)-Tout_simu(i);
% 
% end
% % Crear gráfico de dispersión 3D
% scatter3(dc.Tamb, dc.qdc, dT, 'filled')
% xlabel('T_{amb}')
% ylabel('q')
% zlabel('dT')
% % figure
% % scatter3(Tdb, ratio, Mw_lost_Lmin, 'filled')
% % 
% % elapsed_time=toc;
% % fprintf('Terminado en %0.1f s', elapsed_time)
% 
% 
% %% Elimino números complejos
% total_nan=sum(isnan(Tout_simu));
% fprintf('Soluciones no encontradas (=NaN): %0.0f \n', total_nan)
% 
% tol = 1e-10;
% Tout_simu_valid = Tout_simu;
% Nwlost_simu_valid = Mw_lost_Lmin;
% for i=1:size(Tout_simu,1)
%     if abs(imag(Tout_simu(i))) ~= 0
%         Tout_simu_valid = NaN;
%         Nwlost_simu_valid = NaN;
%     end;
% end;
% 
% total_nan=sum(isnan(Tout_simu_valid));
% fprintf('Soluciones no encontradas (=NaN) y no complejas: %0.0f \n', total_nan)
% 


