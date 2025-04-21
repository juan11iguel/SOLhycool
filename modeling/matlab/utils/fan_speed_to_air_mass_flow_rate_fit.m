function ma_kgs = fan_speed_to_air_mass_flow_rate_fit(w_pct)
    % Polynomial fit to convert from fan speed (as a VFD percentage)
    % to air mass flow rate in kg/s
    
    p1 = -0.0014;
    p2 = 0.1743;
    p3 = -0.7251;

    ma_kgs = p1*(w_pct/2)^2 + p2*w_pct/2 + p3;
end