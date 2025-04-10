function density_water = densW(temperature,pressure)

% densW.m
% Usage: density_water = densW(temperature,pressure)
% temperature in ºC
% pressure in bar
% density in kg/m3

[num_row,num_col]=size(temperature);
density_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        density_water(k)=NaN;
    else
        density_water(k)=XSteam('rho_pT',pressure(k),temperature(k));
    end;
end;
