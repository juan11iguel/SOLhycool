function uncertainty = calculate_uncertainty(value, type)


    if strcmp(type, "pt100")
        uncertainty = 0.3 + value * 0.005; %  ºC

    elseif strcmp(type, "vortex_flow_meter")
        uncertainty = 0.65*1e-2 * value; % m3/h

    elseif strcmp(type, "paddle_flow_meter")
        value = value/1000; % L/h -> m3/h
        uncertainty = 0.5*1e-2 * (2-0.05) + 2.5*1e-2*value; %m3/h
        uncertainty = uncertainty * 1000; % m3/h -> L/h

    else
        MException('calculate_uncertainty:unsupported_sensor', ...
            'Introduced unsupported sensor type: %s', type)
    end

end