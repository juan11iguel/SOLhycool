function density_satvapor = densSatVapTW(temperature)

% densSatVapTW.m
% Usage: density_satvapor = densSatVapTW(temperature)
% temperature in ºC
% density in kg/m3

[num_row,num_col]=size(temperature);
density_satvapor=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        density_satvapor(k)=NaN;
    else
        density_satvapor(k)=XSteam('rhoV_T',temperature(k));
    end;
end;
