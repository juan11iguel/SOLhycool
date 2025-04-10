function enthalpy_satliq = enthalpySatLiqTW(temperature)

% enthalpySatLiqTW.m
% Usage: enthalpy_satliq = enthalpySatLiqTW(temperature)
% temperature in ºC
% enthalpy in kJ/kg

[num_row,num_col]=size(temperature);
enthalpy_satliq=zeros(max(num_row,num_col),1);


for k=1:max(num_row,num_col)
    if isnan(temperature(k))
        enthalpy_satliq(k)=NaN;
    else
        enthalpy_satliq(k)=XSteam('hL_T',temperature(k));
    end;
end;




