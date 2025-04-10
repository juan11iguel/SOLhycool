function entropy_water = entropyW(temperature,pressure)

% entropyW.m
% Usage: entropy_water = entropyW(temperature,pressure)
% temperature in ºC
% pressure in bar
% entropy in kJ/kg-K


[num_row,num_col]=size(temperature);
entropy_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        entropy_water(k)=NaN;
    else
        entropy_water(k)=XSteam('s_pT',pressure(k),temperature(k));
    end;
end;



