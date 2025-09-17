% Test script for the modified WCT function without parfeval dependency
% This script tests the wct_model_physical_andasol function with sample inputs

clc;
clear;

% Test input parameters (typical values)
Tamb = 25;          % Ambient temperature (°C)
HR = 60;            % Relative humidity (%)
Twct_in = 40;       % WCT inlet temperature (°C)
Mwct = 1000;        % Water flow rate (m³/h)
SC_fan_wct = 80;    % Fan speed control (%)

fprintf('Testing WCT model without parfeval dependency...\n');
fprintf('Input parameters:\n');
fprintf('  Tamb = %.1f°C\n', Tamb);
fprintf('  HR = %.1f%%\n', HR);
fprintf('  Twct_in = %.1f°C\n', Twct_in);
fprintf('  Mwct = %.1f m³/h\n', Mwct);
fprintf('  SC_fan_wct = %.1f%%\n', SC_fan_wct);
fprintf('\n');

try
    % Call the modified function
    tic;
    [Twct_out, Pe, M_lost_wct] = wct_model_physical_andasol(Tamb, HR, Twct_in, Mwct, SC_fan_wct);
    elapsed_time = toc;
    
    % Display results
    fprintf('Results:\n');
    fprintf('  Twct_out = %.2f°C\n', Twct_out);
    fprintf('  Pe = %.2f kW\n', Pe);
    fprintf('  M_lost_wct = %.2f L/h\n', M_lost_wct);
    fprintf('  Execution time = %.3f seconds\n', elapsed_time);
    fprintf('\n');
    
    % Validate results
    if ~isnan(Twct_out) && ~isnan(Pe) && ~isnan(M_lost_wct)
        fprintf('✓ SUCCESS: Function executed successfully without parfeval!\n');
        
        % Basic sanity checks
        if Twct_out < Twct_in
            fprintf('✓ Physical check: Outlet temperature (%.2f°C) < Inlet temperature (%.2f°C)\n', Twct_out, Twct_in);
        else
            fprintf('⚠ Warning: Outlet temperature should be lower than inlet temperature\n');
        end
        
        if Pe > 0
            fprintf('✓ Physical check: Power consumption (%.2f kW) > 0\n', Pe);
        else
            fprintf('⚠ Warning: Power consumption should be positive\n');
        end
        
    else
        fprintf('✗ FAILURE: Function returned NaN values\n');
    end
    
catch ME
    fprintf('✗ ERROR: Function failed with error:\n');
    fprintf('  %s\n', ME.message);
    
    % Check if error is related to parfeval
    if contains(ME.message, 'parfeval') || contains(ME.message, 'Parallel')
        fprintf('  This appears to be a parfeval-related error that should now be fixed.\n');
    end
end

fprintf('\nTest completed.\n');