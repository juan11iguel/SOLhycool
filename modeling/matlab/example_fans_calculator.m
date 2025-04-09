% Prueba de fans_calculator
% Nota importante: Solo este tipo de configuraciones:
    % Only WCT (Rp=1)
    % Only DC (Rp=0 & Rs=0)
    % Paralelo (Rp entre 0 y 1 & Rs=0)
    % Serie puro (Rp entre 0 y 1 & Rs=1)->Rs>0.95
%%%%
addpath(genpath("utils/"))
addpath(genpath("component_models/"))

clear
clc 
Tamb_C=14;
HR_pp=90;
mv_kgh=200;
qc_m3h=12;
Rp=0.5;
Rs=1;
Tv_C=33;
parameters=default_parameters();
parameters.condenser_A = 19.59;
parameters.condenser_option = 9;
 options_fans = struct('model_type', 'data', 'parameters', parameters, 'silence_warnings', false);
[wdc,wwct,detallicos] = fans_calculator(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, Tv_C, options_fans);


% %% Validación con el conjunto de validación de Juanmi
% % Nota:  solo para comprobar que no hay errores porque el A y el U no son
% los mismos que en el conjunto de validación
% 
data = readtable("../assets/data.csv");
N = height(data);
wdc = zeros(1, N); 
wwct = zeros(1, N);
detallicos_lista = [];

for i=1:N
    [wdc(i),wwct(i),detallicos] = fans_calculator(data.Tamb(i), data.HR(i), data.mv(i), data.qc(i), data.Rp(i), data.Rs(i), data.Tv(i), options_fans);
    detallicos_lista = [detallicos_lista detallicos];
end
