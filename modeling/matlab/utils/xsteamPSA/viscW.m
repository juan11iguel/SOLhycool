function visc_water = viscW(temperature,pressure)

% viscW.m
% Usage: visc_water = viscW(temperature,pressure)
% temperature in ºC
% pressure in bar
% viscW in Pa·s
% Created by Diego Alarcón (11/02/2021)
% Last modification by Diego Alarcón (11/02/2021)
%

[num_row,num_col]=size(temperature);
visc_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        visc_water(k)=NaN;
    else
        visc_water(k)=XSteam('my_pT',pressure(k),temperature(k));
    end;
end;



