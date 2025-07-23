function Ce_c_kW = recirculation_pump_consumption(qc_m3h, coeffs)
    % RECIRCULATION_PUMP_CONSUMPTION  Calculates pump electrical consumption from flow rate.
    %
    % Inputs:
    %   qc      - Volumetric flow rate (m³/h)
    %   coeffs  - Polynomial coefficients (optional, default: [0.1461, 5.763, -38.32, 227.8])
    %
    % Outputs:
    %   Ce_c    - Electrical consumption (kW)
    % q (m³/h) -> P_pump (kW)
    
    % TODO: Should be qc (m³/h), Rp, Rs -> Ce_c (kW)

    arguments
        qc_m3h (1,1) double {mustBeNonnegative}
        coeffs (1,:) double = [0.1461, 5.763, -38.32, 227.8]
    end

    Ce_c_kW = max(polyval(coeffs, qc_m3h) * 1e-3, 0); % kW
end