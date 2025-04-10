function energy_water = energyW(temperature,pressure)

% energyW.m
% Usage: energy_water = energyW(temperature,pressure)
% temperature in ºC
% pressure in bar
% energy in kJ/kg


[num_row,num_col]=size(temperature);
energy_water=zeros(max(num_row,num_col),1);

if max(size(pressure))==1
    pressure = pressure * ones(max(size(temperature)),1);
end;


for k=1:max(num_row,num_col)
    if isnan(temperature(k))||isnan(pressure(k))
        energy_water(k)=NaN;
    else
        energy_water(k)=XSteam('u_pT',pressure(k),temperature(k));
    end;
end;



