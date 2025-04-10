function enthalpy_water = enthalpyW(temperature,pressure)

% enthalpyW.m
% Usage: enthalpy_water = enthalpyW(temperature,pressure)
% temperature in ºC
% pressure in bar


[num_row,num_col]=size(temperature);
enthalpy_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        enthalpy_water(k)=NaN;
    else
        enthalpy_water(k)=XSteam('h_pT',pressure(k),temperature(k));
    end;
end;



