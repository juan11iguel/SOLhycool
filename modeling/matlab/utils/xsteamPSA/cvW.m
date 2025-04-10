function cv_water = cvW(temperature,pressure)

% cvW.m
% Usage: cv_water = cvW(temperature,pressure)
% temperature in ºC
% pressure in bar
% cv_water in kJ/kg-C
% Created by Diego Alarcón (09/02/2011)
% Last modification by Diego Alarcón (09/03/2017)
%

[num_row,num_col]=size(temperature);
cv_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        cv_water(k)=NaN;
    else
        cv_water(k)=XSteam('Cv_pT',pressure(k),temperature(k));
    end;
end;



