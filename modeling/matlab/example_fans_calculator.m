% Prueba de fans_calculator
% Nota importante: Solo este tipo de configuraciones:
    % Only WCT (Rp=1)
    % Only DC (Rp=0 & Rs=0)
    % Paralelo (Rp entre 0 y 1 & Rs=0)
    % Serie puro (Rp entre 0 y 1 & Rs=1)
%%%%

clear
clc 
Tamb_C=20;
HR_pp=50;
mv_kgh=290;
qc_m3h=24;
Rp=1;
Rs=0;
Tv_C=33;
parameters=default_parameters();
parameters.condenser_A = 19.59;
options_fans = struct('model_type', 'data_based', 'parameters', parameters, 'silence_warnings', true);

[wdc,wwct] = fans_calculator(Tamb_C, HR_pp, mv_kgh, qc_m3h, Rp, Rs, Tv_C, options_fans);

