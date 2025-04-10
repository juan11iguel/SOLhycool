function density_satliq = densSatLiqTW(temperature)

% densSatLiqTW.m
% Usage: density_satvapor = densSatLiqTW(temperature)
% temperature in ºC
% density in kg/m3

[num_row,num_col]=size(temperature);
density_satliq=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        density_satliq(k)=NaN;
    else
        density_satliq(k)=XSteam('rhoL_T',temperature(k));
    end;
end;