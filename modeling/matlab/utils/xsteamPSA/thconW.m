function thcon_water = thconW(temperature,pressure)

% thconW.m
% Usage: thcon_water = thconW(temperature,pressure)
% temperature in ºC
% pressure in bar
% thcon_water in W/m-C
% Created by Diego Alarcón (12/02/2021)
% Last modification by Diego Alarcón (12/02/2021)
%

[num_row,num_col]=size(temperature);
thcon_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        thcon_water(k)=NaN;
    else
        thcon_water(k)=XSteam('tc_pT',pressure(k),temperature(k));
    end;
end;



