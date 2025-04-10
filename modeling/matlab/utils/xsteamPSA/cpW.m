function cp_water = cpW(temperature,pressure)

% cpW.m
% Usage: cp_water = cpW(temperature,pressure)
% temperature in ºC
% pressure in bar
% cp_water in kJ/kg-C
% Created by Diego Alarcón (09/02/2011)
% Last modification by Diego Alarcón (09/03/2017)
%

[num_row,num_col]=size(temperature);
cp_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        cp_water(k)=NaN;
    else
        cp_water(k)=XSteam('Cp_pT',pressure(k),temperature(k));
    end;
end;



