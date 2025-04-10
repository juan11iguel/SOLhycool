function [pressure]=pSatW(temperature)

% pSatW.m
% Usage: [pressure]=pSatW(temperature)
% temperature in ºC
% pressure in bar

[num_row,num_col]=size(temperature);
pressure=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        pressure(k)=NaN;
    else
        pressure(k)=XSteam('psat_T',temperature(k));
    end;
end;

