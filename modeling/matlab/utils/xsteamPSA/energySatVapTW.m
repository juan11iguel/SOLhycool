function energy_water = energySatVapTW(temperature)

% energySatVapTW.m
% Usage: energy_water = energySatVapTW(temperature)
% temperature in ºC
% enthalpy in kJ/kg

[num_row,num_col]=size(temperature);
energy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        energy_water(k)=NaN;
    else
        energy_water(k)=XSteam('uV_T',temperature(k));
    end;
end;




