function energy_water = energySatLiqTW(temperature)

% enthalpySatLiqTW.m
% Usage: energy_water = energySatLiqTW(temperature)
% temperature in ºC
% enthalpy in kJ/kg

[num_row,num_col]=size(temperature);
energy_water=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        energy_water(k)=NaN;
    else
        energy_water(k)=XSteam('uL_T',temperature(k));
    end;
end;




