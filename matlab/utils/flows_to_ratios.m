function [Rp,Rs] = flows_to_ratios(qc, qdc, qwct)
    %RATIOS_TO_FLOWS Summary of this function goes here
    %   Detailed explanation goes here
    arguments
        qc double {mustBeGreaterThan(qc, 0)}
        qdc double {mustBeGreaterThanOrEqual(qdc, 0)}
        qwct double {mustBeGreaterThanOrEqual(qwct, 0)}
    end

    Rp = round(1 - qdc./qc, 3);
    if qdc < 1e-2
        % Rs = nan;
        Rs = 0; % It could be anything really
    else
        Rs = max(round( (qwct./qc-Rp) / (1-Rp), 3), 0); % 1 - (qc-qwct)./qdc;
    end
end

