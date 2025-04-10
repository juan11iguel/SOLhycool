function [temperature]=tSatW(pressure)

% tSatW.m
% Usage: [temperature]=tSatW(pressure)
% pressure in bar
% temperature in ºC
% Created by Diego Alarcón (07/12/2007)
% Last modification by -- (09/03/2017)
%

[num_row,num_col]=size(pressure);
temperature=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(pressure(k))
        temperature(k)=NaN;
    else
        temperature(k)=XSteam('Tsat_p',pressure(k));
    end;
end;

