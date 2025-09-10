function ma_kgs = fan_speed_to_air_mass_flow_rate_fit(w_pct, system)
    % Polynomial fit to convert from fan speed (as a VFD percentage)
    % to air mass flow rate in kg/s
    arguments (Input)
        w_pct double
        system string = "pilot_plant" % "andasol"
    end

    arguments (Output)
        ma_kgs double
    end

    if strcmp(system, "pilot_plant")
        coeffs = [-0.0014, 0.1743, -0.7251];
        divide_by = 2; % Por alguna razón en el ajuste se dividió por 2, en lugar de hacer un ajuste normal ¿?
    elseif strcmp(system, "andasol")
        coeffs = [-0.01032,2.43,501.1];
        divide_by = 1;
    else
        error("Unsupported alternative")
    end
    
    
    % p1 = -0.0014;
    % p2 = 0.1743;
    % p3 = -0.7251;
    % 
    % ma_kgs = p1.*(w_pct/2).^2 + p2.*w_pct./2 + p3;

    % Evaluate polynomial at (w_pct/divide_by), vectorized
    ma_kgs = polyval(coeffs, w_pct./divide_by);
end